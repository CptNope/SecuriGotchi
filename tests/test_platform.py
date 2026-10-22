import os
from pathlib import Path
import unittest
from unittest.mock import patch
import gotchi_platform as platform_info
from install import venv_python


class PlatformTests(unittest.TestCase):
    def test_windows_data_directory(self):
        with patch("gotchi_platform.platform.system", return_value="Windows"):
            with patch.dict(os.environ, {"LOCALAPPDATA": "C:/Users/test/AppData/Local"}):
                self.assertEqual(platform_info.os_family(), "windows")
                self.assertIn("SecuriGotchi", str(platform_info.default_data_dir()))
                self.assertEqual(platform_info.describe_platform()["native_event_logs"], "not_implemented")
                self.assertEqual(platform_info.ssh_text_log_candidates(), ())

    def test_macos_data_directory(self):
        with patch("gotchi_platform.platform.system", return_value="Darwin"):
            self.assertEqual(platform_info.os_family(), "macos")
            self.assertIn("Application Support", str(platform_info.default_data_dir()))
            self.assertEqual(platform_info.describe_platform()["native_event_logs"], "not_implemented")

    def test_linux_capabilities(self):
        with patch("gotchi_platform.platform.system", return_value="Linux"):
            with patch.dict(os.environ, {"SECURIGOTCHI_AUTH_LOG": ""}):
                self.assertEqual(platform_info.describe_platform()["ssh_events"], "linux_text_log")

    def test_venv_python_paths(self):
        self.assertEqual(venv_python(Path("project"), windows=True), Path("project/.venv/Scripts/python.exe"))
        self.assertEqual(venv_python(Path("project"), windows=False), Path("project/.venv/bin/python"))

    def test_health_shape(self):
        self.assertEqual(set(platform_info.system_health()), {"disk_percent", "memory_percent", "load_avg"})


if __name__ == "__main__":
    unittest.main()
