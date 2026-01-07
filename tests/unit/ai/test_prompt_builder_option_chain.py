import json

from core.providers.ai.prompt_builder import build_prompt


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


def test_prompt_includes_context_payload_verbatim() -> None:
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
    assert payload == snapshot_payload


def test_prompt_allows_minimal_payload() -> None:
    prompt_text = build_prompt(
        snapshot_payload={"symbol": "AAPL", "snapshot_time": "2026-01-10T00:00:00Z"},
        option_context={},
        authority_constraints={},
        instructions={},
        prompt_version="test",
    )
    payload = _extract_injected_payload(prompt_text)
    assert payload["symbol"] == "AAPL"
