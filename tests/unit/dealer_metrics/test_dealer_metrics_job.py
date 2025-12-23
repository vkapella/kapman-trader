from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from core.metrics.dealer_metrics_job import _load_option_contracts


class _DummyCursor:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def __enter__(self) -> "_DummyCursor":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def execute(self, *args, **kwargs) -> None:
        return None

    def fetchall(self) -> list[tuple]:
        return self._rows


class _DummyConn:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def cursor(self) -> _DummyCursor:
        return _DummyCursor(self._rows)


def test_load_option_contracts_allows_missing_pricing() -> None:
    expiration_date = date(2025, 1, 31)
    rows = [
        (
            expiration_date,
            Decimal("110"),
            "C",
            None,  # bid
            None,  # ask
            10,  # volume
            200,  # open_interest
            Decimal("0.30"),
            Decimal("0.5"),
            Decimal("0.02"),
        )
    ]

    contracts, stats = _load_option_contracts(
        conn=_DummyConn(rows),
        ticker_id="TEST",
        effective_options_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        effective_options_date=date(2025, 1, 1),
        max_dte_days=90,
        min_open_interest=100,
        min_volume=1,
    )

    assert len(contracts) == 1
    assert stats.total == 1
    assert stats.low_open_interest == 0
    assert stats.low_volume == 0
