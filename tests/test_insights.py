import unittest
from unittest.mock import patch
from gotchi_insights import snapshot, trends
from gotchi_mcp import security_status, security_trends


class InsightTests(unittest.TestCase):
    def test_redaction(self):
        data = {
            "status": "running", "mood": "calm", "log_status": "available",
            "health": {"disk_percent": 20, "future_secret": "hidden"},
            "events_24h": {"failed": 1},
            "alerts": [
                {"severity": "high", "category": "ssh",
                 "title": "IP 192.0.2.9 broke in",
                 "detail": "username private data"},
            ],
        }
        with patch("gotchi_insights.overview", return_value=data):
            result = snapshot()
        self.assertNotIn("192.0.2.9", str(result))
        self.assertNotIn("private data", str(result))
        self.assertNotIn("future_secret", str(result))
        self.assertEqual(result["alerts"][0]["title"], "Other security alert")

    def test_window(self):
        for arg in (100, 0, True):
            with self.assertRaises(ValueError):
                trends(arg)

    def test_mcp_functions(self):
        with patch("gotchi_mcp.snapshot", return_value={"status": "running"}):
            self.assertEqual(security_status()["status"], "running")
        with patch("gotchi_mcp.trends", return_value=[]):
            self.assertEqual(security_trends(24), [])
