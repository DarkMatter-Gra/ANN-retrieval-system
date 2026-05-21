from datetime import datetime, timezone


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now() -> datetime:
    return datetime.now(timezone.utc)
