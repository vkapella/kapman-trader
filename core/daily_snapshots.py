from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

NY_TRADING_TZ = ZoneInfo("America/New_York")
CANONICAL_DAILY_SNAPSHOT_UTC_TIME = time(23, 59, 59, 999999)
LEGACY_A3_SPLIT_UTC_TIMES = (
    time(3, 59, 59, 999999),
    time(4, 59, 59, 999999),
    time(23, 0, 0),
)


def canonical_daily_snapshot_time(snapshot_date: date) -> datetime:
    return datetime(
        year=snapshot_date.year,
        month=snapshot_date.month,
        day=snapshot_date.day,
        hour=CANONICAL_DAILY_SNAPSHOT_UTC_TIME.hour,
        minute=CANONICAL_DAILY_SNAPSHOT_UTC_TIME.minute,
        second=CANONICAL_DAILY_SNAPSHOT_UTC_TIME.second,
        microsecond=CANONICAL_DAILY_SNAPSHOT_UTC_TIME.microsecond,
        tzinfo=timezone.utc,
    )


def ny_trading_date(timestamp_value: datetime) -> date:
    if timestamp_value.tzinfo is None:
        timestamp_value = timestamp_value.replace(tzinfo=timezone.utc)
    return timestamp_value.astimezone(NY_TRADING_TZ).date()


def canonical_snapshot_time_for_timestamp(timestamp_value: datetime) -> datetime:
    return canonical_daily_snapshot_time(ny_trading_date(timestamp_value))
