import unittest
from unittest.mock import patch
from gotchi_webui import app


class WebTests(unittest.TestCase):
    def setUp(self):
        self.admin = patch("gotchi_webui.has_admin", return_value=True)
        self.admin.start()
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess["admin"] = "admin"
            sess["csrf"] = "test-csrf-token"

    def tearDown(self):
        self.admin.stop()

    def test_browser_plugins_disabled(self):
        response = self.client.post("/api/run_plugin", json={"plugin": "Nmap Top Ports"})
        self.assertEqual(response.status_code, 403)

    def test_bad_query_rejected(self):
        self.assertEqual(self.client.post("/api/query", json={}, headers={"X-CSRF-Token": "test-csrf-token"}).status_code, 400)
        self.assertEqual(self.client.post("/api/query", json={"query": " "}, headers={"X-CSRF-Token": "test-csrf-token"}).status_code, 400)

    def test_query_result_shape(self):
        with patch("gotchi_query.get_results", return_value=["Local SSH audit"]):
            response = self.client.post("/api/query", json={"query": "SSH"}, headers={"X-CSRF-Token": "test-csrf-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [{"content": "Local SSH audit"}])

    def test_security_headers(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
