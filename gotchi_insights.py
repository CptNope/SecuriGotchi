"""Safe, aggregated monitoring summaries for the UI and local MCP clients."""
from contextlib import closing
from datetime import datetime, timezone
import time
from gotchi_monitor import overview, connect, database_path

def snapshot(now=None):
    data = overview(now=now)
    return {
        "status": data["status"], "mood": data["mood"],
        "source_status": data["log_status"],
        "health": data["health"],
        "counts": {k: data["events_24h"].get(k, 0) for k in ("failed", "accepted", "invalid_user")},
        "alerts": [{"severity": a["severity"], "category": a["category"], "title": a["title"]}
                   for a in data["alerts"][:10]],
        "notice": "Aggregated sampled security activity, not a comprehensive intrusion-detection report."
    }

def trends(hours=24, now=None):
    if type(hours) is not int or not 1 <= hours <= 72:
        raise ValueError("hours must be an integer from 1 to 72")
    now = int(time.time()) if now is None else int(now)
    start = now // 3600 * 3600 - (hours-1)*3600
    buckets = [{"hour": datetime.fromtimestamp(start+3600*i, timezone.utc).strftime("%Y-%m-%dT%H:00Z"),
                "failed": 0, "accepted": 0, "invalid_user": 0} for i in range(hours)]
    if database_path().exists():
        with closing(connect()) as conn:
            for row in conn.execute("SELECT ts, kind FROM events WHERE ts>=? AND ts<?",
                                    (start, start+hours*3600)):
                index = (row["ts"]-start)//3600
                if 0 <= index < hours and row["kind"] in ("failed","accepted","invalid_user"):
                    buckets[index][row["kind"]] += 1
    return buckets
