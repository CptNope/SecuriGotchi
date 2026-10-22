"""uConsole CM4 hardware-profile tests. No real Pi hardware or IO required."""
import contextlib
import io
from unittest.mock import patch
import unittest

from gotchi_uconsole import board_identity, profile_checks
import gotchi_doctor


class UconsoleProfileTests(unittest.TestCase):
    def test_generic_cm4_does_not_imply_uconsole_chassis(self):
        board = board_identity("Raspberry Pi Compute Module 4 Rev 1.1", "aarch64", "Linux")
        self.assertTrue(board["cm4_detected"])
        self.assertFalse(board["uconsole_marker_detected"])
        selected, items = profile_checks("auto", identity=board)
        self.assertIsNone(selected)
        self.assertEqual(items, [])

    def test_explicit_profile_on_64bit_cm4(self):
        board = board_identity("Raspberry Pi Compute Module 4 Rev 1.1", "aarch64", "Linux")
        profile, checks = profile_checks("uconsole-cm4", identity=board,
                                         memory_bytes=4 * 1024**3,
                                         storage_free_bytes=8 * 1024**3,
                                         python_bits=64)
        self.assertEqual(profile, "uconsole-cm4")
        by_id = {item["id"]: item for item in checks}
        for key in ("uconsole_os", "uconsole_arch", "uconsole_board",
                    "uconsole_memory", "uconsole_storage", "uconsole_display"):
            self.assertEqual(by_id[key]["status"], "pass", key)

    def test_32bit_and_limited_storage_are_warned_not_falsely_supported(self):
        board = board_identity("Raspberry Pi Compute Module 4", "armv7l", "Linux")
        _, checks = profile_checks("uconsole-cm4", identity=board,
                                   memory_bytes=1024**3,
                                   storage_free_bytes=1024**3,
                                   python_bits=32)
        by_id = {item["id"]: item for item in checks}
        self.assertEqual(by_id["uconsole_arch"]["status"], "warning")
        self.assertEqual(by_id["uconsole_memory"]["status"], "warning")
        self.assertEqual(by_id["uconsole_storage"]["status"], "warning")

    def test_explicit_profile_does_not_falsify_hardware_identity(self):
        board = board_identity("Generic x86_64", "x86_64", "Linux")
        _, checks = profile_checks("uconsole-cm4", identity=board,
                                   memory_bytes=8 * 1024**3,
                                   storage_free_bytes=8 * 1024**3,
                                   python_bits=64)
        by_id = {item["id"]: item for item in checks}
        self.assertEqual(by_id["uconsole_board"]["status"], "warning")
        self.assertEqual(by_id["uconsole_arch"]["status"], "warning")

    def test_explicit_marker_auto_enables_profile(self):
        board = board_identity("ClockworkPi uConsole CM4", "aarch64", "Linux")
        profile, _ = profile_checks("auto", identity=board,
                                    memory_bytes=4 * 1024**3,
                                    storage_free_bytes=4 * 1024**3,
                                    python_bits=64)
        self.assertEqual(profile, "uconsole-cm4")

    def test_doctor_json_reports_uconsole_profile_without_writing_files(self):
        board = board_identity("Raspberry Pi Compute Module 4", "aarch64", "Linux")
        with patch("gotchi_uconsole.board_identity", return_value=board):
            with patch("gotchi_uconsole.physical_memory_bytes", return_value=4 * 1024**3):
                with patch("gotchi_uconsole.free_storage_bytes", return_value=8 * 1024**3):
                    with patch("gotchi_doctor._data_path") as path:
                        from pathlib import Path
                        path.return_value = Path("/path/that/does/not/exist/securigotchi")
                        output = io.StringIO()
                        with contextlib.redirect_stdout(output):
                            code = gotchi_doctor.main(["--json", "--device", "uconsole-cm4"])
        self.assertEqual(code, 0)
        self.assertIn('"device_profile": "uconsole-cm4"', output.getvalue())
        self.assertIn('"uconsole_board"', output.getvalue())

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            profile_checks("uconsole-a06")
