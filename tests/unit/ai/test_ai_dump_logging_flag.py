from core.providers.ai.response_parser import normalize_agent_response


def test_ai_dump_logging_flag_does_not_change_behavior(monkeypatch) -> None:
    raw_response = {
        "action": "HOLD",
        "confidence": 0.5,
        "rationale": "Stand aside.",
    }

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
