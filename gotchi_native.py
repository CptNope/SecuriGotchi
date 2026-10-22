"""Read-only OS event adapters.

No privilege escalation, network requests, plugin invocations or shell=True.
Adapters query bounded recent OS security events; native OS logs may be
inaccessible, private/redacted or incomplete. Every event is normalized to
(kind, optional source IP, stable ID); raw messages/usernames are discarded.
"""
from dataclasses import dataclass
import hashlib
import json
import os
import platform
import shutil
import subprocess
import xml.etree.ElementTree as ET

from gotchi_threats import _source_ip

MAX_EVENTS = 250
MAX_OUTPUT = 4 * 1024 * 1024
EVENT_NS = "{http://schemas.microsoft.com/win/2004/08/events/event}"


@dataclass(frozen=True)
class SecurityEvent:
    key: str
    kind: str
    ip: str | None


@dataclass(frozen=True)
class NativeBatch:
    status: str
    source: str
    entries: tuple[SecurityEvent, ...] = ()
    checkpoint: str | None = None
    detail: str = ""


def _run(argv):
    """Run a fixed, vetted read-only command. Never interpolate user input."""
    try:
        result = subprocess.run(
            argv, shell=False, capture_output=True, text=True,
            timeout=20, check=False, errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("OS event reader unavailable") from exc
    if result.returncode != 0:
        # stderr can include private OS details; do not include it in API output.
        raise RuntimeError("OS event source unreadable (check permissions and logging)")
    if len(result.stdout.encode("utf-8")) > MAX_OUTPUT:
        raise RuntimeError("OS event response exceeded the safety limit")
    return result.stdout


def _ssh_event(message):
    if not isinstance(message, str):
        return None
    if "Failed password" in message or "Failed publickey" in message:
        return "failed", _source_ip(message)
    if "Accepted password" in message or "Accepted publickey" in message:
        return "accepted", None
    if "Invalid user" in message:
        return "invalid_user", None
    return None


def parse_windows_xml(payload):
    """Parse wevtutil Security log XML EventID 4625/4624."""
    if "<!DOCTYPE" in payload.upper() or "<!ENTITY" in payload.upper():
        raise ValueError("Document type definitions not permitted")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("Malformed Windows event XML") from exc
    nodes = [root] if root.tag.endswith("}Event") else root.findall(f".//{EVENT_NS}Event")
    entries = []
    for event in nodes[:MAX_EVENTS]:
        system = event.find(f"{EVENT_NS}System")
        if system is None:
            continue
        ident = system.find(f"{EVENT_NS}EventID")
        record = system.find(f"{EVENT_NS}EventRecordID")
        if ident is None or record is None:
            continue
        try:
            eid, rid = int(ident.text or ""), int(record.text or "")
        except ValueError:
            continue
        if eid not in (4624, 4625) or rid <= 0:
            continue
        ip = None
        if eid == 4625:
            event_data = event.find(f"{EVENT_NS}EventData")
            if event_data is not None:
                for node in event_data.findall(f"{EVENT_NS}Data"):
                    if node.get("Name") in ("IpAddress", "SourceNetworkAddress"):
                        from ipaddress import ip_address
                        try:
                            ip = str(ip_address((node.text or "").strip()))
                        except ValueError:
                            pass
        entries.append(SecurityEvent(f"win:{rid}", "failed" if eid == 4625 else "accepted", ip))
    return tuple(entries)


def poll_windows(checkpoint=None):
    if platform.system() != "Windows" or not shutil.which("wevtutil"):
        return NativeBatch("unavailable", "windows-security", detail="Windows Security log reader unavailable")
    argv = [
        "wevtutil", "qe", "Security",
        "/q:*[System[(EventID=4625 or EventID=4624)]]",
        "/rd:true", "/f:xml", f"/c:{MAX_EVENTS}", "/e:Events",
    ]
    try:
        events = parse_windows_xml(_run(argv))
    except (RuntimeError, ValueError):
        return NativeBatch("unavailable", "windows-security", detail="Security log inaccessible or invalid")
    newest = max((int(item.key[4:]) for item in events), default=0)
    old = int(checkpoint) if checkpoint and checkpoint.isdecimal() else 0
    # The query is a newest-N window. Missing older records cannot be recovered
    # if more than N matching events arrive between polls.
    new = tuple(item for item in events if int(item.key[4:]) > old)
    return NativeBatch("partial" if len(events) >= MAX_EVENTS else "available",
                       "windows-security", new, str(max(newest, old)) if newest or old else None,
                       "Newest matching Security events only; requires OS log permissions")


def parse_journal_json(payload):
    entries = []
    last_cursor = None
    for line in payload.splitlines():
        if not line.strip() or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            raise ValueError("Malformed journal JSON")
        if not isinstance(obj, dict):
            continue
        cursor = obj.get("__CURSOR")
        if not isinstance(cursor, str) or not cursor or len(cursor) > 4096:
            continue
        last_cursor = cursor
        parsed = _ssh_event(obj.get("MESSAGE"))
        if parsed:
            entries.append(SecurityEvent("journal:" + cursor, *parsed))
    return tuple(entries), last_cursor


def poll_journal(checkpoint=None):
    if platform.system() != "Linux" or not shutil.which("journalctl"):
        return NativeBatch("unavailable", "linux-journal", detail="journalctl unavailable")
    argv = ["journalctl", "--no-pager", "-q", "--output=json", "-n", str(MAX_EVENTS), "_COMM=sshd"]
    if checkpoint:
        argv.insert(6, "--after-cursor=" + checkpoint)
    try:
        events, last_cursor = parse_journal_json(_run(argv))
    except (RuntimeError, ValueError):
        return NativeBatch("unavailable", "linux-journal", detail="Journal unavailable or inaccessible")
    return NativeBatch("partial" if len(events) >= MAX_EVENTS else "available",
                       "linux-journal", events, last_cursor or checkpoint,
                       "Best-effort SSH journal observations")


def parse_macos_json(payload):
    try:
        data = json.loads(payload)
    except (ValueError, TypeError) as exc:
        raise ValueError("Malformed macOS log JSON") from exc
    if not isinstance(data, list):
        raise ValueError("macOS logs must be a JSON array")
    events = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        process = str(entry.get("process") or entry.get("processImagePath") or "").lower()
        if not (process == "sshd" or process.endswith("/sshd")):
            continue
        message = entry.get("eventMessage")
        parsed = _ssh_event(message)
        if not parsed:
            continue
        identity = json.dumps([
            entry.get("timestamp"), entry.get("processID"),
            entry.get("threadID"), entry.get("traceID"), message
        ], ensure_ascii=False, separators=(",", ":"))
        key = "mac:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
        events.append(SecurityEvent(key, *parsed))
    return tuple(events)


def poll_macos(checkpoint=None):
    if platform.system() != "Darwin":
        return NativeBatch("unavailable", "macos-unified", detail="macOS unified log unavailable")
    argv = [
        "/usr/bin/log", "show", "--style", "json", "--last", "5m",
        "--predicate", 'process == "sshd"',
    ]
    try:
        events = parse_macos_json(_run(argv))
    except (RuntimeError, ValueError):
        return NativeBatch("unavailable", "macos-unified", detail="Unified log inaccessible or invalid")
    return NativeBatch("available", "macos-unified", events, None,
                       "Rolling 5-minute SSH log window, deduplicated; may contain redacted events")


def selected_source(source="auto", has_text_log=False):
    if source not in ("auto", "file", "journal", "windows", "macos"):
        raise ValueError("Unsupported event source")
    if source != "auto":
        return source
    if os.environ.get("SECURIGOTCHI_AUTH_LOG") or has_text_log:
        return "file"
    return {"Linux": "journal", "Windows": "windows", "Darwin": "macos"}.get(platform.system(), "file")


def poll_native(source, checkpoint=None):
    if source == "windows":
        return poll_windows(checkpoint)
    if source == "macos":
        return poll_macos(checkpoint)
    if source == "journal":
        return poll_journal(checkpoint)
    raise ValueError("Unsupported native source")
