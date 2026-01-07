import json

import pytest

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


def test_prompt_includes_option_chain_snapshot_verbatim() -> None:
    option_chain_snapshot = [
        {"expiration": "2026-01-17", "strike": 150, "type": "CALL"},
        {"expiration": "2026-01-17", "strike": 145, "type": "PUT"},
    ]
    option_selection_constraints = {"min_open_interest": 500, "max_spread": 0.15}
    prompt_text = build_prompt(
        snapshot_payload={
            "symbol": "AAPL",
            "snapshot_time": "2026-01-10T00:00:00Z",
            "market_structure": {"wyckoff_regime": "MARKUP", "regime_confidence": 0.7},
        },
        option_context={
            "option_chain_snapshot": option_chain_snapshot,
            "option_selection_constraints": option_selection_constraints,
        },
        authority_constraints={},
        instructions={},
        prompt_version="test",
    )

    payload = _extract_injected_payload(prompt_text)
    assert payload["option_chain_snapshot"] == option_chain_snapshot
    assert payload["option_selection_constraints"] == option_selection_constraints
    assert isinstance(payload["option_chain_hash"], str)
    assert len(payload["option_chain_hash"]) == 64


def test_prompt_missing_option_chain_snapshot_fails() -> None:
    with pytest.raises(ValueError, match="option_chain_snapshot_missing"):
        build_prompt(
            snapshot_payload={"symbol": "AAPL", "snapshot_time": "2026-01-10T00:00:00Z"},
            option_context={},
            authority_constraints={},
            instructions={},
            prompt_version="test",
        )
