"""Platform detection and honest, read-only capability reporting.

The dashboard, memory, and resource measurements are cross-platform.
Native OS event log adapters are not interchangeable and must be separately tested.
"""
import os
from pathlib import Path
import platform
import shutil


def os_family():
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    return "other"


def default_data_dir():
    family = os_family()
    if family == "windows":
        local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        return (Path(local) if local else Path.home() / "AppData" / "Local") / "SecuriGotchi"
    if family == "macos":
        return Path.home() / "Library" / "Application Support" / "SecuriGotchi"
    # Maintain the existing Linux path to preserve Phase 2-4 credentials/state.
    return Path.home() / ".local" / "share" / "securigotchi"


def ssh_text_log_candidates():
    return ("/var/log/auth.log", "/var/log/secure") if os_family() == "linux" else ()


def describe_platform():
    family = os_family()
    imported_log = bool(os.environ.get("SECURIGOTCHI_AUTH_LOG"))
    native_ssh_text = family == "linux"
    return {
        "os": family,
        "raspberry_pi": _is_pi() if native_ssh_text else False,
        "dashboard": "local_only",
        "system_health": "available",
        "ssh_events": (
            "imported_text_log" if imported_log else
            "linux_text_log" if native_ssh_text else "not_implemented"
        ),
        "native_event_logs": "not_implemented" if family in ("windows", "macos") else "not_applicable",
        "notifications": "linux_desktop_optional" if native_ssh_text else "not_implemented",
        "service_generator": "systemd_user_only" if native_ssh_text else "not_implemented",
    }


def _is_pi():
    try:
        model = Path("/proc/device-tree/model").read_bytes().decode("utf-8", "replace")
        return "raspberry pi" in model.lower()
    except (OSError, UnicodeError):
        return False


def system_health():
    """Return portable disk/memory/load measurements; missing data stays None."""
    disk_percent = None
    try:
        disk = shutil.disk_usage(Path.home())
        if disk.total:
            disk_percent = round(disk.used / disk.total * 100, 1)
    except OSError:
        pass

    memory_percent = None
    load_avg = None
    try:
        import psutil
    except ImportError:
        psutil = None

    if psutil is not None:
        try:
            memory_percent = round(psutil.virtual_memory().percent, 1)
        except (OSError, ValueError):
            pass

    try:
        load_avg = round(os.getloadavg()[0], 2)
    except (AttributeError, OSError):
        pass

    return {
        "disk_percent": disk_percent,
        "memory_percent": memory_percent,
        "load_avg": load_avg,
    }
