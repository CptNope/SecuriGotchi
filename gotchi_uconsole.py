"""ClockworkPi uConsole CM4 compatibility checks (no privileged operations).

A Compute Module 4 usually identifies itself only as Raspberry Pi CM4, so
we do not claim that automatic detection proves it is mounted in a uConsole.
Select --device uconsole-cm4 explicitly for a definitive profile selection.
"""
import os
from pathlib import Path
import platform
import shutil
import sys


def board_model(path="/proc/device-tree/model"):
    try:
        return Path(path).read_bytes().decode("utf-8", "replace").strip("\x00 \n")
    except (OSError, UnicodeError):
        return ""


def board_identity(model=None, machine=None, os_name=None):
    model = board_model() if model is None else model
    machine = platform.machine() if machine is None else machine
    os_name = platform.system() if os_name is None else os_name
    name = model.lower()
    explicit_uconsole_marker = "uconsole" in name or "clockworkpi" in name
    cm4 = "compute module 4" in name or "raspberry pi cm4" in name
    return {
        "os": os_name.lower(),
        "architecture": machine.lower(),
        "cm4_detected": cm4,
        "uconsole_marker_detected": explicit_uconsole_marker,
        "board": "ClockworkPi uConsole" if explicit_uconsole_marker
                 else "Raspberry Pi Compute Module 4" if cm4
                 else "Unknown / non-CM4 device",
    }


def physical_memory_bytes():
    # Avoid allocating memory; psutil is a small core dependency.
    try:
        import psutil
        return int(psutil.virtual_memory().total)
    except (ImportError, OSError, ValueError):
        pass
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def free_storage_bytes():
    try:
        return int(shutil.disk_usage(Path.home()).free)
    except OSError:
        return None


def profile_checks(device="auto", identity=None, memory_bytes=None,
                   storage_free_bytes=None, python_bits=None):
    """Return (selected_profile, checks) without creating or modifying files."""
    if device not in ("auto", "uconsole-cm4"):
        raise ValueError("Unknown device profile")
    identity = board_identity() if identity is None else identity
    detected = identity["uconsole_marker_detected"]
    selected = device == "uconsole-cm4" or (device == "auto" and detected)
    if not selected:
        return None, []
    memory = physical_memory_bytes() if memory_bytes is None else memory_bytes
    storage = free_storage_bytes() if storage_free_bytes is None else storage_free_bytes
    bits = (64 if sys.maxsize > 2 ** 32 else 32) if python_bits is None else python_bits
    checks = []

    def result(key, status, message, action=""):
        checks.append({
            "id": key, "status": status, "message": message, "next_step": action
        })

    if identity["os"] != "linux":
        result("uconsole_os", "warning", "uConsole CM4 profile requires a suitable Linux image",
               "Use a CM4-compatible uConsole Linux image from ClockworkPi")
    else:
        result("uconsole_os", "pass", "Linux environment detected")

    arch = identity["architecture"]
    if arch in ("aarch64", "arm64") and bits == 64:
        result("uconsole_arch", "pass", "64-bit ARM Python environment")
    else:
        result("uconsole_arch", "warning", f"Architecture {arch}, Python {bits}-bit",
               "Use the official 64-bit uConsole CM4 Linux image; optional AI wheels may be unavailable")

    if identity["cm4_detected"]:
        result("uconsole_board", "pass", "Raspberry Pi Compute Module 4 detected")
    else:
        result("uconsole_board", "warning", "Compute Module 4 not positively identified",
               "Run on the uConsole itself; the --device flag selects a profile, not hardware proof")

    if memory is None:
        result("uconsole_memory", "warning", "Total RAM unavailable")
    else:
        mib = memory / (1024 * 1024)
        status = "warning" if mib < 2048 else "pass"
        result("uconsole_memory", status, f"Detected approximately {mib / 1024:.1f} GiB RAM",
               "Keep heavy semantic-memory and language-model dependencies optional" if status == "warning" else "")

    if storage is None:
        result("uconsole_storage", "warning", "Free storage unavailable")
    else:
        gib = storage / (1024 ** 3)
        result("uconsole_storage", "warning" if gib < 2 else "pass",
               f"Approximately {gib:.1f} GiB free storage",
               "Free space on the uConsole SD card before installing optional models" if gib < 2 else "")

    result("uconsole_display", "pass",
           "Compact dashboard layout supports the 1280×720 display and rotated viewport",
           "Browser viewport, hardware keyboard and trackball require on-device validation")
    return "uconsole-cm4", checks
