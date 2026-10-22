import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from gotchi_auth import create_admin, has_admin, verify_admin
from gotchi_threats import summarize_lines, get_snapshot
from gotchi_webui import app


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"SECURIGOTCHI_DATA_DIR": self.temp.name})
        self.env.start()
        os.chmod(self.temp.name, 0o700)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_single_admin(self):
        self.assertFalse(has_admin())
        create_admin("a secure test passphrase")
        self.assertTrue(verify_admin("admin", "a secure test passphrase"))
        self.assertFalse(verify_admin("admin", "incorrect"))
        with self.assertRaises(ValueError):
            create_admin("another secure passphrase")

    def test_short_password_rejected(self):
        with self.assertRaises(ValueError):
            create_admin("too short")

    def test_unauthenticated_api_blocked(self):
        create_admin("a secure test passphrase")
        client = app.test_client()
        self.assertEqual(client.get("/api/brain").status_code, 401)
        login = client.get("/login")
        self.assertEqual(login.status_code, 200)
        with client.session_transaction() as session:
            csrf = session["csrf"]
        self.assertEqual(client.post("/login", data={
            "csrf": csrf, "username": "admin", "password": "a secure test passphrase"
        }).status_code, 302)
        self.assertEqual(client.post("/api/run_plugin").status_code, 403)
        self.assertEqual(client.post("/api/query", json={"query": "hello"}).status_code, 403)

    def test_bad_host_blocked(self):
        client = app.test_client()
        self.assertEqual(client.get("/", headers={"Host": "evil.example"}).status_code, 403)


class ThreatTests(unittest.TestCase):
    def test_ssh_summary(self):
        lines = [
            "sshd[1]: Failed password for root from 192.0.2.10 port 123 ssh2",
            "sshd[1]: Failed publickey for root from 192.0.2.10 port 123 ssh2",
            "sshd[1]: Invalid user bob from 192.0.2.11 port 125",
            "sshd[1]: Accepted publickey for alice from 192.0.2.12 port 126",
        ]
        summary = summarize_lines(lines)
        self.assertEqual(summary["failed_logins"], 2)
        self.assertEqual(summary["unique_failure_sources"], 1)
        self.assertEqual(summary["successful_logins"], 1)

    def test_readonly_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "auth.log"
            path.write_text("sshd[1]: Failed password for root from 192.0.2.15 port 123 ssh2\n")
            with patch.dict(os.environ, {"SECURIGOTCHI_AUTH_LOG": str(path)}):
                summary = get_snapshot()
            self.assertEqual(summary["status"], "available")
            self.assertEqual(summary["failed_logins"], 1)


if __name__ == "__main__":
    unittest.main()
