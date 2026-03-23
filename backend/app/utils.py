"""Shared utility functions for the Drama Remix backend."""

from datetime import datetime, timezone, timedelta

# Beijing timezone (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))


def beijing_now() -> datetime:
    """Return the current time in Beijing timezone (UTC+8).

    Returns a NAIVE datetime (no tzinfo) so that SQLite/aiosqlite stores
    the value as-is without converting back to UTC.
    """
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)
