from __future__ import annotations

from decimal import Decimal

import pytest

from core.ingestion.options.normalizer import normalize_polygon_snapshot_result, normalize_polygon_snapshot_results


@pytest.mark.unit
def test_normalize_polygon_snapshot_result_parses_required_keys() -> None:
    raw = {
        "details": {
            "ticker": "O:MSFT240119P00050000",
            "expiration_date": "2024-01-19",
            "strike_price": 50,
            "contract_type": "put",
        },
        "day": {"close": 1.23, "volume": 100},
        "open_interest": 200,
        "implied_volatility": 0.5,
        "greeks": {"delta": -0.12, "gamma": 0.01, "theta": -0.02, "vega": 0.03},
        "last_quote": {"bid": 1.1, "ask": 1.2},
    }

    snap = normalize_polygon_snapshot_result(raw)
    assert snap.contract_ticker == "O:MSFT240119P00050000"
    assert snap.db_expiration_date().isoformat() == "2024-01-19"
    assert snap.db_strike_price() == Decimal("50.0000")
    assert snap.db_option_type() == "P"
    assert snap.bid == Decimal("1.1")
    assert snap.ask == Decimal("1.2")
    assert snap.day_volume == 100
    assert snap.open_interest == 200
    assert snap.implied_volatility == Decimal("0.5")
    assert snap.delta == Decimal("-0.12")


@pytest.mark.unit
def test_normalize_polygon_snapshot_results_drops_non_dict_rows(caplog) -> None:
    caplog.set_level("DEBUG")
    normalized = normalize_polygon_snapshot_results([{"details": {"ticker": "O:AAPL240119C00055000"}}, "bad"])
    assert len(normalized) == 1
    record = next(r for r in caplog.records if r.levelname == "DEBUG")
    assert getattr(record, "stage") == "normalizer"
    assert getattr(record, "raw") == 2
    assert getattr(record, "normalized") == 1
    assert getattr(record, "dropped_non_dict") == 1
