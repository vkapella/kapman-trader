import json
import logging
import os
from typing import Any, Dict

from .prompt_loader import load_prompt

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
    if not isinstance(snapshot_payload, dict):
        return {"wyckoff_regime": "UNKNOWN", "confidence_provided": 0.0}
    daily_snapshot = snapshot_payload.get("daily_snapshot")
    if not isinstance(daily_snapshot, dict):
        daily_snapshot = {}
    regime = daily_snapshot.get("wyckoff_regime") or snapshot_payload.get("wyckoff_regime") or "UNKNOWN"
    confidence = (
        daily_snapshot.get("wyckoff_regime_confidence")
        or snapshot_payload.get("wyckoff_regime_confidence")
        or snapshot_payload.get("wyckoff_confidence")
        or 0.0
    )
    return {
        "wyckoff_regime": str(regime),
        "confidence_provided": _coerce_float(confidence, 0.0),
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
    claimed_context = _claimed_context(snapshot_payload)
    payload_json = _canonical_json(snapshot_payload)
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
    if os.getenv("AI_DUMP") == "1":
        snapshot_payload = snapshot_payload if isinstance(snapshot_payload, dict) else {}
        payload = {
            "event": "ai_prompt_dump",
            "ticker": snapshot_payload.get("symbol") or snapshot_payload.get("ticker"),
            "prompt": prompt_text,
        }
        logger.info("[AI_DUMP] " + json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
    return prompt_text
