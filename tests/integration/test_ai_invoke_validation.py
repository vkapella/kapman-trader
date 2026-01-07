from __future__ import annotations

import json

import pytest

from core.providers.ai.prompt_builder import build_prompt
from core.providers.ai.response_parser import normalize_agent_response


def _extract_injected_payload(prompt_text: str) -> dict:
    if "<<<USER_PROMPT>>>" not in prompt_text:
        raise AssertionError("user prompt marker missing")
    user_text = prompt_text.split("<<<USER_PROMPT>>>", 1)[1]
    marker = "INJECTED INPUT (CANONICAL JSON)"
    if marker not in user_text:
        raise AssertionError("injected payload marker missing")
    start = user_text.index(marker)
    json_start = user_text.index("{", start)
    task_marker = "\n\nTASK"
    json_end = user_text.index(task_marker, json_start)
    payload_text = user_text[json_start:json_end].strip()
    return json.loads(payload_text)


def _valid_response() -> dict:
    return {
        "context_label": "MARKUP",
        "confidence_score": 0.65,
        "metric_assessment": {
            "supporting": ["wyckoff_regime"],
            "contradicting": [],
            "neutral": ["volatility_metrics_json"],
        },
        "metric_weights": {"wyckoff_regime": 0.5, "volatility_metrics_json": 0.2},
        "discarded_metrics": [],
        "conditional_recommendation": {
            "direction": "LONG",
            "action": "PROCEED",
            "option_type": None,
            "option_strategy": None,
        },
    }


@pytest.mark.integration
def test_end_to_end_build_parse_with_context_payload() -> None:
    snapshot_payload = {
        "symbol": "AAPL",
        "snapshot_time": "2026-01-10T00:00:00Z",
        "daily_snapshot": {
            "wyckoff_regime": "MARKUP",
            "wyckoff_regime_confidence": 0.7,
            "wyckoff_regime_set_by_event": "SOS",
            "events_json": {"events": ["SOS"]},
            "bc_score": 10,
            "spring_score": 4,
            "composite_score": 12.5,
            "technical_indicators_json": {"adx": 25},
            "dealer_metrics_json": {"gamma_flip": 150.0},
            "volatility_metrics_json": {"iv_rank": 55},
            "price_metrics_json": {"close": 185.5},
        },
        "wyckoff_regime_transitions": [],
        "wyckoff_sequences": [],
        "wyckoff_sequence_events": [],
        "wyckoff_snapshot_evidence": [],
    }
    prompt_text = build_prompt(
        snapshot_payload=snapshot_payload,
        option_context={},
        authority_constraints={},
        instructions={},
        prompt_version="test",
    )
    payload = _extract_injected_payload(prompt_text)
    assert payload["daily_snapshot"]["wyckoff_regime"] == "MARKUP"
    response = normalize_agent_response(
        raw_response=json.dumps(_valid_response()),
        provider_id="openai",
        model_id="gpt-5-mini",
        prompt_version="test",
        kapman_model_version="test",
    )
    assert response["context_label"] == "MARKUP"


@pytest.mark.integration
def test_end_to_end_rejects_missing_required_field() -> None:
    response = _valid_response()
    response.pop("context_label")

    with pytest.raises(ValueError, match="Missing top-level key"):
        normalize_agent_response(
            raw_response=json.dumps(response),
            provider_id="openai",
            model_id="gpt-5-mini",
            prompt_version="test",
            kapman_model_version="test",
        )
