import json

from core.providers.ai.response_parser import normalize_agent_response


def _minimal_valid_response() -> dict:
    return {
        "snapshot_metadata": {
            "ticker": "AAPL",
            "snapshot_time": "2026-01-10T00:00:00+00:00",
        },
        "context_evaluation": {
            "status": "REJECTED",
            "failure_type": "CONTEXT_REJECTED",
            "reason": "Evidence is insufficient.",
        },
        "option_recommendations": {
            "primary": None,
            "alternatives": [],
        },
        "confidence_summary": {"score": 0.2},
    }


def test_ai_dump_logging_flag_does_not_change_behavior(monkeypatch) -> None:
    raw_response = json.dumps(_minimal_valid_response())

    monkeypatch.delenv("AI_DUMP", raising=False)
    result_without = normalize_agent_response(
        raw_response=raw_response,
        provider_id="openai",
        model_id="gpt-5-mini",
        prompt_version="test",
        kapman_model_version="test",
    )

    monkeypatch.setenv("AI_DUMP", "1")
    result_with = normalize_agent_response(
        raw_response=raw_response,
        provider_id="openai",
        model_id="gpt-5-mini",
        prompt_version="test",
        kapman_model_version="test",
    )

    assert result_with == result_without
