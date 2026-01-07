import asyncio
import hashlib
import json
import logging
from typing import Any, Dict

from core.providers.ai.claude import ClaudeProvider
from core.providers.ai.openai import OpenAIProvider
from core.providers.ai.prompt_builder import build_prompt
from core.providers.ai.response_parser import normalize_agent_response

logger = logging.getLogger("kapman.ai.c1")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _canonical_request_payload(
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


def _invocation_id(request_payload_json: str, provider_id: str, model_id: str) -> str:
    seed = f"{provider_id}:{model_id}:{request_payload_json}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return digest[:12]


def _log_event(invocation_id: str, event: str, payload: Dict[str, Any]) -> None:
    entry = {"event": event, "invocation_id": invocation_id}
    entry.update(payload)
    logger.info(_canonical_json(entry))


def _context_label_from_payload(snapshot_payload: dict) -> str:
    if not isinstance(snapshot_payload, dict):
        return "UNKNOWN"
    daily_snapshot = snapshot_payload.get("daily_snapshot")
    if isinstance(daily_snapshot, dict):
        regime = daily_snapshot.get("wyckoff_regime")
        if isinstance(regime, str) and regime:
            return regime
    regime = snapshot_payload.get("wyckoff_regime")
    if isinstance(regime, str) and regime:
        return regime
    return "UNKNOWN"


def _build_stub_response(*, snapshot_payload: dict) -> Dict[str, Any]:
    return {
        "context_label": _context_label_from_payload(snapshot_payload),
        "confidence_score": 0.0,
        "metric_assessment": {"supporting": [], "contradicting": [], "neutral": []},
        "metric_weights": {},
        "discarded_metrics": ["dry_run"],
        "conditional_recommendation": {
            "direction": "NEUTRAL",
            "action": "HOLD",
            "option_type": None,
            "option_strategy": None,
        },
    }


async def _invoke_provider(provider_id: str, model_id: str, prompt_text: str) -> str:
    if provider_id == "anthropic":
        provider = ClaudeProvider()
    elif provider_id == "openai":
        provider = OpenAIProvider()
    else:
        raise ValueError(f"Unknown provider: {provider_id}")
    response = await provider.invoke(model_id=model_id, system_prompt="", user_prompt=prompt_text)
    return response.content


def invoke_planning_agent(
    *,
    provider_id: str,
    model_id: str,
    snapshot_payload: dict,
    option_context: dict,
    authority_constraints: dict,
    instructions: dict,
    prompt_version: str,
    kapman_model_version: str,
    debug: bool = False,
    dry_run: bool = False,
) -> dict:
    provider_key = str(provider_id or "").lower()
    request_payload = _canonical_request_payload(
        snapshot_payload=snapshot_payload,
        option_context=option_context,
        authority_constraints=authority_constraints,
        instructions=instructions,
        prompt_version=prompt_version,
    )
    request_payload_json = _canonical_json(request_payload)
    invocation_id = _invocation_id(request_payload_json, provider_key, model_id)
    prompt_text = build_prompt(
        snapshot_payload=snapshot_payload,
        option_context=option_context,
        authority_constraints=authority_constraints,
        instructions=instructions,
        prompt_version=prompt_version,
    )

    if debug:
        _log_event(invocation_id, "snapshot_payload", {"snapshot_payload": snapshot_payload})
        _log_event(invocation_id, "option_context", {"option_context": option_context})
        _log_event(invocation_id, "authority_constraints", {"authority_constraints": authority_constraints})
        _log_event(invocation_id, "request_payload", {"request_payload": request_payload})
        _log_event(invocation_id, "prompt_text", {"prompt_text": prompt_text})
        _log_event(invocation_id, "provider_selection", {"provider_id": provider_key, "model_id": model_id})

    if provider_key not in {"anthropic", "openai"}:
        raise ValueError(f"Unknown provider: {provider_key}")
    if not model_id:
        raise ValueError("Missing model_id")

    if dry_run:
        normalized = _build_stub_response(snapshot_payload=snapshot_payload)
        if debug:
            _log_event(invocation_id, "normalized_response", {"normalized_response": normalized})
        return normalized

    try:
        raw_response = asyncio.run(_invoke_provider(provider_key, model_id, prompt_text))
    except Exception as exc:
        reason = f"Provider invocation failed: {type(exc).__name__}: {exc}"
        raise RuntimeError(reason) from exc

    if debug:
        _log_event(invocation_id, "raw_response", {"raw_response": raw_response})

    normalized = normalize_agent_response(
        raw_response=raw_response,
        provider_id=provider_key,
        model_id=model_id,
        prompt_version=prompt_version,
        kapman_model_version=kapman_model_version,
    )

    if debug:
        _log_event(invocation_id, "normalized_response", {"normalized_response": normalized})

    return normalized
