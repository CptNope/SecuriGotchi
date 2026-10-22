"""No graphical session or privileged systemd daemon required to run these tests."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gotchi_monitor as monitor
import gotchi_notifications as notifications
from gotchi_service import render_unit


class Phase4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.chmod(self.temp.name, 0o700)
        self.env = patch.dict(os.environ, {"SECURIGOTCHI_DATA_DIR": self.temp.name})
        self.env.start()
        self.log = Path(self.temp.name) / "auth.log"
        self.log.write_text("", encoding="utf-8")
        self.health = {"disk_percent": 30, "memory_percent": 25, "load_avg": 0.3}

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _make_alert(self, when, severity):
        with monitor.connect() as conn:
            conn.execute(
                "INSERT INTO alerts(ts,category,severity,title,detail,fingerprint) VALUES (?,?,?,?,?,?)",
                (when, "test", severity, "Test alert", "No private data", str(when)),
            )
            conn.commit()

    def test_notification_opt_in_no_historical_replay(self):
        self._make_alert(100, "high")
        notifications.enable_notifications()
        sent = []
        self.assertEqual(notifications.deliver_pending(sender=lambda level, title: sent.append(level) or True), 0)
        self._make_alert(101, "critical")
        self.assertEqual(notifications.deliver_pending(sender=lambda level, title: sent.append(level) or True), 1)
        self.assertEqual(sent, ["critical"])
        self.assertEqual(notifications.deliver_pending(sender=lambda level, title: True), 0)

    def test_delivery_retry_and_threshold_filter(self):
        notifications.enable_notifications()
        self._make_alert(200, "warning")
        self._make_alert(201, "high")
        self.assertEqual(notifications.deliver_pending(sender=lambda *_: False), 0)
        successes = []
        self.assertEqual(notifications.deliver_pending(sender=lambda s, t: successes.append(s) or True), 1)
        self.assertEqual(successes, ["high"])

    def test_watch_lock_prevents_second_collector(self):
        with monitor.exclusive_watch_lock():
            with self.assertRaises(RuntimeError):
                with monitor.exclusive_watch_lock():
                    pass
        with monitor.exclusive_watch_lock():
            pass

    @unittest.skipIf(os.name == 'nt', 'systemd unit paths are Linux-only')
    def test_systemd_template_is_opt_in_and_no_web(self):
        unit = render_unit(Path("/home/example/SecuriGotchi"), 60, True, "high")
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("--notify --notify-level high", unit)
        self.assertIn("gotchi_monitor.py", unit)
        self.assertNotIn("gotchi_webui.py", unit)
        self.assertIn("WantedBy=default.target", unit)

    def test_invalid_service_configuration_rejected(self):
        with self.assertRaises(ValueError):
            render_unit(Path("/home/me/repo"), interval=1)
        with self.assertRaises(ValueError):
            render_unit(Path("/home/me/repo"), notify_level="unsafe")


if __name__ == "__main__":
    unittest.main()
