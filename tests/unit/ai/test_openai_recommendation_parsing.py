import json

from core.providers.ai.response_parser import normalize_agent_response


def _build_valid_response() -> dict:
    return {
        "context_label": "MARKUP",
        "confidence_score": 0.6,
        "metric_assessment": {
            "supporting": ["wyckoff_regime", "bc_score"],
            "contradicting": [],
            "neutral": ["volatility_metrics_json"],
        },
        "metric_weights": {"wyckoff_regime": 0.4, "bc_score": 0.2, "volatility_metrics_json": 0.1},
        "discarded_metrics": ["duplicate_metric"],
        "conditional_recommendation": {
            "direction": "LONG",
            "action": "PROCEED",
            "option_type": None,
            "option_strategy": None,
        },
    }


def test_context_evaluation_parsing_accepts_valid_contracts() -> None:
    raw_response = json.dumps(_build_valid_response())

    response = normalize_agent_response(
        raw_response=raw_response,
        provider_id="openai",
        model_id="gpt-5-mini",
        prompt_version="test",
        kapman_model_version="test",
    )

    assert response["context_label"] == "MARKUP"
    assert response["conditional_recommendation"]["direction"] == "LONG"
