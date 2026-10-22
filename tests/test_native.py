import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gotchi_native import (
    NativeBatch, SecurityEvent, parse_windows_xml, parse_journal_json,
    parse_macos_json, selected_source,
)
import gotchi_monitor as monitor


WINDOWS_XML = """<Events xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
<Event><System><EventID>4625</EventID><EventRecordID>42</EventRecordID></System>
<EventData><Data Name="IpAddress">192.0.2.8</Data></EventData></Event>
</Events>"""


class NativeParsingTests(unittest.TestCase):
    def test_windows_xml(self):
        entries = parse_windows_xml(WINDOWS_XML)
        self.assertEqual([(x.key, x.kind, x.ip) for x in entries],
                         [("win:42", "failed", "192.0.2.8")])

    def test_journal(self):
        entries, cursor = parse_journal_json(
            '{"__CURSOR":"c1","MESSAGE":"Failed password for root from 192.0.2.3 port 22"}\n'
        )
        self.assertEqual(cursor, "c1")
        self.assertEqual(entries[0].kind, "failed")

    def test_macos(self):
        entries = parse_macos_json(
            '[{"process":"sshd","timestamp":"2026-10-22","processID":2,'
            '"eventMessage":"Accepted publickey for user from 192.0.2.3 port 22"}]'
        )
        self.assertEqual(entries[0].kind, "accepted")

    def test_selection(self):
        with patch("gotchi_native.platform.system", return_value="Windows"):
            with patch.dict(os.environ, {"SECURIGOTCHI_AUTH_LOG": ""}):
                self.assertEqual(selected_source(), "windows")

    def test_first_poll_skips_backlog_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            os.chmod(folder, 0o700)
            with patch.dict(os.environ, {"SECURIGOTCHI_DATA_DIR": folder}):
                old = NativeBatch("available", "windows-security", (
                    SecurityEvent("win:42", "failed", "192.0.2.1"),), "42")
                new = NativeBatch("available", "windows-security", (
                    SecurityEvent("win:42", "failed", "192.0.2.1"),
                    SecurityEvent("win:43", "failed", "192.0.2.1"),), "43")
                health = {"disk_percent": 20, "memory_percent": 30, "load_avg": None}
                with patch("gotchi_monitor.poll_native", side_effect=[old,new,new]):
                    a = monitor.run_once(now=1000, health=health, source="windows")
                    b = monitor.run_once(now=1010, health=health, source="windows")
                    c = monitor.run_once(now=1020, health=health, source="windows")
                self.assertEqual([a["events_added"], b["events_added"], c["events_added"]], [0,1,0])
