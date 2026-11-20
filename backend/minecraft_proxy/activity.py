"""Shared idle policy; timestamps are Unix seconds and flags are DynamoDB numbers."""

FIRST_JOIN_WAIT = 30 * 60
RETURNING_WAIT = 10 * 60
HEARTBEAT_MAX_AGE = 120


def deadline(activity):
    if not activity.get("ready_at") or activity.get("players_online", 0) > 0 or not activity.get("empty_since"):
        return None
    return int(activity["empty_since"]) + (RETURNING_WAIT if activity.get("ever_joined") else FIRST_JOIN_WAIT)


def healthy(activity, now):
    return bool(activity.get("heartbeat_at")) and -30 <= now - int(activity["heartbeat_at"]) <= HEARTBEAT_MAX_AGE


def idle_view(activity, now):
    fresh = healthy(activity, now)
    end = deadline(activity) if fresh else None
    return {
        "hasPlayed": bool(activity.get("ever_joined")),
        "monitoringHealthy": fresh,
        "deleteAt": end,
        "remainingSeconds": max(0, end - now) if end else None,
        "shutdownRequested": bool(activity.get("shutdown_requested")),
        "waitMinutes": 10 if activity.get("ever_joined") else 30,
    }


def observe(activity, now, players, joined=False, left=False):
    """Log events catch even players who join and leave between status probes."""
    result = dict(activity)
    result.setdefault("ready_at", now)
    result["players_online"] = players
    if players > 0 or joined:
        result["ever_joined"] = 1
    if players > 0:
        result["empty_since"] = 0
    elif not result.get("empty_since") or joined or left:
        result["empty_since"] = now
    result["heartbeat_at"] = now
    return result
