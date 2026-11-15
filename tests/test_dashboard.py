import unittest

import app


class DashboardApiTests(unittest.TestCase):
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

    def test_dashboard_includes_patient_intake_and_ambulance_acknowledgment(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('id="patient-form"', page)
        self.assertIn('id="ambulance-form"', page)
        self.assertIn('id="sos-button"', page)
        self.assertIn("do not contact a hospital or emergency services", page)

        script_response = app.app.test_client().get("/static/js/script.js")
        script = script_response.get_data(as_text=True)
        script_response.close()
        self.assertIn('"Acknowledge"', script)
        self.assertIn('"Decline"', script)
        self.assertIn("Pending acknowledgment", script)

    def test_dashboard_static_assets_are_served(self):
        client = app.app.test_client()

        for path in ("/static/css/style.css", "/static/js/script.js"):
            response = client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()


if __name__ == "__main__":
    unittest.main()
