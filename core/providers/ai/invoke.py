import asyncio
import hashlib
import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple

from core.providers.ai.claude import ClaudeProvider
from core.providers.ai.openai import OpenAIProvider
from core.providers.ai.prompt_builder import build_prompt
from core.providers.ai.response_parser import (
    STANDARD_GUARDRAILS,
    _failure_response,
    _parse_raw_response,
    _validate_candidate,
    normalize_agent_response,
)
from core.ingestion.options.db import connect as options_db_connect
from core.ingestion.options.db import default_db_url

logger = logging.getLogger("kapman.ai.c1")

_STRIKE_KEYS = ("option_strike", "strike", "strike_price")
_EXPIRATION_KEYS = ("option_expiration", "expiration", "expiry", "expiration_date", "exp_date")
_OPTION_TYPE_KEYS = ("option_type", "type", "contract_type")
_STRIKE_QUANT = Decimal("0.0001")


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


def _first_value(mapping: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    for key in keys:
        if key in mapping:
            value = mapping.get(key)
            if value is not None:
                return value
    return None


def _parse_snapshot_time(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _parse_expiration(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            if "T" in text:
                return datetime.fromisoformat(text).date()
            return date.fromisoformat(text)
        except ValueError:
            return None
    return None


def _parse_strike(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(_STRIKE_QUANT)
    except (InvalidOperation, ValueError):
        return None


def _normalize_option_type(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in {"C", "CALL"}:
        return "C"
    if text in {"P", "PUT"}:
        return "P"
    return None


def _extract_contract_fields(source: Any) -> tuple[Optional[tuple[date, Decimal, str]], Optional[str]]:
    if not isinstance(source, dict):
        return None, None
    strike_raw = _first_value(source, _STRIKE_KEYS)
    expiration_raw = _first_value(source, _EXPIRATION_KEYS)
    option_type_raw = _first_value(source, _OPTION_TYPE_KEYS)

    if strike_raw is None and expiration_raw is None and option_type_raw is None:
        return None, None
    if strike_raw is None or expiration_raw is None or option_type_raw is None:
        return None, "missing_contract_fields"

    strike = _parse_strike(strike_raw)
    expiration = _parse_expiration(expiration_raw)
    option_type = _normalize_option_type(option_type_raw)

    if strike is None or expiration is None or option_type is None:
        return None, "invalid_contract_fields"

    return (expiration, strike, option_type), None


def _collect_recommendation_contracts(recommendation: Any) -> tuple[list[tuple[date, Decimal, str]], list[str]]:
    if not isinstance(recommendation, dict):
        return [], []
    contracts: list[tuple[date, Decimal, str]] = []
    errors: list[str] = []

    def _add_contract(source: Any) -> None:
        contract, error = _extract_contract_fields(source)
        if contract:
            contracts.append(contract)
        if error:
            errors.append(error)

    _add_contract(recommendation)
    _add_contract(recommendation.get("primary_leg"))
    _add_contract(recommendation.get("secondary_leg"))

    legs = recommendation.get("legs") or recommendation.get("option_legs")
    if isinstance(legs, list):
        for leg in legs:
            _add_contract(leg)

    return contracts, errors


def _load_option_chain_context(snapshot_payload: dict) -> tuple[set[date], set[tuple[date, Decimal, str]], datetime]:
    if not isinstance(snapshot_payload, dict):
        raise ValueError("snapshot_payload_missing")
    symbol = snapshot_payload.get("symbol") or snapshot_payload.get("ticker")
    snapshot_time = _parse_snapshot_time(snapshot_payload.get("snapshot_time") or snapshot_payload.get("time"))
    if not symbol or not snapshot_time:
        raise ValueError("snapshot_identity_missing")

    db_url = default_db_url()
    with options_db_connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tickers WHERE UPPER(symbol) = UPPER(%s) LIMIT 1", (symbol,))
            row = cur.fetchone()
        if not row:
            raise ValueError("ticker_not_found")
        ticker_id = row[0]
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT MAX(time)
                FROM options_chains
                WHERE ticker_id = %s
                  AND time <= %s
                """,
                (ticker_id, snapshot_time),
            )
            row = cur.fetchone()
        if not row or row[0] is None:
            raise ValueError("options_chains_unavailable")
        options_time = row[0]

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT expiration_date, strike_price, option_type
                FROM options_chains
                WHERE ticker_id = %s AND time = %s
                """,
                (ticker_id, options_time),
            )
            rows = cur.fetchall()

    expirations: set[date] = set()
    contracts: set[tuple[date, Decimal, str]] = set()
    for expiration, strike_raw, option_type in rows:
        if expiration is None or strike_raw is None or option_type is None:
            continue
        strike = _parse_strike(strike_raw)
        option_type_norm = _normalize_option_type(option_type)
        if strike is None or option_type_norm is None:
            continue
        expirations.add(expiration)
        contracts.add((expiration, strike, option_type_norm))

    if not contracts:
        raise ValueError("options_chains_empty")

    return expirations, contracts, options_time


def _validate_option_recommendations(
    *,
    response: dict,
    snapshot_payload: dict,
    provider_id: str,
    model_id: str,
    prompt_version: str,
    kapman_model_version: str,
    invocation_id: str,
) -> dict:
    snapshot_metadata = response.get("snapshot_metadata") or {}
    if snapshot_metadata.get("ticker") == "UNKNOWN":
        return response

    primary = response.get("primary_recommendation") or {}
    alternatives = response.get("alternative_recommendations") or []

    primary_contracts, primary_errors = _collect_recommendation_contracts(primary)
    alternatives_info: list[tuple[int, dict, list[tuple[date, Decimal, str]], list[str]]] = []
    should_validate = bool(primary_contracts or primary_errors)

    for idx, alt in enumerate(alternatives):
        contracts, errors = _collect_recommendation_contracts(alt)
        if contracts or errors:
            should_validate = True
        alternatives_info.append((idx, alt, contracts, errors))

    if not should_validate:
        return response

    try:
        valid_expirations, valid_contracts, options_time = _load_option_chain_context(snapshot_payload)
    except Exception as exc:
        reason = f"Option validation failed: {exc}"
        return _failure_response(
            reason=reason,
            provider_id=provider_id,
            model_id=model_id,
            prompt_version=prompt_version,
            kapman_model_version=kapman_model_version,
        )

    def _contract_errors(contracts: list[tuple[date, Decimal, str]]) -> list[str]:
        errors: list[str] = []
        for expiration, strike, option_type in contracts:
            if expiration not in valid_expirations:
                errors.append("invalid_expiration")
                continue
            if (expiration, strike, option_type) not in valid_contracts:
                errors.append("invalid_strike")
        return errors

    primary_validation_errors = list(primary_errors)
    if primary_contracts:
        primary_validation_errors.extend(_contract_errors(primary_contracts))
    if primary_validation_errors:
        _log_event(
            invocation_id,
            "option_validation_drop",
            {
                "role": "primary",
                "errors": primary_validation_errors,
                "options_time": options_time.isoformat(),
            },
        )
        reason = f"Invalid option contract in primary recommendation: {sorted(set(primary_validation_errors))}"
        return _failure_response(
            reason=reason,
            provider_id=provider_id,
            model_id=model_id,
            prompt_version=prompt_version,
            kapman_model_version=kapman_model_version,
        )

    filtered_alternatives: list[dict] = []
    for idx, alt, contracts, errors in alternatives_info:
        validation_errors = list(errors)
        if contracts:
            validation_errors.extend(_contract_errors(contracts))
        if validation_errors:
            _log_event(
                invocation_id,
                "option_validation_drop",
                {
                    "role": "alternative",
                    "index": idx,
                    "errors": validation_errors,
                    "options_time": options_time.isoformat(),
                },
            )
            continue
        filtered_alternatives.append(alt)

    response["alternative_recommendations"] = filtered_alternatives
    return response


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
            reason = f"Provider invocation failed: {type(exc).__name__}: {exc}"
            status_code = getattr(exc, "status_code", None)
            response_text = getattr(exc, "response_text", None)
            request_id = getattr(exc, "request_id", None)
            if status_code is not None:
                reason = f"{reason} (status_code={status_code})"
            if response_text:
                reason = f"{reason} (response_text={response_text})"
            if request_id:
                reason = f"{reason} (request_id={request_id})"
            raw_response = {"_error": reason}

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

    normalized = _validate_option_recommendations(
        response=normalized,
        snapshot_payload=snapshot_payload,
        provider_id=provider_key,
        model_id=model_id,
        prompt_version=prompt_version,
        kapman_model_version=kapman_model_version,
        invocation_id=invocation_id,
    )

    if debug:
        _log_event(invocation_id, "normalized_response", {"normalized_response": normalized})

    return normalized
