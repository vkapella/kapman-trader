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
        "snapshot_metadata": {
            "ticker": "AAPL",
            "snapshot_time": "2026-01-10T00:00:00+00:00",
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
        "confidence_summary": {"score": 0.65},
    }


@pytest.mark.integration
def test_end_to_end_build_parse_with_fixed_option_chain_snapshot() -> None:
    option_chain_snapshot = [
        {"expiration": "2026-01-17", "strike": 150, "type": "CALL"},
        {"expiration": "2026-01-17", "strike": 155, "type": "CALL"},
        {"expiration": "2026-01-17", "strike": 145, "type": "PUT"},
    ]
    prompt_text = build_prompt(
        snapshot_payload={
            "symbol": "AAPL",
            "snapshot_time": "2026-01-10T00:00:00Z",
            "market_structure": {"wyckoff_regime": "MARKUP", "regime_confidence": 0.7},
        },
        option_context={
            "option_chain_snapshot": option_chain_snapshot,
            "option_selection_constraints": {"min_open_interest": 500},
        },
        authority_constraints={},
        instructions={},
        prompt_version="test",
    )
    payload = _extract_injected_payload(prompt_text)
    assert payload["option_chain_snapshot"] == option_chain_snapshot
    response = normalize_agent_response(
        raw_response=json.dumps(_valid_response()),
        provider_id="openai",
        model_id="gpt-5-mini",
        prompt_version="test",
        kapman_model_version="test",
    )
    assert response["context_evaluation"]["status"] == "ACCEPTED"


@pytest.mark.integration
def test_end_to_end_rejects_contracts_outside_fixture() -> None:
    option_chain_snapshot = [
        {"expiration": "2026-01-17", "strike": 150, "type": "CALL"},
        {"expiration": "2026-01-17", "strike": 155, "type": "CALL"},
        {"expiration": "2026-01-17", "strike": 145, "type": "PUT"},
    ]
    prompt_text = build_prompt(
        snapshot_payload={
            "symbol": "AAPL",
            "snapshot_time": "2026-01-10T00:00:00Z",
            "market_structure": {"wyckoff_regime": "MARKUP", "regime_confidence": 0.7},
        },
        option_context={
            "option_chain_snapshot": option_chain_snapshot,
            "option_selection_constraints": {"min_open_interest": 500},
        },
        authority_constraints={},
        instructions={},
        prompt_version="test",
    )
    response = _valid_response()
    response["option_recommendations"]["primary"].pop("stop_loss")

    normalized = normalize_agent_response(
        raw_response=json.dumps(response),
        provider_id="openai",
        model_id="gpt-5-mini",
        prompt_version="test",
        kapman_model_version="test",
    )

    assert normalized["context_evaluation"]["status"] == "REJECTED"
    assert normalized["context_evaluation"]["failure_type"] == "SCHEMA_FAIL"
