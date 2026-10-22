"""Opt-in, read-only local monitoring with a bounded SQLite event store.

Start separately: python gotchi_monitor.py watch
The collector never executes plugins, changes firewall rules, or uses sudo.
Event timestamps are ingestion times, not source-log timestamps.
"""
import argparse
from collections import Counter
from contextlib import closing
import os
from pathlib import Path
import shutil
import sys
import sqlite3
import stat
import time
from contextlib import contextmanager

from gotchi_auth import data_dir
from gotchi_platform import system_health
from gotchi_lock import exclusive_watch_lock
from gotchi_threats import DEFAULT_LOGS, _source_ip

MAX_READ_BYTES = 1024 * 1024
RETENTION_SECONDS = 7 * 86400
ALERT_RETENTION_SECONDS = 30 * 86400
ALERT_COOLDOWN_SECONDS = 15 * 60
FAILURE_WINDOW_SECONDS = 5 * 60
SEVERITY = {"info": 0, "warning": 1, "high": 2, "critical": 3}


def database_path():
    return data_dir() / "monitor.sqlite3"


def connect():
    path = database_path()
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError("Monitor database must be a regular file owned by this user")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise RuntimeError("Monitor database must have owner-only permissions (0600)")
    finally:
        os.close(fd)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cursors (
            path TEXT PRIMARY KEY, device INTEGER NOT NULL, inode INTEGER NOT NULL,
            offset INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY, ts INTEGER NOT NULL,
            kind TEXT NOT NULL, source TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_event_ts ON events(ts);
        CREATE INDEX IF NOT EXISTS idx_event_source ON events(kind, source, ts);
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY, ts INTEGER NOT NULL,
            category TEXT NOT NULL, severity TEXT NOT NULL,
            title TEXT NOT NULL, detail TEXT NOT NULL, fingerprint TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_alert_ts ON alerts(ts);
        CREATE INDEX IF NOT EXISTS idx_alert_fingerprint ON alerts(fingerprint, ts);
        CREATE TABLE IF NOT EXISTS health (
            ts INTEGER PRIMARY KEY, disk_percent REAL,
            memory_percent REAL, load_avg REAL
        );
        CREATE TABLE IF NOT EXISTS monitor_state (
            id INTEGER PRIMARY KEY CHECK (id=1),
            last_poll INTEGER NOT NULL, log_status TEXT NOT NULL,
            source_name TEXT, bytes_skipped INTEGER NOT NULL
        );
    """)
    return conn


def sample_health():
    return system_health()


def parse_ssh_line(line):
    """Return a normalized event only; no usernames or raw log data are stored."""
    if "sshd" not in line:
        return None
    if "Failed password" in line or "Failed publickey" in line:
        return "failed", _source_ip(line)
    if "Accepted password" in line or "Accepted publickey" in line:
        return "accepted", None
    if "Invalid user" in line:
        return "invalid_user", None
    return None


def _select_log(explicit=None):
    if explicit:
        candidates = (explicit,)
    elif os.environ.get("SECURIGOTCHI_AUTH_LOG"):
        candidates = (os.environ["SECURIGOTCHI_AUTH_LOG"],)
    else:
        candidates = DEFAULT_LOGS
    for candidate in candidates:
        path = Path(candidate).expanduser()
        try:
            if path.is_file():
                with path.open("rb"):
                    return path
        except (OSError, PermissionError):
            pass
    return None


def _consume_new(conn, path):
    """Incremental file read, rotation/truncation aware; commit cursor with events."""
    source = str(path.resolve())
    with path.open("rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise OSError("Only regular log files are supported")
        previous = conn.execute(
            "SELECT device, inode, offset FROM cursors WHERE path=?", (source,)
        ).fetchone()
        if previous is None:
            # Never interpret old log history as new attacks on first startup.
            start, discontinuity, skipped = info.st_size, False, 0
        elif previous["device"] != info.st_dev or previous["inode"] != info.st_ino or info.st_size < previous["offset"]:
            start, discontinuity, skipped = max(0, info.st_size - MAX_READ_BYTES), True, max(0, info.st_size - MAX_READ_BYTES)
        else:
            start, discontinuity, skipped = previous["offset"], False, 0
            if info.st_size - start > MAX_READ_BYTES:
                skipped = info.st_size - start - MAX_READ_BYTES
                start = info.st_size - MAX_READ_BYTES
                discontinuity = True
        handle.seek(start)
        chunk = handle.read(MAX_READ_BYTES)
        # For truncation/rotation/overflow, cut a partial line at the new offset.
        cut = 0
        if discontinuity and start:
            marker = chunk.find(b"\n")
            if marker == -1:
                chunk = b""
            else:
                cut = marker + 1
        text = chunk[cut:]
        last_newline = text.rfind(b"\n")
        complete = text[:last_newline + 1] if last_newline >= 0 else b""
        new_offset = start + cut + len(complete)
        if previous is None:
            new_offset = info.st_size
        conn.execute(
            "INSERT INTO cursors(path,device,inode,offset) VALUES (?,?,?,?) "
            "ON CONFLICT(path) DO UPDATE SET device=excluded.device,"
            "inode=excluded.inode,offset=excluded.offset",
            (source, info.st_dev, info.st_ino, new_offset),
        )
        if previous is None:
            return [], 0
        records = []
        for line in complete.decode("utf-8", errors="replace").splitlines():
            event = parse_ssh_line(line)
            if event:
                records.append(event)
        return records, skipped


def _emit(conn, now, category, severity, title, detail, fingerprint):
    previous = conn.execute(
        "SELECT ts, severity FROM alerts WHERE fingerprint=? ORDER BY ts DESC LIMIT 1",
        (fingerprint,),
    ).fetchone()
    if previous is not None and now - previous["ts"] < ALERT_COOLDOWN_SECONDS:
        if SEVERITY[severity] <= SEVERITY[previous["severity"]]:
            return False
    conn.execute(
        "INSERT INTO alerts(ts,category,severity,title,detail,fingerprint) "
        "VALUES (?,?,?,?,?,?)",
        (now, category, severity, title, detail, fingerprint),
    )
    return True


def _health_alerts(conn, now, health):
    for key, label in (("disk_percent", "Disk usage"), ("memory_percent", "Memory usage")):
        value = health.get(key)
        if value is None:
            continue
        severity = "critical" if value >= 97 else "high" if value >= 90 else "warning" if value >= 80 else None
        if severity:
            _emit(conn, now, "health", severity, f"{label} elevated",
                  f"{label}: {value:.1f}% (sampled locally)", key)


def run_once(now=None, log_path=None, health=None):
    """Read available log changes and machine health exactly once."""
    now = int(time.time()) if now is None else int(now)
    health = sample_health() if health is None else health
    path = _select_log(log_path)
    with closing(connect()) as conn, conn:
        records, skipped = [], 0
        status = "unavailable"
        if path:
            try:
                records, skipped = _consume_new(conn, path)
                status = "available"
            except (OSError, PermissionError):
                status = "unavailable"
        sources = set()
        for kind, ip in records:
            conn.execute("INSERT INTO events(ts,kind,source) VALUES (?,?,?)", (now, kind, ip))
            if kind == "failed" and ip:
                sources.add(ip)
        for ip in sources:
            count = conn.execute(
                "SELECT COUNT(*) FROM events WHERE kind='failed' AND source=? AND ts>=?",
                (ip, now - FAILURE_WINDOW_SECONDS),
            ).fetchone()[0]
            if count >= 5:
                severity = "critical" if count >= 10 else "high"
                _emit(conn, now, "ssh", severity, "Repeated SSH login failures",
                      f"{count} failed attempts from {ip} within the last 5 minutes of collector observations",
                      "ssh:" + ip)
        conn.execute(
            "INSERT OR REPLACE INTO health(ts,disk_percent,memory_percent,load_avg) "
            "VALUES (?,?,?,?)",
            (now, health.get("disk_percent"), health.get("memory_percent"), health.get("load_avg")),
        )
        _health_alerts(conn, now, health)
        conn.execute(
            "INSERT OR REPLACE INTO monitor_state(id,last_poll,log_status,source_name,bytes_skipped) VALUES (1,?,?,?,?)",
            (now, status, path.name if status == "available" else None, skipped),
        )
        conn.execute("DELETE FROM events WHERE ts < ?", (now - RETENTION_SECONDS,))
        conn.execute("DELETE FROM health WHERE ts < ?", (now - RETENTION_SECONDS,))
        conn.execute("DELETE FROM alerts WHERE ts < ?", (now - ALERT_RETENTION_SECONDS,))
    return {"last_poll": now, "log_status": status, "events_added": len(records), "bytes_skipped": skipped}


def overview(now=None):
    now = int(time.time()) if now is None else int(now)
    if not database_path().exists():
        return {
            "status": "not_started", "last_poll": None, "log_status": "unavailable",
            "source": None, "bytes_skipped": 0, "health": None, "events_24h": {},
            "alerts": [], "mood": "sleeping",
        }
    with closing(connect()) as conn:
        state = conn.execute("SELECT * FROM monitor_state WHERE id=1").fetchone()
        sample = conn.execute("SELECT * FROM health ORDER BY ts DESC LIMIT 1").fetchone()
        event_counts = {
            row["kind"]: row["total"] for row in conn.execute(
                "SELECT kind, COUNT(*) AS total FROM events WHERE ts>=? GROUP BY kind",
                (now - 86400,),
            )
        }
        alerts = [
            {"ts": row["ts"], "severity": row["severity"], "category": row["category"],
             "title": row["title"], "detail": row["detail"]}
            for row in conn.execute(
                "SELECT ts,severity,category,title,detail FROM alerts WHERE ts>=? "
                "ORDER BY ts DESC, id DESC LIMIT 12", (now - 86400,)
            )
        ]
    active = state is not None and now - state["last_poll"] <= 180
    severity = max((SEVERITY[a["severity"]] for a in alerts if now - a["ts"] <= 3600), default=0)
    mood = "sleeping" if not active else (
        "critical" if severity >= 3 else "alert" if severity == 2 else
        "watchful" if severity == 1 else "calm"
    )
    return {
        "status": "running" if active else "stale",
        "last_poll": state["last_poll"] if state else None,
        "log_status": state["log_status"] if state else "unavailable",
        "source": state["source_name"] if state else None,
        "bytes_skipped": state["bytes_skipped"] if state else 0,
        "health": {
            "disk_percent": sample["disk_percent"], "memory_percent": sample["memory_percent"],
            "load_avg": sample["load_avg"]
        } if sample else None,
        "events_24h": event_counts,
        "alerts": alerts,
        "mood": mood,
    }


def main():
    parser = argparse.ArgumentParser(description="Read-only SecuriGotchi local monitoring collector")
    parser.add_argument("command", choices=["once", "watch", "status"])
    parser.add_argument("--interval", type=int, default=60, help="Seconds between polls (10-3600)")
    parser.add_argument("--notify", action="store_true", help="Opt-in desktop notifications (watch only)")
    parser.add_argument("--notify-level", choices=["warning", "high", "critical"], default="high")
    args = parser.parse_args()
    if args.notify and args.command != "watch":
        parser.error("--notify requires the watch command")
    if not 10 <= args.interval <= 3600:
        parser.error("--interval must be between 10 and 3600 seconds")
    if args.command == "status":
        import json
        print(json.dumps(overview(), indent=2))
        return
    if args.command == "once":
        print(run_once())
        return
    notifier = None
    if args.notify:
        import shutil as _shutil
        if not _shutil.which("notify-send"):
            parser.error("notify-send is missing. Install libnotify-bin or omit --notify.")
        from gotchi_notifications import enable_notifications, deliver_pending
        notifier = deliver_pending
    print("Monitoring locally; Ctrl+C to stop. No firewall or scan operations are performed.")
    try:
        with exclusive_watch_lock():
            if notifier:
                enable_notifications()  # Before first poll; no historical alert replay.
            while True:
                print(run_once(), flush=True)
                if notifier:
                    notifier(min_level=args.notify_level)
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nCollector stopped.")


if __name__ == "__main__":
    main()
