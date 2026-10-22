import unittest
from unittest.mock import patch
from gotchi_explain import explain

class ExplainTests(unittest.TestCase):
    def test_offline_monitor_rejected(self):
        with patch("gotchi_explain.snapshot", return_value={"status": "stale"}):
            with self.assertRaises(ValueError):
                explain()
    def test_model_validation(self):
        with self.assertRaises(ValueError):
            explain("bad model")
