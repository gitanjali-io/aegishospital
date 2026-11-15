import os
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
        self.assertIn('id="patient-form"', page)
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

    def test_driver_request_is_shared_and_hospital_can_mark_received(self):
        driver = app.app.test_client()
        hospital = app.app.test_client()
        response = driver.post(
            "/api/v1/ambulance-requests",
            json={
                "ambulanceId": "AMB-104",
                "patientId": "P004",
                "emergencyType": "Road accident",
                "severity": "High",
                "eta": 12,
            },
        )

        self.assertEqual(response.status_code, 201)
        created = response.get_json()["request"]
        self.assertEqual(created["status"], "Pending")
        self.assertFalse(created["sos"])

        received = hospital.get("/api/v1/ambulance-requests").get_json()["requests"]
        self.assertEqual(received[0]["id"], created["id"])
        self.assertEqual(received[0]["patientId"], "P004")

        response = hospital.patch(
            f"/api/v1/ambulance-requests/{created['id']}",
            json={"status": "Received"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["request"]["status"], "Received")
        self.assertEqual(
            hospital.get("/api/v1/patients").get_json()["patients"][0]["status"],
            "Received",
        )

    def test_hospital_can_decline_request_and_sos_is_flagged_critical(self):
        client = app.app.test_client()
        response = client.post(
            "/api/v1/ambulance-requests",
            json={
                "ambulanceId": "AMB-105",
                "patientId": "P005",
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
            json={"status": "Declined"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["request"]["status"], "Declined")

    def test_request_validation_and_duplicate_patient_ids(self):
        client = app.app.test_client()
        invalid = client.post(
            "/api/v1/ambulance-requests",
            json={
                "ambulanceId": "AMB-106",
                "patientId": "P006",
                "emergencyType": "Emergency",
                "severity": "Unknown",
                "eta": True,
            },
        )
        self.assertEqual(invalid.status_code, 400)

        patient = {
            "patientId": "P010",
            "emergencyType": "Triage",
            "severity": "Moderate",
            "eta": 15,
        }
        self.assertEqual(client.post("/api/v1/patients", json=patient).status_code, 201)
        self.assertEqual(client.post("/api/v1/patients", json=patient).status_code, 409)

    def test_dashboard_static_assets_are_served(self):
        client = app.app.test_client()

        for path in ("/static/css/style.css", "/static/js/script.js"):
            response = client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()


if __name__ == "__main__":
    unittest.main()
