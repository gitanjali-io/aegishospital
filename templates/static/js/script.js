document.querySelectorAll(".sidebar nav a").forEach((link) => {
    link.addEventListener("click", () => {
        document.querySelector(".sidebar nav a.active")?.classList.remove("active");
        link.classList.add("active");
    });
});

const patientsBody = document.querySelector("#patients-body");
const requestList = document.querySelector("#request-list");
const patientForm = document.querySelector("#patient-form");
const ambulanceForm = document.querySelector("#ambulance-form");
const dashboardMessage = document.querySelector("#dashboard-message");
let patients = [];
let requests = [];
let refreshInProgress = false;

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

function renderRequests() {
    requestList.replaceChildren();
    const pendingCount = requests.filter((item) => item.status === "Pending").length;
    document.querySelector("#request-count").textContent = `${pendingCount} pending`;

    requests.forEach((item) => {
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
        state.textContent = `${item.sos ? "SOS · " : ""}${item.status}`;
        details.append(title, description, state);
        card.append(details);

        if (item.status === "Pending") {
            const actions = document.createElement("div");
            actions.className = "request-actions";
            [
                { status: "Received", className: "primary-button", label: "Mark received" },
                { status: "Declined", className: "secondary-button", label: "Decline" },
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
        requestList.append(card);
    });
}

async function refreshData() {
    if (refreshInProgress) return;
    refreshInProgress = true;
    try {
        const [patientData, requestData] = await Promise.all([
            apiRequest("/api/v1/patients"),
            apiRequest("/api/v1/ambulance-requests"),
        ]);
        patients = patientData.patients;
        requests = requestData.requests;
        renderPatients();
        renderRequests();
    } catch (error) {
        showMessage(`Could not load the shared hospital queue: ${error.message}`);
    } finally {
        refreshInProgress = false;
    }
}

function readForm(form) {
    return Object.fromEntries(new FormData(form).entries());
}

function getPatientPayload(form) {
    const values = readForm(form);
    return {
        patientId: values.patientId.trim().toUpperCase(),
        emergencyType: values.emergencyType.trim(),
        severity: values.severity,
        eta: Number(values.eta),
    };
}

async function sendAmbulanceRequest(isSos = false) {
    if (!ambulanceForm.reportValidity()) return;
    const values = readForm(ambulanceForm);
    const button = document.querySelector(isSos ? "#sos-button" : "#ambulance-form button[type=submit]");
    button.disabled = true;
    try {
        await apiRequest("/api/v1/ambulance-requests", {
            method: "POST",
            body: JSON.stringify({
                ambulanceId: values.ambulanceId.trim().toUpperCase(),
                ...getPatientPayload(ambulanceForm),
                sos: isSos,
            }),
        });
        ambulanceForm.reset();
        await refreshData();
        showMessage(
            isSos
                ? "Demo SOS received in the shared hospital queue. It did not contact emergency services."
                : "Ambulance request sent to the shared hospital queue.",
        );
    } catch (error) {
        showMessage(`Could not send request: ${error.message}`);
    } finally {
        button.disabled = false;
    }
}

patientForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = patientForm.querySelector("button[type=submit]");
    button.disabled = true;
    try {
        await apiRequest("/api/v1/patients", {
            method: "POST",
            body: JSON.stringify(getPatientPayload(patientForm)),
        });
        patientForm.reset();
        await refreshData();
        showMessage("Patient added to the shared demo register.");
    } catch (error) {
        showMessage(`Could not add patient: ${error.message}`);
    } finally {
        button.disabled = false;
    }
});

ambulanceForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendAmbulanceRequest();
});

document.querySelector("#sos-button").addEventListener("click", () => {
    if (!ambulanceForm.reportValidity()) return;
    if (window.confirm("Send a demo SOS request to the shared hospital queue? This will not contact emergency services.")) {
        sendAmbulanceRequest(true);
    }
});

requestList.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-request-id]");
    if (!button) return;
    button.disabled = true;
    try {
        const result = await apiRequest(
            `/api/v1/ambulance-requests/${encodeURIComponent(button.dataset.requestId)}`,
            {
                method: "PATCH",
                body: JSON.stringify({ status: button.dataset.status }),
            },
        );
        await refreshData();
        showMessage(`Request from ${result.request.ambulanceId} marked ${result.request.status.toLowerCase()}.`);
    } catch (error) {
        showMessage(`Could not update request: ${error.message}`);
        await refreshData();
    }
});

refreshData();
window.setInterval(refreshData, 4000);
