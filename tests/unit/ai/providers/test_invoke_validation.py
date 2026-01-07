from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from core.providers.ai import invoke as invoke_module


def _base_response() -> dict:
    return {
        "snapshot_metadata": {
            "ticker": "AAPL",
            "snapshot_time": "2026-01-10T00:00:00+00:00",
            "model_version": "test",
            "wyckoff_regime": "MARKUP",
            "wyckoff_primary_event": "SOS",
            "data_completeness_flags": {},
            "ai_provider": "anthropic",
            "ai_model": "test-model",
            "ai_model_version": None,
            "kapman_model_version": "test",
        },
        "context_evaluation": {
            "status": "ACCEPTED",
            "failure_type": None,
            "reason": "Context supported.",
        },
        "option_recommendations": {
            "primary": {
                "option_type": "CALL",
                "strike": 150,
                "expiration": "2026-01-17",
                "stop_loss": "-50% premium",
                "profit_target": "+100% premium",
            },
            "alternatives": [],
        },
        "confidence_summary": {"score": 0.7},
    }


def _validate_with_context(monkeypatch: pytest.MonkeyPatch, response: dict, *, contracts: set) -> dict:
    expirations = {contract[0] for contract in contracts}
    options_time = datetime(2026, 1, 10, tzinfo=timezone.utc)

    def _stub_context(_snapshot_payload: dict):
        return expirations, contracts, options_time

    monkeypatch.setattr(invoke_module, "_load_option_chain_context", _stub_context)
    return invoke_module._validate_option_recommendations(
        response=response,
        snapshot_payload={"symbol": "AAPL", "snapshot_time": "2026-01-10T00:00:00+00:00"},
        provider_id="anthropic",
        model_id="test-model",
        prompt_version="test",
        kapman_model_version="test",
        invocation_id="inv-1",
    )


def test_valid_contract_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _base_response()
    contracts = {(date(2026, 1, 17), Decimal("150.0000"), "C")}

    validated = _validate_with_context(monkeypatch, response, contracts=contracts)

    assert validated["context_evaluation"]["status"] == "ACCEPTED"
    assert validated["context_evaluation"]["failure_type"] is None
    assert validated["option_recommendations"]["primary"]["strike"] == 150


def test_invalid_expiration_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _base_response()
    response["option_recommendations"]["primary"]["expiration"] = "2026-02-17"
    contracts = {(date(2026, 1, 17), Decimal("150.0000"), "C")}

    validated = _validate_with_context(monkeypatch, response, contracts=contracts)

    assert validated["context_evaluation"]["status"] == "REJECTED"
    assert validated["context_evaluation"]["failure_type"] == "INVALID_CHAIN"
    assert validated["option_recommendations"]["primary"] is None


def test_invalid_strike_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _base_response()
    response["option_recommendations"]["primary"]["strike"] = 155
    contracts = {(date(2026, 1, 17), Decimal("150.0000"), "C")}

    validated = _validate_with_context(monkeypatch, response, contracts=contracts)

    assert validated["context_evaluation"]["status"] == "REJECTED"
    assert validated["context_evaluation"]["failure_type"] == "INVALID_CHAIN"
    assert validated["option_recommendations"]["primary"] is None


def test_invalid_option_type_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _base_response()
    response["option_recommendations"]["primary"]["option_type"] = "PUT"
    contracts = {(date(2026, 1, 17), Decimal("150.0000"), "C")}

    validated = _validate_with_context(monkeypatch, response, contracts=contracts)

    assert validated["context_evaluation"]["status"] == "REJECTED"
    assert validated["context_evaluation"]["failure_type"] == "INVALID_CHAIN"
    assert validated["option_recommendations"]["primary"] is None


def test_normalization_failure_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _base_response()
    response["option_recommendations"]["primary"]["strike"] = "bad"
    contracts = {(date(2026, 1, 17), Decimal("150.0000"), "C")}

    validated = _validate_with_context(monkeypatch, response, contracts=contracts)

    assert validated["context_evaluation"]["status"] == "REJECTED"
    assert validated["context_evaluation"]["failure_type"] == "SCHEMA_FAIL"
    assert validated["option_recommendations"]["primary"] is None


def test_mixed_valid_invalid_recommendations(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _base_response()
    response["option_recommendations"]["alternatives"] = [
        {
            "option_type": "CALL",
            "strike": 150,
            "expiration": "2026-01-17",
            "stop_loss": "-50% premium",
            "profit_target": "+80% premium",
        },
        {
            "option_type": "CALL",
            "strike": 155,
            "expiration": "2026-01-17",
            "stop_loss": "-50% premium",
            "profit_target": "+80% premium",
        },
    ]
    contracts = {(date(2026, 1, 17), Decimal("150.0000"), "C")}

    validated = _validate_with_context(monkeypatch, response, contracts=contracts)

    assert validated["context_evaluation"]["status"] == "REJECTED"
    assert validated["context_evaluation"]["failure_type"] == "INVALID_CHAIN"
    assert validated["option_recommendations"]["primary"] is None
