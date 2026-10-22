"""Monitor tests use temp stores and synthetic log lines; never run real scans."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gotchi_monitor as monitor


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.chmod(self.tmp.name, 0o700)
        self.log = Path(self.tmp.name) / "auth.log"
        self.log.write_text("", encoding="utf-8")
        self.env = patch.dict(os.environ, {"SECURIGOTCHI_DATA_DIR": self.tmp.name})
        self.env.start()
        self.health = {"disk_percent": 30, "memory_percent": 40, "load_avg": 0.2}

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_restart_cursor_and_incremental_detection(self):
        monitor.run_once(now=1000, log_path=str(self.log), health=self.health)
        self.log.write_text("old sshd[1]: Failed password for root from 192.0.2.4 port 123 ssh2\n")
        result = monitor.run_once(now=1010, log_path=str(self.log), health=self.health)
        self.assertEqual(result["events_added"], 1)
        self.assertEqual(monitor.run_once(now=1020, log_path=str(self.log), health=self.health)["events_added"], 0)
        self.assertEqual(monitor.overview(now=1020)["events_24h"]["failed"], 1)

    def test_alert_deduplication_and_escalation(self):
        monitor.run_once(now=1000, log_path=str(self.log), health=self.health)
        lines = ["sshd[2]: Failed password for root from 192.0.2.10 port 22 ssh2\n"] * 5
        with self.log.open("a") as stream:
            stream.writelines(lines)
        monitor.run_once(now=1010, log_path=str(self.log), health=self.health)
        self.assertEqual(len(monitor.overview(now=1010)["alerts"]), 1)
        with self.log.open("a") as stream:
            stream.writelines(lines)
        monitor.run_once(now=1020, log_path=str(self.log), health=self.health)
        alerts = monitor.overview(now=1020)["alerts"]
        self.assertEqual(len(alerts), 2)
        self.assertEqual(alerts[0]["severity"], "critical")
        self.assertEqual(monitor.overview(now=1020)["mood"], "critical")

    def test_partial_line_replayed_once(self):
        monitor.run_once(now=1000, log_path=str(self.log), health=self.health)
        with self.log.open("a") as stream:
            stream.write("sshd[1]: Failed password for root from 192.0.2.5")
        self.assertEqual(monitor.run_once(now=1001, log_path=str(self.log), health=self.health)["events_added"], 0)
        with self.log.open("a") as stream:
            stream.write(" port 22 ssh2\n")
        self.assertEqual(monitor.run_once(now=1002, log_path=str(self.log), health=self.health)["events_added"], 1)

    def test_unavailable_log_and_health_alert(self):
        result = monitor.run_once(now=2000, log_path=str(self.log)+"missing",
                                  health={"disk_percent": 98, "memory_percent": 35, "load_avg": 1})
        self.assertEqual(result["log_status"], "unavailable")
        self.assertEqual(monitor.overview(now=2000)["alerts"][0]["severity"], "critical")

    def test_stale_collector(self):
        monitor.run_once(now=1000, log_path=str(self.log), health=self.health)
        self.assertEqual(monitor.overview(now=1500)["mood"], "sleeping")


if __name__ == "__main__":
    unittest.main()
