from __future__ import annotations

from core.providers.ai import invoke as invoke_module


def _minimal_payload() -> dict:
    return {
        "symbol": "AAPL",
        "snapshot_time": "2026-01-10T00:00:00+00:00",
        "daily_snapshot": {"wyckoff_regime": "MARKUP", "wyckoff_regime_confidence": 0.8},
        "wyckoff_regime_transitions": [],
        "wyckoff_sequences": [],
        "wyckoff_sequence_events": [],
        "wyckoff_snapshot_evidence": [],
    }


def test_dry_run_returns_schema_compliant_response() -> None:
    response = invoke_module.invoke_planning_agent(
        provider_id="openai",
        model_id="gpt-5-mini",
        snapshot_payload=_minimal_payload(),
        option_context={},
        authority_constraints={},
        instructions={},
        prompt_version="test",
        kapman_model_version="test",
        debug=False,
        dry_run=True,
    )

    assert response["context_label"] == "MARKUP"
    assert response["confidence_score"] == 0.0
    assert response["conditional_recommendation"]["action"] == "HOLD"
