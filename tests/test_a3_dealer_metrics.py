from __future__ import annotations

from datetime import date, timezone

from core.metrics.dealer_metrics_job import _should_process_ticker, _snapshot_time_utc
from scripts.run_a3_dealer_metrics import _parse_snapshot_time, _resolve_snapshot_dates


class _DummyCursor:
    def __init__(self, *, max_date: date | None, range_dates: list[date]) -> None:
        self._max_date = max_date
        self._range_dates = range_dates
        self._query = ""

    def __enter__(self) -> "_DummyCursor":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def execute(self, query: str, params=None) -> None:
        self._query = query

    def fetchone(self):
        if "MAX(date)" in self._query:
            return (self._max_date,)
        return (None,)

    def fetchall(self):
        if "SELECT DISTINCT date" in self._query:
            return [(d,) for d in self._range_dates]
        return []


class _DummyConn:
    def __init__(self, *, max_date: date | None, range_dates: list[date]) -> None:
        self._max_date = max_date
        self._range_dates = range_dates

    def cursor(self) -> _DummyCursor:
        return _DummyCursor(max_date=self._max_date, range_dates=self._range_dates)


def test_snapshot_time_derivation_uses_canonical_stored_utc() -> None:
    snapshot_date = date(2025, 1, 2)
    snapshot_time = _snapshot_time_utc(snapshot_date)

    assert snapshot_time.tzinfo == timezone.utc
    assert snapshot_time.date() == snapshot_date
    assert (snapshot_time.hour, snapshot_time.minute, snapshot_time.second, snapshot_time.microsecond) == (
        23,
        59,
        59,
        999999,
    )


def test_parse_snapshot_time_accepts_z_suffix() -> None:
    parsed = _parse_snapshot_time("2025-01-02T21:00:00Z")
    assert parsed.tzinfo == timezone.utc
    assert parsed.isoformat() == "2025-01-02T21:00:00+00:00"


def test_resolve_snapshot_dates_defaults_to_latest() -> None:
    latest = date(2025, 1, 5)
    conn = _DummyConn(max_date=latest, range_dates=[])
    resolved = _resolve_snapshot_dates(conn, date_value=None, snapshot_time=None, start_date=None, end_date=None)
    assert resolved == [latest]


def test_resolve_snapshot_dates_inclusive_range() -> None:
    start = date(2025, 1, 2)
    mid = date(2025, 1, 3)
    end = date(2025, 1, 4)
    conn = _DummyConn(max_date=date(2025, 1, 10), range_dates=[start, mid, end])
    resolved = _resolve_snapshot_dates(conn, date_value=None, snapshot_time=None, start_date=start, end_date=end)
    assert resolved == [start, mid, end]


def test_resolve_snapshot_dates_prefers_single_date() -> None:
    single = date(2025, 1, 7)
    conn = _DummyConn(max_date=date(2025, 1, 10), range_dates=[])
    resolved = _resolve_snapshot_dates(
        conn,
        date_value=single,
        snapshot_time=None,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
    )
    assert resolved == [single]


def test_resolve_snapshot_dates_normalizes_provided_snapshot_time_to_ny_trading_day() -> None:
    conn = _DummyConn(max_date=date(2025, 1, 10), range_dates=[])
    resolved = _resolve_snapshot_dates(
        conn,
        date_value=None,
        snapshot_time=_parse_snapshot_time("2025-01-03T04:59:59.999999+00:00"),
        start_date=None,
        end_date=None,
    )
    assert resolved == [date(2025, 1, 2)]


def test_should_process_ticker_skips_existing_metrics() -> None:
    existing = {"A", "B"}
    assert _should_process_ticker("A", existing) is False
    assert _should_process_ticker("C", existing) is True
