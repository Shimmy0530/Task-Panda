from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC `now` — drop-in for the deprecated `datetime.utcnow()`.

    Returns a tz-naive datetime in UTC. The whole codebase stores and compares
    naive-UTC datetimes (DB columns are naive; see `_to_naive_utc` in
    `routers/sessions.py`), so we must NOT return an aware datetime here — mixing
    aware and naive values raises `TypeError` on subtraction/comparison.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
