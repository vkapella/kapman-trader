import json

from core.providers.ai.response_parser import normalize_agent_response


def test_schema_validation_fails_on_missing_primary_fields() -> None:
    response = {
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
            },
            "alternatives": [],
        },
        "confidence_summary": {"score": 0.6},
    }

    normalized = normalize_agent_response(
        raw_response=json.dumps(response),
        provider_id="openai",
        model_id="gpt-5-mini",
        prompt_version="test",
        kapman_model_version="test",
    )

    assert normalized["context_evaluation"]["status"] == "REJECTED"
    assert normalized["context_evaluation"]["failure_type"] == "SCHEMA_FAIL"
    assert normalized["option_recommendations"]["primary"] is None


def test_parser_rejects_invalid_json() -> None:
    normalized = normalize_agent_response(
        raw_response="not json",
        provider_id="openai",
        model_id="gpt-5-mini",
        prompt_version="test",
        kapman_model_version="test",
    )

    assert normalized["context_evaluation"]["status"] == "REJECTED"
    assert normalized["context_evaluation"]["failure_type"] == "SCHEMA_FAIL"
    assert normalized["option_recommendations"]["primary"] is None
