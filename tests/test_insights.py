import unittest
from unittest.mock import patch
from gotchi_insights import snapshot, trends
from gotchi_mcp import security_status, security_trends

class InsightTests(unittest.TestCase):
    def test_redaction(self):
        raw = {"status":"running","mood":"calm","log_status":"available",
               "health":{},"events_24h":{"failed":1},
               "alerts":[{"severity":"warning","category":"ssh",
                          "title":"Login failures","detail":"private data"}]}
        with patch("gotchi_insights.overview",return_value=raw):
            result=snapshot()
        self.assertNotIn("private data",str(result))
    def test_window(self):
        with self.assertRaises(ValueError):
            trends(100)
        with self.assertRaises(ValueError):
            trends(True)
    def test_mcp(self):
        with patch("gotchi_mcp.snapshot",return_value={"status":"running"}):
            self.assertEqual(security_status()["status"],"running")
        with patch("gotchi_mcp.trends",return_value=[]):
            self.assertEqual(security_trends(24),[])
