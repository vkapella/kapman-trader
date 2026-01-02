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
        "primary_recommendation": {
            "action": "ENTER",
            "strategy_class": "LONG_CALL",
            "direction": "BULLISH",
            "confidence_score": 80,
            "time_horizon": "short",
            "rationale_summary": "Test rationale.",
        },
        "alternative_recommendations": [
            {
                "label": "Alt 1",
                "action": "WAIT",
                "strategy_class": "NONE",
                "direction": "NEUTRAL",
                "confidence_score": 60,
                "blocking_reason": "Blocked.",
                "promotion_conditions": "Clear veto.",
            }
        ],
        "reasoning_trace": {
            "fired_rules": [],
            "cluster_contributions": [{"cluster": "Meta", "impact": "TEST"}],
            "supporting_factors": [],
            "blocking_factors": [],
        },
        "confidence_summary": {
            "confidence_type": "RELATIVE",
            "ranking_basis": "Primary outranks alternatives by construction",
            "confidence_gap_notes": None,
        },
        "missing_data_declaration": [],
        "guardrails_and_disclaimers": ["Guardrail"],
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
    response["primary_recommendation"].update(
        {"option_strike": 150, "option_expiration": "2026-01-17", "option_type": "C"}
    )
    contracts = {(date(2026, 1, 17), Decimal("150.0000"), "C")}

    validated = _validate_with_context(monkeypatch, response, contracts=contracts)

    assert validated["primary_recommendation"]["option_strike"] == 150
    assert len(validated["alternative_recommendations"]) == 1


def test_invalid_expiration_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _base_response()
    response["primary_recommendation"].update(
        {"option_strike": 150, "option_expiration": "2026-02-17", "option_type": "C"}
    )
    contracts = {(date(2026, 1, 17), Decimal("150.0000"), "C")}

    validated = _validate_with_context(monkeypatch, response, contracts=contracts)

    assert validated["snapshot_metadata"]["ticker"] == "UNKNOWN"
    assert "Invalid option contract" in validated["primary_recommendation"]["rationale_summary"]


def test_invalid_strike_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _base_response()
    response["primary_recommendation"].update(
        {"option_strike": 155, "option_expiration": "2026-01-17", "option_type": "C"}
    )
    contracts = {(date(2026, 1, 17), Decimal("150.0000"), "C")}

    validated = _validate_with_context(monkeypatch, response, contracts=contracts)

    assert validated["snapshot_metadata"]["ticker"] == "UNKNOWN"
    assert "Invalid option contract" in validated["primary_recommendation"]["rationale_summary"]


def test_invalid_option_type_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _base_response()
    response["primary_recommendation"].update(
        {"option_strike": 150, "option_expiration": "2026-01-17", "option_type": "P"}
    )
    contracts = {(date(2026, 1, 17), Decimal("150.0000"), "C")}

    validated = _validate_with_context(monkeypatch, response, contracts=contracts)

    assert validated["snapshot_metadata"]["ticker"] == "UNKNOWN"
    assert "Invalid option contract" in validated["primary_recommendation"]["rationale_summary"]


def test_normalization_failure_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _base_response()
    response["primary_recommendation"].update(
        {"option_strike": "bad", "option_expiration": "2026-01-17", "option_type": "C"}
    )
    contracts = {(date(2026, 1, 17), Decimal("150.0000"), "C")}

    validated = _validate_with_context(monkeypatch, response, contracts=contracts)

    assert validated["snapshot_metadata"]["ticker"] == "UNKNOWN"
    assert "Invalid option contract" in validated["primary_recommendation"]["rationale_summary"]


def test_mixed_valid_invalid_recommendations(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _base_response()
    response["primary_recommendation"].update(
        {"option_strike": 150, "option_expiration": "2026-01-17", "option_type": "C"}
    )
    response["alternative_recommendations"] = [
        {
            "label": "Valid alt",
            "action": "WAIT",
            "strategy_class": "NONE",
            "direction": "NEUTRAL",
            "confidence_score": 60,
            "blocking_reason": "Blocked.",
            "promotion_conditions": "Clear veto.",
            "option_strike": 150,
            "option_expiration": "2026-01-17",
            "option_type": "C",
        },
        {
            "label": "Invalid alt",
            "action": "WAIT",
            "strategy_class": "NONE",
            "direction": "NEUTRAL",
            "confidence_score": 55,
            "blocking_reason": "Blocked.",
            "promotion_conditions": "Clear veto.",
            "option_strike": 155,
            "option_expiration": "2026-01-17",
            "option_type": "C",
        },
    ]
    contracts = {(date(2026, 1, 17), Decimal("150.0000"), "C")}

    validated = _validate_with_context(monkeypatch, response, contracts=contracts)

    assert len(validated["alternative_recommendations"]) == 1
    assert validated["alternative_recommendations"][0]["label"] == "Valid alt"
