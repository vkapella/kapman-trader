import argparse
import json
import logging
import sys
from pathlib import Path


def _add_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))


def _build_snapshot_payload() -> dict:
    return {
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
        "data_completeness_flags": {
            "technical_summary": "COMPUTED",
            "volatility_summary": "COMPUTED",
            "dealer_summary": "COMPUTED",
        },
    }


def _build_option_context() -> dict:
    return {
        "spot_price": 185.2,
        "expiration_buckets": ["short", "medium"],
        "moneyness_bands": ["ATM", "slightly_OTM"],
        "liquidity_constraints": {"min_open_interest": 500, "min_volume": 100},
    }


def _build_authority_constraints() -> dict:
    return {
        "wyckoff_veto": False,
        "iv_forbids_long_premium": False,
        "dealer_timing_veto": False,
    }


def _build_instructions() -> dict:
    return {
        "objective": "produce ranked trade recommendations",
        "forbidden_actions": [
            "assume strike existence",
            "assume expiration existence",
            "claim executability",
        ],
    }


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
    from core.providers.ai.invoke import invoke_planning_agent

    response = invoke_planning_agent(
        provider_id=args.provider,
        model_id=args.model,
        snapshot_payload=_build_snapshot_payload(),
        option_context=_build_option_context(),
        authority_constraints=_build_authority_constraints(),
        instructions=_build_instructions(),
        prompt_version="dev-runner-v1",
        kapman_model_version="dev-runner",
        debug=args.debug,
        dry_run=args.dry_run,
    )
    print(json.dumps(response, sort_keys=True, ensure_ascii=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
