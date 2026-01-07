import json

import pytest

from core.providers.ai.response_parser import normalize_agent_response


def test_schema_validation_fails_on_missing_fields() -> None:
    response = {
        "confidence_score": 0.6,
        "metric_assessment": {"supporting": [], "contradicting": [], "neutral": []},
        "metric_weights": {},
        "discarded_metrics": [],
        "conditional_recommendation": {
            "direction": "NEUTRAL",
            "action": "HOLD",
            "option_type": None,
            "option_strategy": None,
        },
    }

    with pytest.raises(ValueError, match="Missing top-level key"):
        normalize_agent_response(
            raw_response=json.dumps(response),
            provider_id="openai",
            model_id="gpt-5-mini",
            prompt_version="test",
            kapman_model_version="test",
        )


def test_parser_rejects_invalid_json() -> None:
    with pytest.raises(ValueError, match="Invalid JSON"):
        normalize_agent_response(
            raw_response="not json",
            provider_id="openai",
            model_id="gpt-5-mini",
            prompt_version="test",
            kapman_model_version="test",
        )
