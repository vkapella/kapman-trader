import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path


def _add_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))


def _build_request_payload() -> dict:
    return {
        "context": {
            "symbol": "AAPL",
            "snapshot_time": "2025-01-15",
            "market_structure": {
                "wyckoff_regime": "MARKUP",
                "wyckoff_events": ["SOS"],
                "regime_confidence": 0.82,
            },
            "technical_summary": {"adx": 28, "momentum_slope": 0.4},
            "volatility_summary": {"iv_rank": 55, "iv_regime": "MID"},
            "dealer_summary": {"gamma_flip_level": 182.5, "net_gex": 1000000},
        },
        "option_context": {
            "spot_price": 185.2,
            "expiration_buckets": ["short", "medium"],
            "moneyness_bands": ["ATM", "slightly_OTM"],
            "liquidity_constraints": {"min_open_interest": 500, "min_volume": 100},
        },
        "authority_constraints": {
            "wyckoff_veto": False,
            "iv_forbids_long_premium": False,
            "dealer_timing_veto": False,
        },
        "instructions": {
            "objective": "produce ranked trade recommendations",
            "forbidden_actions": [
                "assume strike existence",
                "assume expiration existence",
                "claim executability",
            ],
        },
    }


def _model_dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return value


async def _run(args: argparse.Namespace) -> None:
    from core.providers.ai.base import invoke_planning_agent

    request_payload = _build_request_payload()
    invocation_config = {
        "ai_debug": args.debug,
        "ai_dry_run": args.dry_run,
        "model_version": "dev-runner",
    }
    response = await invoke_planning_agent(
        provider_id=args.provider,
        model_id=args.model,
        request_payload=request_payload,
        invocation_config=invocation_config,
    )
    payload = _model_dump(response)
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Slice C AI dev runner")
    parser.add_argument("--provider", choices=["anthropic", "openai"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.INFO)

    _add_repo_root()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
