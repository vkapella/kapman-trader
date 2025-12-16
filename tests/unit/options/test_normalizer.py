import logging
from datetime import date

import pytest

from core.pipeline.options_normalizer import normalize_contracts


def test_parses_expiration_and_strike():
    raw = [{"expiration_date": "2024-01-19", "strike_price": "100", "option_type": "call"}]
    normalized = normalize_contracts(raw, "AAPL", as_of=date(2024, 1, 1))
    assert normalized[0]["expiration_date"].isoformat() == "2024-01-19"
    assert str(normalized[0]["strike_price"]) == "100"


def test_classifies_call_put():
    raw = [
        {"expiration_date": "2024-01-19", "strike_price": 50, "contract_type": "p"},
        {"expiration_date": "2024-01-19", "strike_price": 55, "symbol": "O:AAPL240119C00055000"},
    ]
    normalized = normalize_contracts(raw, "AAPL", as_of=date(2024, 1, 1))
    assert normalized[0]["option_type"] == "put"
    assert normalized[1]["option_type"] == "call"


def test_drops_malformed_with_logging(caplog):
    raw = [{"strike_price": 100}, {"expiration_date": "bad", "strike_price": 10, "option_type": "call"}]
    caplog.set_level(logging.INFO)
    normalized = normalize_contracts(raw, "MSFT", as_of=date(2024, 1, 1))
    assert normalized == []
    record = next(r for r in caplog.records if r.levelname == "INFO")
    assert getattr(record, "stage") == "normalize"
    assert getattr(record, "dropped") == 2
