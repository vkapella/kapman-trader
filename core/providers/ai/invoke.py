import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, Tuple

from core.providers.ai.claude import ClaudeProvider
from core.providers.ai.openai import OpenAIProvider
from core.providers.ai.prompt_builder import build_prompt
from core.providers.ai.response_parser import (
    STANDARD_GUARDRAILS,
    _parse_raw_response,
    _validate_candidate,
    normalize_agent_response,
)

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


def _first_present(mapping: Dict[str, Any], keys: Tuple[str, ...], default: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return str(value)
    return default


def _build_stub_response(
    *,
    snapshot_payload: dict,
    provider_id: str,
    model_id: str,
    prompt_version: str,
    kapman_model_version: str,
) -> Dict[str, Any]:
    market_structure = snapshot_payload.get("market_structure", {}) if isinstance(snapshot_payload, dict) else {}
    wyckoff_events = market_structure.get("wyckoff_events", [])
    primary_event = wyckoff_events[0] if isinstance(wyckoff_events, list) and wyckoff_events else "NONE"
    snapshot_metadata = {
        "ticker": _first_present(snapshot_payload, ("symbol", "ticker"), "UNKNOWN"),
        "snapshot_time": _first_present(snapshot_payload, ("snapshot_time", "time"), "UNKNOWN"),
        "model_version": prompt_version,
        "wyckoff_regime": _first_present(
            snapshot_payload,
            ("wyckoff_regime",),
            _first_present(market_structure, ("wyckoff_regime",), "UNKNOWN"),
        ),
        "wyckoff_primary_event": _first_present(
            snapshot_payload,
            ("wyckoff_primary_event",),
            primary_event,
        ),
        "data_completeness_flags": snapshot_payload.get("data_completeness_flags", {}),
        "ai_provider": provider_id,
        "ai_model": model_id,
        "ai_model_version": None,
        "kapman_model_version": kapman_model_version,
    }
    return {
        "snapshot_metadata": snapshot_metadata,
        "primary_recommendation": {
            "action": "NO_TRADE",
            "strategy_class": "NONE",
            "direction": "NEUTRAL",
            "confidence_score": 75,
            "time_horizon": "medium",
            "rationale_summary": "Dry-run stub response.",
        },
        "alternative_recommendations": [
            {
                "label": "Re-run with live provider",
                "action": "WAIT",
                "strategy_class": "NONE",
                "direction": "NEUTRAL",
                "confidence_score": 50,
                "blocking_reason": "Dry-run mode enabled.",
                "promotion_conditions": "Disable dry-run and re-run.",
            }
        ],
        "reasoning_trace": {
            "fired_rules": [],
            "cluster_contributions": [{"cluster": "Meta", "impact": "DRY_RUN"}],
            "supporting_factors": [],
            "blocking_factors": ["Dry-run mode enabled."],
        },
        "confidence_summary": {
            "confidence_type": "RELATIVE",
            "ranking_basis": "Primary outranks alternatives by construction",
            "confidence_gap_notes": None,
        },
        "missing_data_declaration": ["Dry-run stub response."],
        "guardrails_and_disclaimers": list(STANDARD_GUARDRAILS),
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
    provider_key = provider_id.lower()
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
        raw_response: Any = {"_error": f"Unknown provider: {provider_key}"}
    elif not model_id:
        raw_response = {"_error": "Missing model_id"}
    elif dry_run:
        raw_response = _build_stub_response(
            snapshot_payload=snapshot_payload,
            provider_id=provider_key,
            model_id=model_id,
            prompt_version=prompt_version,
            kapman_model_version=kapman_model_version,
        )
    else:
        try:
            raw_response = asyncio.run(_invoke_provider(provider_key, model_id, prompt_text))
        except Exception as exc:
            raw_response = {"_error": f"Provider invocation failed: {exc}"}

    if debug:
        _log_event(invocation_id, "raw_response", {"raw_response": raw_response})
        candidate, parse_error = _parse_raw_response(raw_response)
        if parse_error:
            validation_status = {"status": "FAIL", "reason": parse_error}
        else:
            valid, reason = _validate_candidate(candidate)
            validation_status = {"status": "PASS" if valid else "FAIL", "reason": reason}
        _log_event(invocation_id, "schema_validation", validation_status)

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
