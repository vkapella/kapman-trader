import json
import logging
import os
from typing import Any, Dict

from .prompt_loader import load_prompt
from .response_parser import register_option_chain_snapshot

logger = logging.getLogger("kapman.ai.prompt_builder")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _format_json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _coerce_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _claimed_context(snapshot_payload: dict) -> Dict[str, Any]:
    market_structure = snapshot_payload.get("market_structure") if isinstance(snapshot_payload, dict) else {}
    if not isinstance(market_structure, dict):
        market_structure = {}
    regime = snapshot_payload.get("wyckoff_regime") or market_structure.get("wyckoff_regime") or "UNKNOWN"
    confidence = (
        snapshot_payload.get("wyckoff_confidence")
        or snapshot_payload.get("regime_confidence")
        or market_structure.get("regime_confidence")
        or 0.0
    )
    return {
        "wyckoff_regime": str(regime),
        "confidence_provided": _coerce_float(confidence, 0.0),
    }


def _request_payload(
    *,
    snapshot_payload: dict,
    option_context: dict,
    option_chain_snapshot: Any,
    option_selection_constraints: Any,
    authority_constraints: dict,
    instructions: dict,
    prompt_version: str,
    option_chain_hash: str,
    claimed_context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "prompt_version": prompt_version,
        "claimed_context": claimed_context,
        "snapshot_payload": snapshot_payload,
        "option_context": option_context,
        "option_chain_snapshot": option_chain_snapshot,
        "option_selection_constraints": option_selection_constraints,
        "authority_constraints": authority_constraints,
        "instructions": instructions,
        "option_chain_hash": option_chain_hash,
    }

SYSTEM_PROMPT_TEMPLATE = load_prompt("system/wyckoff_context_evaluator.v1.system.md")
USER_PROMPT_TEMPLATE = load_prompt("user/wyckoff_context_evaluator.v1.user.md")
SYSTEM_MARKER = "<<<SYSTEM_PROMPT>>>"
USER_MARKER = "<<<USER_PROMPT>>>"


def build_prompt(
    *,
    snapshot_payload: dict,
    option_context: dict,
    authority_constraints: dict,
    instructions: dict,
    prompt_version: str,
) -> str:
    option_chain_snapshot = {}
    if isinstance(option_context, dict):
        option_chain_snapshot = option_context.get("option_chain_snapshot") or {}
    if not option_chain_snapshot and isinstance(snapshot_payload, dict):
        option_chain_snapshot = snapshot_payload.get("option_chain_snapshot") or {}
    if not option_chain_snapshot:
        raise ValueError("option_chain_snapshot_missing")

    option_selection_constraints = {}
    if isinstance(option_context, dict):
        option_selection_constraints = option_context.get("option_selection_constraints") or {}

    claimed_context = _claimed_context(snapshot_payload)
    option_chain_hash, contract_count = register_option_chain_snapshot(option_chain_snapshot)
    payload = _request_payload(
        snapshot_payload=snapshot_payload,
        option_context=option_context,
        option_chain_snapshot=option_chain_snapshot,
        option_selection_constraints=option_selection_constraints,
        authority_constraints=authority_constraints,
        instructions=instructions,
        prompt_version=prompt_version,
        option_chain_hash=option_chain_hash,
        claimed_context=claimed_context,
    )
    payload_json = _canonical_json(payload)
    user_prompt = USER_PROMPT_TEMPLATE
    user_prompt = user_prompt.replace("{{WYCKOFF_REGIME}}", claimed_context["wyckoff_regime"])
    user_prompt = user_prompt.replace("{{WYCKOFF_CONFIDENCE}}", _format_json_value(claimed_context["confidence_provided"]))
    user_prompt = user_prompt.replace("{{INJECTED_CONTEXT_JSON}}", payload_json)
    prompt_text = "\n".join(
        [
            SYSTEM_MARKER,
            SYSTEM_PROMPT_TEMPLATE.strip(),
            USER_MARKER,
            user_prompt.strip(),
        ]
    )
    logger.info(
        _canonical_json(
            {
                "event": "option_chain_hash",
                "hash": option_chain_hash,
                "contract_count": contract_count,
            }
        )
    )
    if os.getenv("AI_DUMP") == "1":
        snapshot_payload = snapshot_payload if isinstance(snapshot_payload, dict) else {}
        payload = {
            "event": "ai_prompt_dump",
            "ticker": snapshot_payload.get("symbol") or snapshot_payload.get("ticker"),
            "prompt": prompt_text,
        }
        logger.info("[AI_DUMP] " + json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
    return prompt_text
