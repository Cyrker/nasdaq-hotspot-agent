from __future__ import annotations

from datetime import timezone, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


FALLBACK_TIMEZONES: dict[str, tzinfo] = {
    "Asia/Shanghai": timezone(timedelta(hours=8), name="CST"),
    "America/New_York": timezone(timedelta(hours=-5), name="ET"),
    "UTC": timezone.utc,
}


def load_timezone(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return FALLBACK_TIMEZONES.get(name, timezone.utc)
