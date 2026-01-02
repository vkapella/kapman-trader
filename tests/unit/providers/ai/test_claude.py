import pytest

from core.providers.ai.base import (
    AIRequest,
    invoke_planning_agent,
)


@pytest.mark.asyncio
async def test_invoke_planning_agent_dry_run():
    request = AIRequest(
        context={
            "symbol": "AAPL",
            "snapshot_time": "2025-01-15",
            "market_structure": {
                "wyckoff_regime": "MARKUP",
                "wyckoff_events": ["SOS"],
                "regime_confidence": 0.82,
            },
            "technical_summary": {"adx": 28},
            "volatility_summary": {"iv_rank": 85},
            "dealer_summary": {},
        },
        option_context={
            "spot_price": 185.5,
            "expiration_buckets": ["short", "medium"],
            "moneyness_bands": ["ATM", "slightly_OTM"],
            "liquidity_constraints": {"min_open_interest": 500, "min_volume": 100},
        },
        authority_constraints={
            "wyckoff_veto": False,
            "iv_forbids_long_premium": True,
            "dealer_timing_veto": False,
        },
        instructions={
            "objective": "produce ranked trade recommendations",
            "forbidden_actions": [
                "assume strike existence",
                "assume expiration existence",
                "claim executability",
            ],
        },
    )

    output = await invoke_planning_agent(
        provider_id="anthropic",
        model_id="claude-sonnet-4-20250514",
        request_payload=request,
        invocation_config={
            "ai_debug": False,
            "ai_dry_run": True,
            "model_version": "test-version",
        },
    )

    assert output.snapshot_metadata.ticker == "AAPL"
    assert output.snapshot_metadata.ai_provider == "anthropic"
    assert output.primary_recommendation.action.value in {"NO_TRADE", "WAIT"}
    assert output.guardrails_and_disclaimers
    assert output.missing_data_declaration
