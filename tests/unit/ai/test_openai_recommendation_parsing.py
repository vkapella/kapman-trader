from core.providers.ai.response_parser import normalize_agent_response


def test_no_trade_recommendation_parsing() -> None:
    raw_response = {
        "action": "NO_TRADE",
        "confidence": 0.5,
        "rationale": "Insufficient setup quality.",
    }

    response = normalize_agent_response(
        raw_response=raw_response,
        provider_id="openai",
        model_id="gpt-5-mini",
        prompt_version="test",
        kapman_model_version="test",
    )

    primary = response["primary_recommendation"]
    assert primary["action"] == "NO_TRADE"
    assert primary["confidence_score"] == 50
    assert response["alternative_recommendations"] == []
