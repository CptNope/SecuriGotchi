"""Non-destructive doctor tests. No live OS logs, network, services or model calls."""
import contextlib
from contextlib import closing
import io
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import gotchi_doctor as doctor


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "securigotchi"
        self.data_patch = patch("gotchi_doctor._data_path", return_value=self.path)
        self.data_patch.start()
        self.platform_patch = patch("gotchi_doctor.describe_platform", return_value={
            "os": "linux", "raspberry_pi": True,
        })
        self.platform_patch.start()

    def tearDown(self):
        self.platform_patch.stop()
        self.data_patch.stop()
        self.temp.cleanup()

    def test_default_is_non_destructive_and_does_not_probe(self):
        with patch("gotchi_doctor._local_log_check", wraps=doctor._local_log_check):
            with patch("gotchi_doctor._ollama_check", wraps=doctor._ollama_check):
                report = doctor.run_checks(now=123456)
        self.assertFalse(self.path.exists())
        ids = {c["id"]: c for c in report["checks"]}
        self.assertEqual(ids["security_log"]["status"], "not_checked")
        self.assertEqual(ids["ollama"]["status"], "not_checked")
        self.assertEqual(ids["collector"]["message"], "Collector: not_started")
        self.assertEqual(report["raspberry_pi"], True)

    def test_existing_admin_and_monitor_are_inspected_readonly(self):
        self.path.mkdir(mode=0o700)
        admin = self.path / "auth.sqlite3"
        with closing(sqlite3.connect(admin)) as conn, conn:
            conn.execute("CREATE TABLE admins (username TEXT)")
            conn.execute("INSERT INTO admins VALUES ('admin')")
        os.chmod(admin, 0o600)
        key = self.path / "flask_signing_key.bin"
        key.write_bytes(b"x" * 32)
        os.chmod(key, 0o600)
        monitor = self.path / "monitor.sqlite3"
        with closing(sqlite3.connect(monitor)) as conn, conn:
            conn.execute("CREATE TABLE monitor_state (id INTEGER,last_poll INTEGER,log_status TEXT)")
            conn.execute("INSERT INTO monitor_state VALUES (1, 1000, 'available')")
        os.chmod(monitor, 0o600)
        report = doctor.run_checks(now=1060)
        ids = {c["id"]: c for c in report["checks"]}
        self.assertEqual(ids["collector"]["message"], "Collector: running")
        self.assertIn("configured", ids["local_admin"]["message"])
        self.assertTrue(admin.is_file())
        self.assertEqual(monitor.stat().st_size > 0, True)

    def test_stale_corrupt_and_future_collector_status(self):
        self.path.mkdir(mode=0o700)
        monitor = self.path / "monitor.sqlite3"
        with contextlib.closing(sqlite3.connect(monitor)) as conn, conn:
            conn.execute("CREATE TABLE monitor_state (id INTEGER,last_poll INTEGER,log_status TEXT)")
            conn.execute("INSERT INTO monitor_state VALUES (1, 1000, 'available')")
        self.assertEqual(doctor._collector_state(monitor, 1200), "stale")
        self.assertEqual(doctor._collector_state(monitor, 900), "clock_mismatch")
        self.assertEqual(doctor._collector_state(self.path / "missing.sqlite3", 1200), "not_started")

    def test_symlink_rejected(self):
        self.path.mkdir(mode=0o700)
        target = self.path / "key"
        target.write_text("test")
        symlink = self.path / "link"
        try:
            symlink.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this environment")
        self.assertEqual(doctor._private_status(symlink)[0], "fail")

    def test_log_probe_with_readable_text_fixture(self):
        self.path.mkdir(mode=0o700)
        log = self.path / "fixture.log"
        log.write_text("synthetic log, no secrets", encoding="utf-8")
        with patch.dict(os.environ, {"SECURIGOTCHI_AUTH_LOG": str(log)}):
            self.assertEqual(doctor._local_log_check(True, "linux")["status"], "pass")

    def test_ollama_probe_is_opt_in(self):
        with patch("gotchi_ai_ops.local_models", return_value=["llama3:8b"]):
            result = doctor._ollama_check(True)
        self.assertIn("1 installed model", result["message"])

    def test_json_output(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = doctor.main(["--json"])
        self.assertEqual(exit_code, 0)
        self.assertIn('"security_log"', output.getvalue())
        self.assertFalse(self.path.exists())

    def test_strict_mode_exit_code(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(doctor.main(["--strict"]), 1)
