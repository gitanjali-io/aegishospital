import os
import sqlite3
import uuid
from contextlib import contextmanager

from flask import Flask, jsonify, render_template, request

app = Flask(__name__, static_folder="templates/static")
app.config["DATABASE"] = os.environ.get(
    "HOSPITAL_DATABASE",
    os.path.join(app.instance_path, "hospital-demo.sqlite3"),
)

SEVERITIES = {"Critical", "High", "Moderate"}
REQUEST_STATUSES = {"Received", "Declined"}


@contextmanager
def database_connection():
    database_path = app.config["DATABASE"]
    os.makedirs(os.path.dirname(os.path.abspath(database_path)), exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id TEXT PRIMARY KEY,
                emergency_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                eta INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS ambulance_requests (
                id TEXT PRIMARY KEY,
                ambulance_id TEXT NOT NULL,
                patient_id TEXT NOT NULL,
                emergency_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                eta INTEGER NOT NULL,
                is_sos INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        with connection:
            if connection.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
                connection.executemany(
                    """
                    INSERT INTO patients (id, emergency_type, severity, eta, status)
                    VALUES (?, ?, ?, ?, 'Incoming')
                    """,
                    (
                        ("P001", "Cardiac emergency", "Critical", 8),
                        ("P002", "Spinal trauma", "High", 14),
                        ("P003", "Road accident", "Moderate", 21),
                    ),
                )
            demo_cases = (
                ("P201", "Cardiac emergency", "Critical", 6),
                ("P202", "Road accident", "High", 12),
                ("P203", "Urgent assistance", "Critical", 3),
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO patients (id, emergency_type, severity, eta, status)
                VALUES (?, ?, ?, ?, 'Pending')
                """,
                demo_cases,
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO ambulance_requests
                    (id, ambulance_id, patient_id, emergency_type, severity, eta, is_sos)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ("DEMO-REQ-201", "AMB-201", "P201", "Cardiac emergency", "Critical", 6, 0),
                    ("DEMO-REQ-202", "AMB-202", "P202", "Road accident", "High", 12, 0),
                    ("DEMO-REQ-203", "AMB-203", "P203", "Urgent assistance", "Critical", 3, 1),
                ),
            )
        with connection:
            yield connection
    finally:
        connection.close()


def request_payload_error(payload):
    if not isinstance(payload, dict):
        return "A JSON object is required."

    required_fields = ("ambulanceId", "patientId", "emergencyType", "severity", "eta")
    if any(not isinstance(payload.get(field), str) or not payload[field].strip() for field in required_fields[:4]):
        return "Ambulance ID, patient ID, emergency type, and severity are required."

    if any(len(payload[field].strip()) > limit for field, limit in (
        ("ambulanceId", 20),
        ("patientId", 20),
        ("emergencyType", 80),
    )):
        return "One or more text fields exceed the allowed length."

    if payload["severity"] not in SEVERITIES:
        return "Severity must be Critical, High, or Moderate."

    eta = payload.get("eta")
    if isinstance(eta, bool) or not isinstance(eta, int) or not 0 <= eta <= 999:
        return "ETA must be a whole number between 0 and 999 minutes."

    if "sos" in payload and not isinstance(payload["sos"], bool):
        return "SOS must be true or false."

    return None


def patient_json(row):
    return {
        "id": row["id"],
        "emergencyType": row["emergency_type"],
        "severity": row["severity"],
        "eta": row["eta"],
        "status": row["status"],
    }


def request_json(row):
    return {
        "id": row["id"],
        "ambulanceId": row["ambulance_id"],
        "patientId": row["patient_id"],
        "emergencyType": row["emergency_type"],
        "severity": row["severity"],
        "eta": row["eta"],
        "sos": bool(row["is_sos"]),
        "status": row["status"],
        "createdAt": row["created_at"],
    }


@app.get("/")
def hospital_dashboard():
    return render_template('hospital.html')


@app.get("/api/v1/dashboard")
def dashboard_data():
    location = os.environ.get("HOSPITAL_LOCATION", "Bengaluru, India")
    return jsonify({
        "api_version": "1.0",
        "status": "demo",
        "location": {"name": location},
        "notice": (
            "Operational figures shown in the dashboard are illustrative demo data. "
            "Connect an authorized hospital system for live data."
        ),
    })


@app.get("/api/v1/patients")
def list_patients():
    with database_connection() as connection:
        rows = connection.execute(
            "SELECT id, emergency_type, severity, eta, status FROM patients ORDER BY created_at DESC, rowid DESC"
        ).fetchall()
    return jsonify({"patients": [patient_json(row) for row in rows]})


@app.post("/api/v1/patients")
def create_patient():
    if not request.is_json:
        return jsonify({"error": "A JSON request body is required."}), 415
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON object is required."}), 400

    patient_id = payload.get("patientId")
    emergency_type = payload.get("emergencyType")
    severity = payload.get("severity")
    eta = payload.get("eta")
    if not isinstance(patient_id, str) or not patient_id.strip() or len(patient_id.strip()) > 20:
        return jsonify({"error": "Patient ID is required and must be at most 20 characters."}), 400
    if not isinstance(emergency_type, str) or not emergency_type.strip() or len(emergency_type.strip()) > 80:
        return jsonify({"error": "Emergency type is required and must be at most 80 characters."}), 400
    if severity not in SEVERITIES:
        return jsonify({"error": "Severity must be Critical, High, or Moderate."}), 400
    if isinstance(eta, bool) or not isinstance(eta, int) or not 0 <= eta <= 999:
        return jsonify({"error": "ETA must be a whole number between 0 and 999 minutes."}), 400

    patient_id = patient_id.strip().upper()
    try:
        with database_connection() as connection:
            connection.execute(
                "INSERT INTO patients (id, emergency_type, severity, eta, status) VALUES (?, ?, ?, ?, 'Incoming')",
                (patient_id, emergency_type.strip(), severity, eta),
            )
            row = connection.execute(
                "SELECT id, emergency_type, severity, eta, status FROM patients WHERE id = ?",
                (patient_id,),
            ).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"error": "That patient ID already exists."}), 409
    return jsonify({"patient": patient_json(row)}), 201


@app.get("/api/v1/ambulance-requests")
def list_ambulance_requests():
    with database_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM ambulance_requests ORDER BY created_at DESC, rowid DESC"
        ).fetchall()
    return jsonify({"requests": [request_json(row) for row in rows]})


@app.post("/api/v1/ambulance-requests")
def create_ambulance_request():
    if not request.is_json:
        return jsonify({"error": "A JSON request body is required."}), 415
    payload = request.get_json(silent=True)
    error = request_payload_error(payload)
    if error:
        return jsonify({"error": error}), 400

    ambulance_id = payload["ambulanceId"].strip().upper()
    patient_id = payload["patientId"].strip().upper()
    emergency_type = payload["emergencyType"].strip()
    is_sos = payload.get("sos", False)
    severity = "Critical" if is_sos else payload["severity"]
    request_id = str(uuid.uuid4())
    try:
        with database_connection() as connection:
            connection.execute(
                """
                INSERT INTO patients (id, emergency_type, severity, eta, status)
                VALUES (?, ?, ?, ?, 'Pending')
                ON CONFLICT(id) DO UPDATE SET
                    emergency_type = excluded.emergency_type,
                    severity = excluded.severity,
                    eta = excluded.eta,
                    status = 'Pending'
                """,
                (patient_id, emergency_type, severity, payload["eta"]),
            )
            connection.execute(
                """
                INSERT INTO ambulance_requests
                    (id, ambulance_id, patient_id, emergency_type, severity, eta, is_sos)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    ambulance_id,
                    patient_id,
                    emergency_type,
                    severity,
                    payload["eta"],
                    int(is_sos),
                ),
            )
            row = connection.execute(
                "SELECT * FROM ambulance_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
    except sqlite3.Error:
        app.logger.exception("Could not save an ambulance request")
        return jsonify({"error": "The request could not be saved. Please try again."}), 500
    return jsonify({"request": request_json(row)}), 201


@app.patch("/api/v1/ambulance-requests/<request_id>")
def update_ambulance_request(request_id):
    if not request.is_json:
        return jsonify({"error": "A JSON request body is required."}), 415
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("status") not in REQUEST_STATUSES:
        return jsonify({"error": "Status must be Received or Declined."}), 400

    with database_connection() as connection:
        cursor = connection.execute(
            "UPDATE ambulance_requests SET status = ? WHERE id = ? AND status = 'Pending'",
            (payload["status"], request_id),
        )
        if cursor.rowcount == 0:
            exists = connection.execute(
                "SELECT status FROM ambulance_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
            if exists is None:
                return jsonify({"error": "Ambulance request not found."}), 404
            return jsonify({"error": "This request has already been answered."}), 409

        request_row = connection.execute(
            "SELECT * FROM ambulance_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        connection.execute(
            "UPDATE patients SET status = ? WHERE id = ?",
            (payload["status"], request_row["patient_id"]),
        )
    return jsonify({"request": request_json(request_row)})


if __name__ == '__main__':
    app.run(debug=os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"})