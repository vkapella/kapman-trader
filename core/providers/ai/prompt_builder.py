import json
import logging
import os
from typing import Any, Dict

from .prompt_loader import load_prompt

logger = logging.getLogger("kapman.ai.prompt_builder")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _request_payload(
    *,
    snapshot_payload: dict,
    option_context: dict,
    authority_constraints: dict,
    instructions: dict,
    prompt_version: str,
) -> Dict[str, Any]:
    return {
        "prompt_version": prompt_version,
        "snapshot_payload": snapshot_payload,
        "option_context": option_context,
        "authority_constraints": authority_constraints,
        "instructions": instructions,
    }


PROMPT_TEMPLATE = load_prompt("c4_recommendation_prompt.txt")


def build_prompt(
    *,
    snapshot_payload: dict,
    option_context: dict,
    authority_constraints: dict,
    instructions: dict,
    prompt_version: str,
) -> str:
    payload = _request_payload(
        snapshot_payload=snapshot_payload,
        option_context=option_context,
        authority_constraints=authority_constraints,
        instructions=instructions,
        prompt_version=prompt_version,
    )
    payload_json = _canonical_json(payload)
    prompt_text = "\n".join(
        [
            PROMPT_TEMPLATE,
            "You MUST return exactly one recommendation.",
            "If no trade is appropriate, return action = HOLD with rationale.",
            "CONTEXT:",
            payload_json,
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
