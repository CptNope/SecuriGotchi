"""Read-only SSH authentication log snapshot (no privileges or commands required)."""
from collections import Counter
import ipaddress
import os
from pathlib import Path
import re

MAX_TAIL_BYTES = 1024 * 1024
SOURCE_RE = re.compile(r"\bfrom\s+([0-9A-Fa-f:.]+)(?:\s|$)")
from gotchi_platform import ssh_text_log_candidates
DEFAULT_LOGS = ssh_text_log_candidates()


def _source_ip(line):
    match = SOURCE_RE.search(line)
    if not match:
        return None
    try:
        return str(ipaddress.ip_address(match.group(1)))
    except ValueError:
        return None


def _read_tail(path):
    with path.open("rb") as handle:
        size = handle.seek(0, os.SEEK_END)
        start = max(0, size - MAX_TAIL_BYTES)
        handle.seek(start)
        raw = handle.read(MAX_TAIL_BYTES)
    if start:
        raw = raw.partition(b"\n")[2]
    return raw.decode("utf-8", errors="replace").splitlines()


def summarize_lines(lines):
    """Return bounded counts, not raw auth log entries or usernames."""
    failed = 0
    invalid = 0
    accepted = 0
    sources = Counter()
    for line in lines:
        if "sshd" not in line:
            continue
        if "Failed password" in line or "Failed publickey" in line:
            failed += 1
            ip = _source_ip(line)
            if ip:
                sources[ip] += 1
        if "Invalid user" in line:
            invalid += 1
        if "Accepted password" in line or "Accepted publickey" in line:
            accepted += 1
    return {
        "failed_logins": failed,
        "invalid_user_events": invalid,
        "successful_logins": accepted,
        "unique_failure_sources": len(sources),
        "top_failure_sources": [
            {"ip": ip, "failures": count} for ip, count in sources.most_common(5)
        ],
    }


def get_snapshot():
    from gotchi_settings import load
    override = os.environ.get("SECURIGOTCHI_AUTH_LOG") or load()['auth_log']
    candidates = (override,) if override else DEFAULT_LOGS
    for candidate in candidates:
        path = Path(candidate).expanduser()
        try:
            if not path.is_file():
                continue
            lines = _read_tail(path)
        except (PermissionError, OSError):
            continue
        return {
            "status": "available",
            "source": path.name,
            "sample_lines": len(lines),
            "note": "Current accessible log tail only; not a complete intrusion history or live feed.",
            **summarize_lines(lines),
        }
    return {
        "status": "unavailable",
        "source": None,
        "sample_lines": 0,
        "note": "No readable SSH auth log. Choose a readable SSH text log in Settings or set SECURIGOTCHI_AUTH_LOG.",
        **summarize_lines([]),
    }
