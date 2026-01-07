import hashlib
import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple


STANDARD_GUARDRAILS = [
    "This recommendation is rule-based, not predictive.",
    "It is conditioned only on computed inputs.",
    "It does not guarantee execution, fills, or outcomes.",
    "It does not replace position sizing or risk controls.",
    "It reflects current conditions only.",
]

logger = logging.getLogger("kapman.ai.response_parser")

_OPTION_CHAIN_REGISTRY: dict[str, set[tuple[str, Decimal, str]]] = {}
_STRIKE_QUANT = Decimal("0.0001")


def _ai_dump_enabled() -> bool:
    return os.getenv("AI_DUMP") == "1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def extract_output_text(response: dict) -> List[str]:
    texts = []
    for item in response.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    texts.append(part.get("text"))
    return texts


def _parse_strike(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(_STRIKE_QUANT)
    except (InvalidOperation, ValueError):
        return None


def _parse_expiration(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            if "T" in text:
                return datetime.fromisoformat(text).date().isoformat()
            return date.fromisoformat(text).isoformat()
        except ValueError:
            return None
    return None


def _normalize_option_type(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in {"C", "CALL"}:
        return "CALL"
    if text in {"P", "PUT"}:
        return "PUT"
    return None


def _iter_snapshot_contracts(snapshot: Any) -> List[Any]:
    if isinstance(snapshot, list):
        return snapshot
    if isinstance(snapshot, dict):
        for key in ("contracts", "options", "option_chain", "chain"):
            value = snapshot.get(key)
            if isinstance(value, list):
                return value
    return []


def _extract_contracts_from_snapshot(snapshot: Any) -> set[tuple[str, Decimal, str]]:
    contracts: set[tuple[str, Decimal, str]] = set()
    for item in _iter_snapshot_contracts(snapshot):
        if not isinstance(item, dict):
            continue
        expiration = _parse_expiration(item.get("expiration") or item.get("expiration_date"))
        strike = _parse_strike(item.get("strike") or item.get("strike_price"))
        option_type = _normalize_option_type(item.get("type") or item.get("option_type"))
        if expiration and strike and option_type:
            contracts.add((expiration, strike, option_type))
    return contracts


def register_option_chain_snapshot(snapshot: Any) -> tuple[str, int]:
    if snapshot is None:
        raise ValueError("option_chain_snapshot_missing")
    snapshot_json = _canonical_json(snapshot)
    digest = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
    contracts = _extract_contracts_from_snapshot(snapshot)
    if not contracts:
        raise ValueError("option_chain_snapshot_empty")
    _OPTION_CHAIN_REGISTRY[digest] = contracts
    return digest, len(contracts)


def _parse_raw_response(raw_response: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if isinstance(raw_response, dict):
        if "_error" in raw_response:
            return None, str(raw_response.get("_error"))
        if isinstance(raw_response.get("output"), list):
            texts = extract_output_text(raw_response)
            if not texts:
                return None, "No output_text found in response"
            try:
                data = json.loads(texts[0])
            except Exception as exc:
                return None, f"Invalid JSON: {exc}"
            if not isinstance(data, dict):
                return None, "Response JSON is not an object"
            return data, None
        return raw_response, None
    if isinstance(raw_response, (bytes, bytearray)):
        raw_response = raw_response.decode("utf-8", errors="replace")
    if isinstance(raw_response, str):
        content = raw_response.strip()
        if not content:
            return None, "Empty response"
        try:
            data = json.loads(content)
        except Exception as exc:
            return None, f"Invalid JSON: {exc}"
        if not isinstance(data, dict):
            return None, "Response JSON is not an object"
        return data, None
    return None, "Unsupported raw response type"


def _validate_candidate(candidate: Dict[str, Any]) -> Tuple[bool, str]:
    errors: List[str] = []
    for key in ("snapshot_metadata", "context_evaluation", "option_recommendations", "confidence_summary"):
        if key not in candidate:
            errors.append(f"Missing top-level key: {key}")
    snapshot_metadata = candidate.get("snapshot_metadata")
    if snapshot_metadata is not None and not isinstance(snapshot_metadata, dict):
        errors.append("snapshot_metadata must be an object")

    context_eval = candidate.get("context_evaluation")
    status = None
    failure_type = None
    if not isinstance(context_eval, dict):
        errors.append("context_evaluation must be an object")
    else:
        status = context_eval.get("status")
        failure_type = context_eval.get("failure_type")
        reason = context_eval.get("reason")
        if status not in {"ACCEPTED", "REJECTED"}:
            errors.append("context_evaluation.status invalid")
        if failure_type not in {"SCHEMA_FAIL", "INVALID_CHAIN", "CONTEXT_REJECTED", None}:
            errors.append("context_evaluation.failure_type invalid")
        if not isinstance(reason, str):
            errors.append("context_evaluation.reason must be a string")
        if status == "REJECTED" and failure_type is None:
            errors.append("context_evaluation.failure_type required for rejection")
        if status == "ACCEPTED" and failure_type is not None:
            errors.append("context_evaluation.failure_type must be null for acceptance")

    option_recs = candidate.get("option_recommendations")
    primary = None
    if not isinstance(option_recs, dict):
        errors.append("option_recommendations must be an object")
    else:
        primary = option_recs.get("primary")
        alternatives = option_recs.get("alternatives")
        if not isinstance(alternatives, list):
            errors.append("option_recommendations.alternatives must be a list")
        if status == "REJECTED" and primary is not None:
            errors.append("option_recommendations.primary must be null for rejection")
        if status == "ACCEPTED":
            if not isinstance(primary, dict):
                errors.append("option_recommendations.primary must be an object for acceptance")
            else:
                option_type_raw = primary.get("option_type")
                if option_type_raw not in {"CALL", "PUT"}:
                    errors.append("option_recommendations.primary.option_type invalid")
                strike_value = primary.get("strike")
                if not isinstance(strike_value, (int, float, Decimal)) or isinstance(strike_value, bool):
                    errors.append("option_recommendations.primary.strike must be numeric")
                expiration_raw = primary.get("expiration")
                expiration = _parse_expiration(expiration_raw)
                if expiration is None or not isinstance(expiration_raw, str) or expiration_raw.strip() != expiration:
                    errors.append("option_recommendations.primary.expiration invalid")
                stop_loss = primary.get("stop_loss")
                if not isinstance(stop_loss, str) or not stop_loss:
                    errors.append("option_recommendations.primary.stop_loss required")
                profit_target = primary.get("profit_target")
                if not isinstance(profit_target, str) or not profit_target:
                    errors.append("option_recommendations.primary.profit_target required")

    confidence_summary = candidate.get("confidence_summary")
    if confidence_summary is not None and not isinstance(confidence_summary, dict):
        errors.append("confidence_summary must be an object")

    if errors:
        logger.error("schema_validation_failed", extra={"errors": errors})
        return False, "; ".join(errors)
    return True, "PASS"


def _build_failure_response(
    *,
    reason: str,
    failure_type: str,
    provider_id: str,
    model_id: str,
    prompt_version: str,
    kapman_model_version: str,
) -> Dict[str, Any]:
    snapshot_metadata = {
        "ticker": "UNKNOWN",
        "snapshot_time": "UNKNOWN",
        "model_version": prompt_version,
        "wyckoff_regime": "UNKNOWN",
        "wyckoff_primary_event": "NONE",
        "data_completeness_flags": {},
        "ai_provider": provider_id,
        "ai_model": model_id,
        "ai_model_version": None,
        "kapman_model_version": kapman_model_version,
    }
    return {
        "snapshot_metadata": snapshot_metadata,
        "context_evaluation": {
            "status": "REJECTED",
            "failure_type": failure_type,
            "reason": reason,
        },
        "option_recommendations": {"primary": None, "alternatives": []},
        "confidence_summary": {
            "score": 0.0,
            "summary": "failure",
            "confidence_type": "RELATIVE",
            "ranking_basis": "Primary outranks alternatives by construction",
            "confidence_gap_notes": None,
        },
        "primary_recommendation": {
            "action": "NO_TRADE",
            "strategy_class": "NONE",
            "direction": "NEUTRAL",
            "confidence_score": 75,
            "time_horizon": "medium",
            "rationale_summary": reason,
        },
        "alternative_recommendations": [
            {
                "label": "Re-run after fix",
                "action": "WAIT",
                "strategy_class": "NONE",
                "direction": "NEUTRAL",
                "confidence_score": 50,
                "blocking_reason": reason,
                "promotion_conditions": "Provide a valid AI response and re-run.",
            }
        ],
        "reasoning_trace": {
            "fired_rules": [],
            "cluster_contributions": [{"cluster": "Meta", "impact": "MALFORMED_RESPONSE"}],
            "supporting_factors": [],
            "blocking_factors": [reason],
        },
        "missing_data_declaration": [f"Normalization failure: {reason}"],
        "guardrails_and_disclaimers": list(STANDARD_GUARDRAILS),
    }


def _failure_response(
    *,
    reason: str,
    provider_id: str,
    model_id: str,
    prompt_version: str,
    kapman_model_version: str,
    failure_type: str = "SCHEMA_FAIL",
) -> Dict[str, Any]:
    return _build_failure_response(
        reason=reason,
        failure_type=failure_type,
        provider_id=provider_id,
        model_id=model_id,
        prompt_version=prompt_version,
        kapman_model_version=kapman_model_version,
    )


def normalize_agent_response(
    *,
    raw_response: Any,
    provider_id: str,
    model_id: str,
    prompt_version: str,
    kapman_model_version: str,
) -> Dict[str, Any]:
    logger.debug("ai_raw_output", extra={"raw_response": raw_response})
    if _ai_dump_enabled():
        logger.info(
            "[AI_DUMP] "
            + json.dumps({"event": "ai_parser_input", "raw_response": raw_response}, ensure_ascii=True, separators=(",", ":"))
        )
    candidate, error_reason = _parse_raw_response(raw_response)
    if error_reason:
        logger.error("ai_parse_failure", extra={"reason": error_reason})
        return _failure_response(
            reason=error_reason,
            provider_id=provider_id,
            model_id=model_id,
            prompt_version=prompt_version,
            kapman_model_version=kapman_model_version,
            failure_type="SCHEMA_FAIL",
        )
    assert candidate is not None
    valid, reason = _validate_candidate(candidate)
    if not valid:
        return _failure_response(
            reason=reason,
            provider_id=provider_id,
            model_id=model_id,
            prompt_version=prompt_version,
            kapman_model_version=kapman_model_version,
            failure_type="SCHEMA_FAIL",
        )
    return candidate
