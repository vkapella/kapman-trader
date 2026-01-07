import json

from core.providers.ai.response_parser import normalize_agent_response


def _build_valid_response() -> dict:
    return {
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
                "stop_loss": "-50% premium",
                "profit_target": "+100% premium",
            },
            "alternatives": [],
        },
        "confidence_summary": {"score": 0.6},
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

    assert response["context_evaluation"]["status"] == "ACCEPTED"
    assert response["option_recommendations"]["primary"]["option_type"] == "CALL"
