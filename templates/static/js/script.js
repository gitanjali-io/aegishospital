document.querySelectorAll(".sidebar nav a").forEach((link) => {
    link.addEventListener("click", () => {
        document.querySelector(".sidebar nav a.active")?.classList.remove("active");
        link.classList.add("active");
    });
});

const patientsBody = document.querySelector("#patients-body");
const requestList = document.querySelector("#request-list");
const sosList = document.querySelector("#sos-list");
const hospitalForm = document.querySelector("#hospital-form");
const hospitalSelect = document.querySelector("#hospital-select");
const dashboardMessage = document.querySelector("#dashboard-message");
let patients = [];
let requests = [];
let hospitals = [];
let selectedHospitalId = "";
let refreshVersion = 0;

function showMessage(message) {
    dashboardMessage.textContent = message;
}

async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...options.headers,
        },
    });
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.error || `Request failed (${response.status}).`);
    }
    return payload;
}

function createCell(text, className) {
    const cell = document.createElement("td");
    cell.textContent = text;
    if (className) cell.className = className;
    return cell;
}

function renderPatients() {
    patientsBody.replaceChildren();
    patients.forEach((patient) => {
        const row = document.createElement("tr");
        row.append(createCell(patient.id, "patient-id"));
        row.append(createCell(patient.emergencyType));

        const severityCell = document.createElement("td");
        const severity = document.createElement("span");
        severity.className = `severity ${patient.severity.toLowerCase()}`;
        severity.textContent = patient.severity;
        severityCell.append(severity);
        row.append(severityCell);

        row.append(createCell(`${patient.eta} min`));
        const statusCell = document.createElement("td");
        const status = document.createElement("span");
        status.className = "status-label";
        const dot = document.createElement("span");
        dot.className = "small-status-dot";
        dot.setAttribute("aria-hidden", "true");
        status.append(dot, document.createTextNode(` ${patient.status}`));
        statusCell.append(status);
        row.append(statusCell);
        patientsBody.append(row);
    });
    document.querySelector("#patient-count").textContent =
        `${patients.length} ${patients.length === 1 ? "record" : "records"}`;
}

function updateHospitalContext() {
    const hospital = hospitals.find((item) => item.id === selectedHospitalId);
    if (!hospital) return;
    document.querySelector("#hospital-location").textContent =
        `HOSPITAL OPERATIONS / ${hospital.location.toUpperCase()}`;
    document.querySelector("#hospital-subtitle").textContent =
        `${hospital.name} · ${hospital.location}`;
}

async function loadHospitals() {
    const data = await apiRequest("/api/v1/hospitals");
    hospitals = data.hospitals;
    hospitalSelect.replaceChildren();
    hospitals.forEach((hospital) => {
        const option = document.createElement("option");
        option.value = hospital.id;
        option.textContent = `${hospital.name} · ${hospital.location}`;
        hospitalSelect.append(option);
    });

    const savedHospitalId = localStorage.getItem("hospitalId");
    selectedHospitalId = hospitals.some((item) => item.id === savedHospitalId)
        ? savedHospitalId
        : hospitals[0]?.id ?? "";
    hospitalSelect.value = selectedHospitalId;
    updateHospitalContext();
}

function renderRequestCards(container, items, emptyMessage) {
    container.replaceChildren();
    if (items.length === 0) {
        const emptyState = document.createElement("p");
        emptyState.className = "queue-empty";
        emptyState.textContent = emptyMessage;
        container.append(emptyState);
        return;
    }

    items.forEach((item) => {
        const card = document.createElement("article");
        card.className = `request-card${item.sos ? " request-sos" : ""}`;

        const details = document.createElement("div");
        details.className = "request-details";
        const title = document.createElement("strong");
        title.textContent = `${item.ambulanceId} · ${item.patientId}`;
        const description = document.createElement("span");
        description.textContent =
            `${item.emergencyType} · ${item.severity} · ETA ${item.eta} min`;
        const state = document.createElement("span");
        state.className = "request-state";
        state.textContent = `${item.sos ? "SOS · " : ""}${item.status === "Pending" ? "Awaiting hospital response" : item.status}`;
        details.append(title, description, state);
        card.append(details);

        if (item.status === "Pending") {
            const actions = document.createElement("div");
            actions.className = "request-actions";
            [
                { status: "Received", className: "primary-button", label: "Accept · mark received" },
                { status: "Declined", className: "secondary-button", label: "Decline request" },
            ].forEach((action) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = action.className;
                button.dataset.requestId = item.id;
                button.dataset.status = action.status;
                button.textContent = action.label;
                actions.append(button);
            });
            card.append(actions);
        }
        container.append(card);
    });
}

function renderRequests() {
    const pendingRequests = requests.filter((item) => item.status === "Pending" && !item.sos);
    const pendingSos = requests.filter((item) => item.status === "Pending" && item.sos);
    document.querySelector("#request-count").textContent = `${pendingRequests.length} pending`;
    document.querySelector("#sos-count").textContent = `${pendingSos.length} active`;
    renderRequestCards(
        requestList,
        requests.filter((item) => !item.sos),
        "No ambulance requests received yet.",
    );
    renderRequestCards(
        sosList,
        requests.filter((item) => item.sos),
        "No SOS alerts received.",
    );
}

async function refreshData() {
    if (!selectedHospitalId) return;
    const version = ++refreshVersion;
    const hospitalId = selectedHospitalId;
    const query = `?hospitalId=${encodeURIComponent(hospitalId)}`;
    try {
        const [patientData, requestData] = await Promise.all([
            apiRequest(`/api/v1/patients${query}`),
            apiRequest(`/api/v1/ambulance-requests${query}`),
        ]);
        if (version !== refreshVersion || hospitalId !== selectedHospitalId) return;
        patients = patientData.patients;
        requests = requestData.requests;
        renderPatients();
        renderRequests();
    } catch (error) {
        if (version !== refreshVersion) return;
        showMessage(`Could not load the shared hospital queue: ${error.message}`);
    }
}

function readForm(form) {
    return Object.fromEntries(new FormData(form).entries());
}

hospitalForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = hospitalForm.querySelector("button[type=submit]");
    button.disabled = true;
    try {
        const values = readForm(hospitalForm);
        const result = await apiRequest("/api/v1/hospitals", {
            method: "POST",
            body: JSON.stringify({
                name: values.name.trim(),
                location: values.location.trim(),
            }),
        });
        await loadHospitals();
        selectedHospitalId = result.hospital.id;
        hospitalSelect.value = selectedHospitalId;
        localStorage.setItem("hospitalId", selectedHospitalId);
        updateHospitalContext();
        hospitalForm.reset();
        await refreshData();
        showMessage(`${result.hospital.name} inbox added.`);
    } catch (error) {
        showMessage(`Could not add hospital: ${error.message}`);
    } finally {
        button.disabled = false;
    }
});

hospitalSelect.addEventListener("change", () => {
    selectedHospitalId = hospitalSelect.value;
    localStorage.setItem("hospitalId", selectedHospitalId);
    updateHospitalContext();
    patients = [];
    requests = [];
    renderPatients();
    renderRequests();
    refreshData();
});

async function handleQueueAction(event) {
    const button = event.target.closest("button[data-request-id]");
    if (!button) return;
    button.disabled = true;
    try {
        const result = await apiRequest(
            `/api/v1/ambulance-requests/${encodeURIComponent(button.dataset.requestId)}`,
            {
                method: "PATCH",
                body: JSON.stringify({
                    status: button.dataset.status,
                    hospitalId: selectedHospitalId,
                }),
            },
        );
        await refreshData();
        showMessage(`Request from ${result.request.ambulanceId} marked ${result.request.status.toLowerCase()}.`);
    } catch (error) {
        showMessage(`Could not update request: ${error.message}`);
        await refreshData();
    }
}

requestList.addEventListener("click", handleQueueAction);
sosList.addEventListener("click", handleQueueAction);

loadHospitals()
    .then(refreshData)
    .catch((error) => showMessage(`Could not load hospitals: ${error.message}`));
window.setInterval(refreshData, 4000);
