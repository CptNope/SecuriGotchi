"""Non-destructive SecuriGotchi installation and environment diagnostics.

Usage:
    python gotchi_doctor.py
    python gotchi_doctor.py --json
    python gotchi_doctor.py --probe-ollama --probe-logs

Default checks never connect to a model, run plugins, alter permissions, create
files, or require elevated privileges. Optional probes perform bounded reads
against only local OS security sources or loopback Ollama.
"""
import argparse
from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import time

from gotchi_platform import default_data_dir, describe_platform, ssh_text_log_candidates

ALLOWED_STATUSES = ("pass", "warning", "fail", "not_checked")
MIN_PYTHON = (3, 11)


def check(name, status, message, next_step=""):
    if status not in ALLOWED_STATUSES:
        raise ValueError("Unexpected check status")
    return {"id": name, "status": status, "message": message, "next_step": next_step}


def _data_path():
    configured = os.environ.get("SECURIGOTCHI_DATA_DIR")
    return (Path(configured).expanduser() if configured else default_data_dir()).absolute()


def _private_status(path, directory=False):
    if path.is_symlink():
        return "fail", "Symlinks are not supported for sensitive SecuriGotchi state"
    if not path.exists():
        return "warning", "Not initialized"
    try:
        info = path.stat()
        if directory and not stat.S_ISDIR(info.st_mode):
            return "fail", "Expected a directory"
        if not directory and not stat.S_ISREG(info.st_mode):
            return "fail", "Expected a regular file"
        if os.name != "nt":
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                return "fail", "Ownership or Unix permissions are unsafe"
            return "pass", "Owned by current user, private Unix permissions"
        return "warning", "Exists; Windows ACL privacy was not verified"
    except OSError:
        return "fail", "Unable to inspect permissions"


def _admin_status(path):
    if not path.is_file() or path.is_symlink():
        return False
    try:
        # Read-only sqlite open; does not initialize tables or mutate credentials.
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
            return db.execute("SELECT 1 FROM admins LIMIT 1").fetchone() is not None
    except (sqlite3.Error, OSError, ValueError):
        return False


def _collector_state(path, now):
    if not path.is_file() or path.is_symlink():
        return "not_started"
    try:
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2) as db:
            row = db.execute("SELECT last_poll,log_status FROM monitor_state WHERE id=1").fetchone()
        if row is None:
            return "not_started"
        last_poll, status = row
        if not isinstance(last_poll, int):
            return "unknown"
        if last_poll > now + 60:
            return "clock_mismatch"
        if now - last_poll > 180:
            return "stale"
        return "running" if status == "available" else "limited"
    except (sqlite3.Error, OSError, ValueError):
        return "unknown"


def _local_log_check(probe_logs, family):
    if not probe_logs:
        return check("security_log", "not_checked",
                     "Log access not probed to avoid unnecessary OS log access",
                     "Run with --probe-logs for a bounded, read-only check")
    from gotchi_native import poll_native
    configured = os.environ.get("SECURIGOTCHI_AUTH_LOG")
    if configured:
        paths = (configured,)
    else:
        paths = ssh_text_log_candidates()
    for candidate in paths:
        path = Path(candidate).expanduser()
        try:
            if path.is_file():
                with path.open("rb"):
                    return check("security_log", "pass", "Readable local SSH text log")
        except (OSError, PermissionError):
            pass
    source = {"linux": "journal", "windows": "windows", "macos": "macos"}.get(family)
    if not source:
        return check("security_log", "warning", "No native security-event adapter for this OS")
    batch = poll_native(source)
    if batch.status == "available":
        return check("security_log", "pass", "Native security events are readable (bounded sample)")
    if batch.status == "partial":
        return check("security_log", "warning", "Native event sample reached its limit; events may be missed")
    return check("security_log", "warning", "Native security event source unavailable",
                 "Verify OS logging and current-user read access; do not grant blanket administrator rights")


def _ollama_check(probe):
    if not probe:
        return check("ollama", "not_checked", "Local Ollama has not been contacted",
                     "Run with --probe-ollama to inspect installed local models")
    from gotchi_ai_ops import local_models
    try:
        count = len(local_models())
    except RuntimeError:
        return check("ollama", "warning", "Local Ollama could not be reached",
                     "Start Ollama on 127.0.0.1:11434 or skip optional AI")
    return check("ollama", "pass" if count else "warning",
                 f"Local Ollama reachable; {count} installed model(s)",
                 "Pull a compatible model locally if you want AI incident explanations" if not count else "")


def run_checks(probe_ollama=False, probe_logs=False, now=None):
    """Return machine-readable, bounded results. Never auto-fix system settings."""
    now = int(time.time()) if now is None else int(now)
    platform = describe_platform()
    path = _data_path()
    checks = []
    checks.append(check("python", "pass" if sys.version_info[:2] >= MIN_PYTHON else "fail",
                        f"Python {sys.version_info.major}.{sys.version_info.minor}",
                        "Install Python 3.11+ and rerun python install.py" if sys.version_info[:2] < MIN_PYTHON else ""))
    for name in ("flask", "psutil"):
        present = importlib.util.find_spec(name) is not None
        checks.append(check("dependency_" + name, "pass" if present else "warning",
                            name + (" installed" if present else " unavailable"),
                            "Run python install.py (or use the project's virtualenv)" if not present else ""))

    state, message = _private_status(path, directory=True)
    checks.append(check("data_directory", state, message,
                        "Back up the directory; ensure it is owned by your account and private" if state != "pass" else ""))
    admin_file = path / "auth.sqlite3"
    admin_private, _ = _private_status(admin_file)
    admin_exists = _admin_status(admin_file) if admin_private != "fail" else False
    checks.append(check("local_admin", "pass" if admin_exists and admin_private == "pass" else
                        "fail" if admin_private == "fail" else "warning",
                        "Local administrator configured" if admin_exists else "Local administrator not configured or inaccessible",
                        "Run python gotchi_auth.py init-admin only if no admin exists" if not admin_exists else
                        "Review credentials-file permissions and local OS ACLs" if admin_private != "pass" else ""))
    key_file = path / "flask_signing_key.bin"
    key_status, key_msg = _private_status(key_file)
    checks.append(check("session_key", key_status, key_msg,
                        "Start the dashboard locally to initialize the session key" if key_status == "warning" else
                        "Fix private permissions before running the dashboard" if key_status == "fail" else ""))

    monitor_path = path / "monitor.sqlite3"
    monitor_privacy, _ = _private_status(monitor_path)
    state = _collector_state(monitor_path, now) if monitor_privacy != "fail" else "unknown"
    status = "pass" if state == "running" else "fail" if monitor_privacy == "fail" else "warning"
    checks.append(check("collector", status, "Collector: " + state,
                        "Start python gotchi_monitor.py watch --interval 60 in a separate terminal"
                        if state in ("stale", "not_started") else
                        "Review monitor database access, timestamps, and log permissions" if state != "running" else ""))
    checks.append(_local_log_check(probe_logs, platform["os"]))
    checks.append(_ollama_check(probe_ollama))

    mcp_available = importlib.util.find_spec("mcp") is not None
    checks.append(check("mcp_sdk", "pass" if mcp_available else "warning",
                        "Optional MCP SDK installed" if mcp_available else "Optional MCP SDK not installed",
                        "For trusted local MCP clients, install requirements-mcp.txt" if not mcp_available else ""))
    statuses = {k: sum(c["status"] == k for c in checks) for k in ALLOWED_STATUSES}
    return {
        "version": 1,
        "platform": platform["os"],
        "raspberry_pi": bool(platform.get("raspberry_pi")),
        "checks": checks,
        "summary": statuses,
        "disclaimer": "Read-only best-effort diagnostics are not a security audit.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only SecuriGotchi installation diagnostics")
    parser.add_argument("--json", action="store_true", help="Print machine-readable diagnostics")
    parser.add_argument("--probe-logs", action="store_true", help="Read bounded OS log samples")
    parser.add_argument("--probe-ollama", action="store_true", help="Connect to loopback Ollama (up to 3s)")
    parser.add_argument("--strict", action="store_true", help="Return nonzero for warnings or failures")
    args = parser.parse_args(argv)
    report = run_checks(probe_ollama=args.probe_ollama, probe_logs=args.probe_logs)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("SecuriGotchi Setup Doctor —", report["platform"])
        for item in report["checks"]:
            print(f"  {item['status'].upper():11s} {item['id']}: {item['message']}")
            if item["next_step"]:
                print("    Next:", item["next_step"])
        print("No changes made. Optional security log and Ollama probes are explicit.")
    return 1 if (report["summary"]["fail"] or
                 args.strict and report["summary"]["warning"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
