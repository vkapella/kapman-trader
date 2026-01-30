import json

from core.providers.ai.response_parser import normalize_agent_response


def _build_base_response(metric_weights):
    return {
        "context_label": "MARKUP",
        "confidence_score": 0.6,
        "metric_assessment": {
            "supporting": ["wyckoff_regime", "bc_score"],
            "contradicting": [],
            "neutral": ["volatility_metrics_json"],
        },
        "metric_weights": metric_weights,
        "discarded_metrics": ["duplicate_metric"],
        "conditional_recommendation": {
            "direction": "LONG",
            "action": "PROCEED",
            "option_type": None,
            "option_strategy": None,
        },
    }


def test_normalize_agent_response_accepts_dict_metric_weights() -> None:
    weights = {"wyckoff_regime": 0.4, "bc_score": 0.2}
    raw_response = json.dumps(_build_base_response(weights))

    response = normalize_agent_response(
        raw_response=raw_response,
        provider_id="openai",
        model_id="gpt-5",
        prompt_version="test",
        kapman_model_version="wyckoff-context@test",
    )

    assert response["metric_weights"] == weights


def test_normalize_agent_response_converts_list_metric_weights_to_dict() -> None:
    weights_list = [
        {"metric": "rsi", "weight": 0.7},
        {"metric": "macd", "weight": 0.3},
    ]
    raw_response = json.dumps(_build_base_response(weights_list))

    response = normalize_agent_response(
        raw_response=raw_response,
        provider_id="openai",
        model_id="gpt-5",
        prompt_version="test",
        kapman_model_version="wyckoff-context@test",
    )

    assert response["metric_weights"] == {"rsi": 0.7, "macd": 0.3}


def test_normalize_agent_response_ignores_invalid_list_items() -> None:
    weights_list = [
        {"metric": "rsi", "weight": 0.7},
        "bad",
        {"metric": ""},
        {"weight": 0.1},
        {"metric": "macd", "weight": "0.3"},
        {"metric": "bool", "weight": True},
        {"metric": "adx", "weight": 0.2},
    ]
    raw_response = json.dumps(_build_base_response(weights_list))

    response = normalize_agent_response(
        raw_response=raw_response,
        provider_id="openai",
        model_id="gpt-5",
        prompt_version="test",
        kapman_model_version="wyckoff-context@test",
    )

    assert response["metric_weights"] == {"rsi": 0.7, "adx": 0.2}
