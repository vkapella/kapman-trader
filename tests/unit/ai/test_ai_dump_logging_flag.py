import json

from core.providers.ai.response_parser import normalize_agent_response


def _minimal_valid_response() -> dict:
    return {
        "context_label": "UNKNOWN",
        "confidence_score": 0.2,
        "metric_assessment": {"supporting": [], "contradicting": [], "neutral": []},
        "metric_weights": {},
        "discarded_metrics": ["insufficient_data"],
        "conditional_recommendation": {
            "direction": "NEUTRAL",
            "action": "HOLD",
            "option_type": None,
            "option_strategy": None,
        },
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
