"""Bounded security summaries for trusted local MCP clients and the dashboard.

No raw records, source IPs, log messages, or user-controlled alert titles.
"""
from contextlib import closing
from datetime import datetime, timezone
import time

from gotchi_monitor import overview, connect, database_path

SAFE_ALERT_TITLES = frozenset({
    "Repeated SSH login failures",
    "Disk usage elevated",
    "Memory usage elevated",
})
SAFE_SEVERITIES = frozenset({"info", "warning", "high", "critical"})
SAFE_CATEGORIES = frozenset({"ssh", "health"})


def snapshot(now=None):
    data = overview(now=now)
    alerts = []
    for item in data["alerts"][:10]:
        title = item.get("title")
        alerts.append({
            "severity": item.get("severity") if item.get("severity") in SAFE_SEVERITIES else "info",
            "category": item.get("category") if item.get("category") in SAFE_CATEGORIES else "other",
            "title": title if title in SAFE_ALERT_TITLES else "Other security alert",
        })
    raw_health = data.get("health") or {}
    health = {
        key: raw_health.get(key)
        for key in ("disk_percent", "memory_percent", "load_avg")
    } if data.get("health") else None
    return {
        "status": data["status"],
        "mood": data["mood"],
        "source_status": data["log_status"],
        "health": health,
        "counts": {
            key: int(data["events_24h"].get(key, 0))
            for key in ("failed", "accepted", "invalid_user")
        },
        "alerts": alerts,
        "notice": ("Counts are sampled, not proof of compromise or safety. "
                   "A trusted MCP host may share these aggregates with its model."),
    }


def trends(hours=24, now=None):
    if type(hours) is not int or not 1 <= hours <= 72:
        raise ValueError("hours must be an integer from 1 to 72")
    now = int(time.time()) if now is None else int(now)
    start = now // 3600 * 3600 - (hours - 1) * 3600
    buckets = [{
        "hour": datetime.fromtimestamp(start + 3600 * i, timezone.utc).strftime("%Y-%m-%dT%H:00Z"),
        "failed": 0, "accepted": 0, "invalid_user": 0
    } for i in range(hours)]
    if database_path().exists():
        with closing(connect()) as conn:
            for row in conn.execute(
                "SELECT (ts / 3600) AS bucket, kind, COUNT(*) AS total FROM events "
                "WHERE ts >= ? AND ts < ? "
                "AND kind IN ('failed', 'accepted', 'invalid_user') "
                "GROUP BY (ts / 3600), kind",
                (start, start + hours * 3600)
            ):
                index = int(row["bucket"]) - (start // 3600)
                if 0 <= index < hours:
                    buckets[index][row["kind"]] += int(row["total"])
    return buckets
