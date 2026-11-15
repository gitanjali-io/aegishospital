import os
import sqlite3
import tempfile
import unittest

import app


class DashboardApiTests(unittest.TestCase):
    def setUp(self):
        self.database_directory = tempfile.TemporaryDirectory()
        app.app.config["DATABASE"] = os.path.join(self.database_directory.name, "test.sqlite3")

    def tearDown(self):
        self.database_directory.cleanup()

    def test_api_identifies_demo_data_without_external_data_sources(self):
        response = app.app.test_client().get("/api/v1/dashboard")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["api_version"], "1.0")
        self.assertEqual(payload["status"], "demo")
        self.assertEqual(payload["location"]["name"], "Bengaluru, India")
        self.assertNotIn("sources", payload)
        self.assertNotIn("weather", payload)
        self.assertIn("illustrative demo data", payload["notice"])

    def test_dashboard_has_no_environmental_data_panel(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True).lower()
        self.assertNotIn("air quality", page)
        self.assertNotIn("weather", page)
        self.assertNotIn("open-meteo", page)
        self.assertNotIn("pm2.5", page)
        self.assertIn("operations snapshot", page)

    def test_dashboard_is_hospital_receiver_not_ambulance_request_sender(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertNotIn('id="patient-form"', page)
        self.assertIn("Patient details are added when an ambulance request is received", page)
        self.assertIn('id="request-list"', page)
        self.assertIn('id="sos-list"', page)
        self.assertIn("Incoming ambulance requests", page)
        self.assertIn("Urgent driver alerts", page)
        self.assertNotIn('id="ambulance-form"', page)
        self.assertNotIn('id="sos-button"', page)
        self.assertNotIn("Send request to hospital", page)
        self.assertIn("does not contact emergency services", page)

        script_response = app.app.test_client().get("/static/js/script.js")
        script = script_response.get_data(as_text=True)
        script_response.close()
        self.assertIn("Accept · mark received", script)
        self.assertIn("Declined", script)
        self.assertIn("/api/v1/ambulance-requests", script)
        self.assertIn("window.setInterval(refreshData, 4000)", script)
        self.assertNotIn("sendAmbulanceRequest", script)
        self.assertNotIn("#sos-button", script)

    def test_hospital_list_includes_multiple_destinations(self):
        response = app.app.test_client().get("/api/v1/hospitals")

        self.assertEqual(response.status_code, 200)
        hospitals = response.get_json()["hospitals"]
        self.assertGreaterEqual(len(hospitals), 4)
        self.assertIn("bengaluru-north", {hospital["id"] for hospital in hospitals})

        created = app.app.test_client().post(
            "/api/v1/hospitals",
            json={"name": "Demo East Hospital", "location": "Bengaluru East"},
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["hospital"]["name"], "Demo East Hospital")

    def test_existing_database_is_migrated_into_hospital_scoped_tables(self):
        database_path = app.app.config["DATABASE"]
        connection = sqlite3.connect(database_path)
        connection.executescript(
            """
            CREATE TABLE patients (
                id TEXT PRIMARY KEY,
                emergency_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                eta INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO patients (id, emergency_type, severity, eta, status)
            VALUES ('LEGACY-1', 'Demo case', 'High', 9, 'Incoming');
            CREATE TABLE ambulance_requests (
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
            INSERT INTO ambulance_requests
                (id, ambulance_id, patient_id, emergency_type, severity, eta)
            VALUES ('LEGACY-REQ', 'AMB-OLD', 'LEGACY-1', 'Demo case', 'High', 9);
            """
        )
        connection.close()

        client = app.app.test_client()
        patients = client.get(
            "/api/v1/patients?hospitalId=bengaluru-central"
        ).get_json()["patients"]
        requests = client.get(
            "/api/v1/ambulance-requests?hospitalId=bengaluru-central"
        ).get_json()["requests"]
        self.assertIn("LEGACY-1", {patient["id"] for patient in patients})
        legacy_request = next(item for item in requests if item["id"] == "LEGACY-REQ")
        self.assertEqual(legacy_request["hospitalId"], "bengaluru-central")

    def test_hospital_queue_has_fictional_pending_requests_and_sos_example(self):
        client = app.app.test_client()
        demo_requests = {}
        for hospital_id in ("bengaluru-central", "bengaluru-north", "bengaluru-south", "mysuru-general"):
            requests = client.get(
                f"/api/v1/ambulance-requests?hospitalId={hospital_id}"
            ).get_json()["requests"]
            demo_requests.update({item["id"]: item for item in requests})

        self.assertEqual(demo_requests["DEMO-REQ-201"]["hospitalId"], "bengaluru-north")
        self.assertEqual(demo_requests["DEMO-REQ-202"]["hospitalId"], "bengaluru-central")
        self.assertEqual(demo_requests["DEMO-REQ-203"]["hospitalId"], "bengaluru-south")
        self.assertEqual(demo_requests["DEMO-REQ-204"]["hospitalId"], "mysuru-general")
        self.assertTrue(demo_requests["DEMO-REQ-203"]["sos"])

    def test_driver_request_is_shared_and_hospital_can_mark_received(self):
        driver = app.app.test_client()
        hospital = app.app.test_client()
        response = driver.post(
            "/api/v1/ambulance-requests",
            json={
                "ambulanceId": "AMB-104",
                "patientId": "P004",
                "hospitalId": "bengaluru-north",
                "emergencyType": "Road accident",
                "severity": "High",
                "eta": 12,
            },
        )

        self.assertEqual(response.status_code, 201)
        created = response.get_json()["request"]
        self.assertEqual(created["status"], "Pending")
        self.assertFalse(created["sos"])

        received = hospital.get(
            "/api/v1/ambulance-requests?hospitalId=bengaluru-north"
        ).get_json()["requests"]
        self.assertEqual(received[0]["id"], created["id"])
        self.assertEqual(received[0]["patientId"], "P004")
        other_hospital_requests = hospital.get(
            "/api/v1/ambulance-requests?hospitalId=bengaluru-central"
        ).get_json()["requests"]
        self.assertNotIn(created["id"], {item["id"] for item in other_hospital_requests})

        wrong_hospital_response = hospital.patch(
            f"/api/v1/ambulance-requests/{created['id']}",
            json={"status": "Declined", "hospitalId": "bengaluru-central"},
        )
        self.assertEqual(wrong_hospital_response.status_code, 404)

        response = hospital.patch(
            f"/api/v1/ambulance-requests/{created['id']}",
            json={"status": "Received", "hospitalId": "bengaluru-north"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["request"]["status"], "Received")
        self.assertEqual(
            hospital.get(
                "/api/v1/patients?hospitalId=bengaluru-north"
            ).get_json()["patients"][0]["status"],
            "Received",
        )

    def test_hospital_can_decline_request_and_sos_is_flagged_critical(self):
        client = app.app.test_client()
        response = client.post(
            "/api/v1/ambulance-requests",
            json={
                "ambulanceId": "AMB-105",
                "patientId": "P005",
                "hospitalId": "bengaluru-central",
                "emergencyType": "Urgent assistance",
                "severity": "Moderate",
                "eta": 3,
                "sos": True,
            },
        )
        created = response.get_json()["request"]
        self.assertEqual(response.status_code, 201)
        self.assertTrue(created["sos"])
        self.assertEqual(created["severity"], "Critical")

        response = client.patch(
            f"/api/v1/ambulance-requests/{created['id']}",
            json={"status": "Declined", "hospitalId": "bengaluru-central"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["request"]["status"], "Declined")

    def test_request_validation_and_patient_ids_are_scoped_to_hospital(self):
        client = app.app.test_client()
        invalid = client.post(
            "/api/v1/ambulance-requests",
            json={
                "ambulanceId": "AMB-106",
                "patientId": "P006",
                "hospitalId": "bengaluru-central",
                "emergencyType": "Emergency",
                "severity": "Unknown",
                "eta": True,
            },
        )
        self.assertEqual(invalid.status_code, 400)

        patient = {
            "patientId": "P010",
            "hospitalId": "bengaluru-central",
            "emergencyType": "Triage",
            "severity": "Moderate",
            "eta": 15,
        }
        self.assertEqual(client.post("/api/v1/patients", json=patient).status_code, 201)
        self.assertEqual(client.post("/api/v1/patients", json=patient).status_code, 409)

        patient["hospitalId"] = "bengaluru-south"
        self.assertEqual(client.post("/api/v1/patients", json=patient).status_code, 201)
        central_patients = client.get(
            "/api/v1/patients?hospitalId=bengaluru-central"
        ).get_json()["patients"]
        south_patients = client.get(
            "/api/v1/patients?hospitalId=bengaluru-south"
        ).get_json()["patients"]
        self.assertIn("P010", {item["id"] for item in central_patients})
        self.assertIn("P010", {item["id"] for item in south_patients})

    def test_dashboard_static_assets_are_served(self):
        client = app.app.test_client()

        for path in ("/static/css/style.css", "/static/js/script.js"):
            response = client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()


if __name__ == "__main__":
    unittest.main()
