document.querySelectorAll(".sidebar nav a").forEach((link) => {
    link.addEventListener("click", () => {
        document.querySelector(".sidebar nav a.active")?.classList.remove("active");
        link.classList.add("active");
    });
});

const patients = [
    { id: "P001", emergencyType: "Cardiac emergency", severity: "Critical", eta: 8, status: "Incoming" },
    { id: "P002", emergencyType: "Spinal trauma", severity: "High", eta: 14, status: "Incoming" },
    { id: "P003", emergencyType: "Road accident", severity: "Moderate", eta: 21, status: "Incoming" },
];
const requests = [];
const patientForm = document.querySelector("#patient-form");
const ambulanceForm = document.querySelector("#ambulance-form");
const patientsBody = document.querySelector("#patients-body");
const requestList = document.querySelector("#request-list");
const dashboardMessage = document.querySelector("#dashboard-message");

function showMessage(message) {
    dashboardMessage.textContent = message;
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
    const pendingCount = requests.filter((request) => request.status === "Pending acknowledgment").length;
    document.querySelector("#request-count").textContent = `${pendingCount} pending`;

    requests.forEach((request) => {
        const card = document.createElement("article");
        card.className = `request-card${request.sos ? " request-sos" : ""}`;

        const details = document.createElement("div");
        details.className = "request-details";
        const title = document.createElement("strong");
        title.textContent = `${request.ambulanceId} · ${request.patientId}`;
        const description = document.createElement("span");
        description.textContent =
            `${request.emergencyType} · ${request.severity} · ETA ${request.eta} min`;
        const state = document.createElement("span");
        state.className = "request-state";
        state.textContent = `${request.sos ? "SOS · " : ""}${request.status}`;
        details.append(title, description, state);
        card.append(details);

        if (request.status === "Pending acknowledgment") {
            const actions = document.createElement("div");
            actions.className = "request-actions";
            ["acknowledge", "decline"].forEach((action) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = action === "acknowledge" ? "primary-button" : "secondary-button";
                button.dataset.requestId = request.id;
                button.dataset.action = action;
                button.textContent = action === "acknowledge" ? "Acknowledge" : "Decline";
                actions.append(button);
            });
            card.append(actions);
        }
        requestList.append(card);
    });
}

function readForm(form) {
    return Object.fromEntries(new FormData(form).entries());
}

function addRequest(form, isSos = false) {
    if (!form.reportValidity()) return;
    const values = readForm(form);
    const patientId = values.patientId.trim().toUpperCase();
    const ambulanceId = values.ambulanceId.trim().toUpperCase();
    const existingPatient = patients.find((patient) => patient.id === patientId);
    const patientDetails = {
        id: patientId,
        emergencyType: values.emergencyType.trim(),
        severity: isSos ? "Critical" : values.severity,
        eta: Number(values.eta),
        status: "Pending acknowledgment",
    };

    if (existingPatient) Object.assign(existingPatient, patientDetails);
    else patients.unshift(patientDetails);

    requests.unshift({
        id: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${requests.length}`,
        ambulanceId,
        patientId,
        emergencyType: patientDetails.emergencyType,
        severity: patientDetails.severity,
        eta: patientDetails.eta,
        status: "Pending acknowledgment",
        sos: isSos,
    });
    renderPatients();
    renderRequests();
    showMessage(isSos ? "SOS request added to the demo acknowledgment queue." : "Ambulance request added to the demo acknowledgment queue.");
    form.reset();
}

patientForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const values = readForm(patientForm);
    const patientId = values.patientId.trim().toUpperCase();
    if (patients.some((patient) => patient.id === patientId)) {
        showMessage(`Patient ID ${patientId} already exists. Use a unique ID.`);
        patientForm.elements.patientId.focus();
        return;
    }

    patients.unshift({
        id: patientId,
        emergencyType: values.emergencyType.trim(),
        severity: values.severity,
        eta: Number(values.eta),
        status: "Incoming",
    });
    renderPatients();
    showMessage(`Demo patient ${patientId} added.`);
    patientForm.reset();
});

ambulanceForm.addEventListener("submit", (event) => {
    event.preventDefault();
    addRequest(ambulanceForm);
});

document.querySelector("#sos-button").addEventListener("click", () => {
    if (!ambulanceForm.reportValidity()) return;
    if (window.confirm("Send a demo SOS request to the on-screen acknowledgment queue? This will not contact emergency services.")) {
        addRequest(ambulanceForm, true);
    }
});

requestList.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-request-id]");
    if (!button) return;
    const request = requests.find((item) => item.id === button.dataset.requestId);
    if (!request || request.status !== "Pending acknowledgment") return;

    request.status = button.dataset.action === "acknowledge" ? "Acknowledged" : "Declined";
    const patient = patients.find((item) => item.id === request.patientId);
    if (patient) patient.status = request.status;
    renderPatients();
    renderRequests();
    showMessage(`Request from ${request.ambulanceId} ${request.status.toLowerCase()}.`);
});

renderPatients();
renderRequests();
