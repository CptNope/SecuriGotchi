"""Optional local desktop alerts from the existing monitor database.

No cloud endpoints, credential sharing, background threads, or automatic commands.
Requires a working Linux user desktop notification session (notify-send/D-Bus).
"""
import argparse
from contextlib import closing
import logging
import shutil
import subprocess

from gotchi_monitor import connect, SEVERITY

LOG = logging.getLogger(__name__)
LEVELS = ("warning", "high", "critical")


def _cursor_table(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS notification_cursor "
        "(name TEXT PRIMARY KEY, last_id INTEGER NOT NULL)"
    )


def enable_notifications():
    """Begin observing *future* alerts: don't replay the 30-day alert archive."""
    with closing(connect()) as conn, conn:
        _cursor_table(conn)
        greatest = conn.execute("SELECT COALESCE(MAX(id),0) FROM alerts").fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO notification_cursor(name,last_id) VALUES (?,?)",
            ("local-desktop", greatest),
        )


def _notify_desktop(severity, title):
    """Return True only if a local desktop broker accepted the message."""
    urgency = "critical" if severity in ("critical", "high") else "normal"
    try:
        result = subprocess.run(
            [
                "notify-send", "--app-name=SecuriGotchi",
                "--urgency=" + urgency, "--expire-time=10000",
                "SecuriGotchi security alert",
                severity.upper() + ": " + title,
            ],
            timeout=5, check=False, capture_output=True, text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def deliver_pending(min_level="high", sender=None, limit=20):
    """Deliver eligible alerts and save a durable cursor after each one.

    The caller must invoke enable_notifications() before the collector's first
    monitored poll. The delivery guarantee is best-effort: a crash after the
    desktop broker accepts a message can cause a duplicate on restart.
    """
    if min_level not in LEVELS:
        raise ValueError("Minimum notification level must be warning, high, or critical")
    if not 1 <= limit <= 100:
        raise ValueError("Notification batch size must be 1-100")
    sender = _notify_desktop if sender is None else sender
    with closing(connect()) as conn:
        _cursor_table(conn)
        row = conn.execute(
            "SELECT last_id FROM notification_cursor WHERE name=?",
            ("local-desktop",),
        ).fetchone()
        if row is None:
            raise RuntimeError("Call enable_notifications() before dispatching notifications")
        pending = conn.execute(
            "SELECT id,severity,title FROM alerts WHERE id>? ORDER BY id LIMIT ?",
            (row["last_id"], limit),
        ).fetchall()
        sent = 0
        for alert in pending:
            severity = alert["severity"]
            if severity not in SEVERITY:
                LOG.warning("Unknown alert severity; halting notification dispatch")
                break
            if SEVERITY[severity] >= SEVERITY[min_level]:
                try:
                    success = bool(sender(severity, alert["title"]))
                except Exception:
                    LOG.exception("Desktop notification failed")
                    success = False
                if not success:
                    LOG.warning("Desktop notification unavailable; alert retained for retry")
                    break
                sent += 1
            with conn:
                conn.execute(
                    "UPDATE notification_cursor SET last_id=? WHERE name=?",
                    (alert["id"], "local-desktop"),
                )
        return sent


def main():
    parser = argparse.ArgumentParser(description="SecuriGotchi local desktop notification test")
    parser.add_argument("command", choices=["test"])
    args = parser.parse_args()
    if not shutil.which("notify-send"):
        parser.error("notify-send unavailable. Install libnotify-bin on Debian/Ubuntu.")
    if not _notify_desktop("warning", "Desktop notification test"):
        parser.error("Desktop notification delivery failed. Check graphical login and D-Bus session.")
    print("Desktop notification broker accepted the test message.")


if __name__ == "__main__":
    main()
