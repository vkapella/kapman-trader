import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple


STANDARD_GUARDRAILS = [
    "This recommendation is rule-based, not predictive.",
    "It is conditioned only on computed inputs.",
    "It does not guarantee execution, fills, or outcomes.",
    "It does not replace position sizing or risk controls.",
    "It reflects current conditions only.",
]

logger = logging.getLogger("kapman.ai.response_parser")


def _ai_dump_enabled() -> bool:
    return os.getenv("AI_DUMP") == "1"


def extract_output_text(response: dict) -> List[str]:
    texts = []
    for item in response.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    texts.append(part.get("text"))
    return texts

REQUIRED_TOP_LEVEL = [
    "snapshot_metadata",
    "primary_recommendation",
    "alternative_recommendations",
    "reasoning_trace",
    "confidence_summary",
    "missing_data_declaration",
    "guardrails_and_disclaimers",
]

REQUIRED_SNAPSHOT_METADATA = [
    "ticker",
    "snapshot_time",
    "model_version",
    "wyckoff_regime",
    "wyckoff_primary_event",
    "data_completeness_flags",
]

REQUIRED_PRIMARY = [
    "action",
    "strategy_class",
    "direction",
    "confidence_score",
    "time_horizon",
    "rationale_summary",
]

REQUIRED_ALTERNATIVE = [
    "label",
    "action",
    "strategy_class",
    "direction",
    "confidence_score",
    "blocking_reason",
    "promotion_conditions",
]

REQUIRED_REASONING = [
    "fired_rules",
    "cluster_contributions",
    "supporting_factors",
    "blocking_factors",
]

REQUIRED_CLUSTER_CONTRIBUTION = [
    "cluster",
    "impact",
]

REQUIRED_CONFIDENCE = [
    "confidence_type",
    "ranking_basis",
]


def _parse_raw_response(raw_response: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if isinstance(raw_response, dict):
        if "_error" in raw_response:
            return None, str(raw_response.get("_error"))
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


def _missing_key(container: Dict[str, Any], key: str) -> bool:
    return key not in container


def _validate_candidate(candidate: Dict[str, Any]) -> Tuple[bool, str]:
    for key in REQUIRED_TOP_LEVEL:
        if _missing_key(candidate, key):
            return False, f"Missing top-level key: {key}"
    if not isinstance(candidate["snapshot_metadata"], dict):
        return False, "snapshot_metadata must be an object"
    for key in REQUIRED_SNAPSHOT_METADATA:
        if _missing_key(candidate["snapshot_metadata"], key):
            return False, f"Missing snapshot_metadata field: {key}"
    if not isinstance(candidate["primary_recommendation"], dict):
        return False, "primary_recommendation must be an object"
    for key in REQUIRED_PRIMARY:
        if _missing_key(candidate["primary_recommendation"], key):
            return False, f"Missing primary_recommendation field: {key}"
    if not isinstance(candidate["alternative_recommendations"], list):
        return False, "alternative_recommendations must be a list"
    for alt in candidate["alternative_recommendations"]:
        if not isinstance(alt, dict):
            return False, "alternative_recommendations must contain objects"
        for key in REQUIRED_ALTERNATIVE:
            if _missing_key(alt, key):
                return False, f"Missing alternative_recommendations field: {key}"
    if not isinstance(candidate["reasoning_trace"], dict):
        return False, "reasoning_trace must be an object"
    for key in REQUIRED_REASONING:
        if _missing_key(candidate["reasoning_trace"], key):
            return False, f"Missing reasoning_trace field: {key}"
    if not isinstance(candidate["reasoning_trace"]["cluster_contributions"], list):
        return False, "cluster_contributions must be a list"
    for entry in candidate["reasoning_trace"]["cluster_contributions"]:
        if not isinstance(entry, dict):
            return False, "cluster_contributions must contain objects"
        for key in REQUIRED_CLUSTER_CONTRIBUTION:
            if _missing_key(entry, key):
                return False, f"Missing cluster_contributions field: {key}"
    if not isinstance(candidate["confidence_summary"], dict):
        return False, "confidence_summary must be an object"
    for key in REQUIRED_CONFIDENCE:
        if _missing_key(candidate["confidence_summary"], key):
            return False, f"Missing confidence_summary field: {key}"
    if not isinstance(candidate["missing_data_declaration"], list):
        return False, "missing_data_declaration must be a list"
    if not isinstance(candidate["guardrails_and_disclaimers"], list):
        return False, "guardrails_and_disclaimers must be a list"
    if not candidate["guardrails_and_disclaimers"]:
        return False, "guardrails_and_disclaimers must be non-empty"
    primary_confidence = candidate["primary_recommendation"].get("confidence_score")
    if not isinstance(primary_confidence, (int, float)):
        return False, "primary confidence_score must be numeric"
    for alt in candidate["alternative_recommendations"]:
        alt_confidence = alt.get("confidence_score")
        if not isinstance(alt_confidence, (int, float)):
            return False, "alternative confidence_score must be numeric"
        if alt_confidence >= primary_confidence:
            return False, "alternative confidence must be lower than primary"
    return True, "PASS"


def _coerce_confidence_score(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if 0.0 <= score <= 1.0:
        return int(round(score * 100))
    if 0.0 <= score <= 100.0:
        return int(round(score))
    return None


def normalize_recommendation(raw_output: Any) -> Dict[str, Any]:
    if raw_output is None:
        raise RuntimeError("Model returned no content")
    if isinstance(raw_output, (bytes, bytearray)):
        raw_output = raw_output.decode("utf-8", errors="replace")
    if isinstance(raw_output, str):
        text = raw_output.strip()
        if not text:
            raise RuntimeError("Model returned no content")
        return {
            "action": "HOLD",
            "confidence": 0.5,
            "risk_level": "MEDIUM",
            "rationale": text,
        }
    if not isinstance(raw_output, dict):
        raise RuntimeError("Model returned no content")

    if "primary_recommendation" in raw_output and isinstance(raw_output["primary_recommendation"], dict):
        primary = raw_output["primary_recommendation"]
        raw_action = primary.get("action")
        raw_confidence = primary.get("confidence_score") or primary.get("confidence")
        raw_rationale = primary.get("rationale_summary") or primary.get("rationale")
    else:
        raw_action = raw_output.get("action")
        raw_confidence = raw_output.get("confidence")
        raw_rationale = raw_output.get("rationale") or raw_output.get("rationale_summary")

    action = str(raw_action or "HOLD").strip().upper()
    reason = None
    if action not in {"BUY", "SELL", "HOLD", "NO_TRADE"}:
        reason = "invalid_action"
        action = "HOLD"
    if action == "NO_TRADE":
        reason = "no_trade_action"
        action = "HOLD"

    confidence = 0.5
    if raw_confidence is not None:
        try:
            value = float(raw_confidence)
        except (TypeError, ValueError):
            value = None
        if value is not None:
            if 0.0 <= value <= 1.0:
                confidence = value
            elif 0.0 <= value <= 100.0:
                confidence = value / 100.0
            else:
                if reason is None:
                    reason = "invalid_confidence"

    rationale = ""
    if raw_rationale is None:
        rationale = ""
    elif isinstance(raw_rationale, str):
        rationale = raw_rationale
    else:
        rationale = str(raw_rationale)

    risk_level = str(raw_output.get("risk_level") or "MEDIUM").strip().upper()
    if risk_level not in {"LOW", "MEDIUM", "HIGH"}:
        risk_level = "MEDIUM"

    normalized = {
        "action": action,
        "confidence": confidence,
        "risk_level": risk_level,
        "rationale": rationale,
    }
    if _ai_dump_enabled() and action == "HOLD":
        logger.info("[AI_DUMP] " + json.dumps({"event": "hold_reason", "reason": reason or "default_hold"}, ensure_ascii=True, separators=(",", ":")))
    return normalized


def _build_simple_recommendation(
    *,
    recommendation: Dict[str, Any],
    candidate: Optional[Dict[str, Any]],
    provider_id: str,
    model_id: str,
    prompt_version: str,
    kapman_model_version: str,
) -> Dict[str, Any]:
    confidence_score = int(round(recommendation["confidence"] * 100))
    normalized_action = recommendation["action"]
    if normalized_action == "BUY":
        primary_action = "ENTER"
        direction = "BULLISH"
    elif normalized_action == "SELL":
        primary_action = "ENTER"
        direction = "BEARISH"
    else:
        primary_action = "NO_TRADE"
        direction = "NEUTRAL"
    rationale_text = recommendation["rationale"]
    ticker = "UNKNOWN"
    if candidate:
        ticker = candidate.get("symbol") or candidate.get("ticker") or "UNKNOWN"
        snapshot_metadata = candidate.get("snapshot_metadata")
        if isinstance(snapshot_metadata, dict):
            ticker = snapshot_metadata.get("ticker") or ticker
    snapshot_metadata = {
        "ticker": str(ticker),
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
        "primary_recommendation": {
            "action": primary_action,
            "strategy_class": "NONE",
            "direction": direction,
            "confidence_score": confidence_score,
            "time_horizon": "medium",
            "rationale_summary": rationale_text,
        },
        "alternative_recommendations": [],
        "reasoning_trace": {
            "fired_rules": [],
            "cluster_contributions": [{"cluster": "Meta", "impact": "MODEL_OUTPUT"}],
            "supporting_factors": [],
            "blocking_factors": [],
        },
        "confidence_summary": {
            "confidence_type": "RELATIVE",
            "ranking_basis": "Primary outranks alternatives by construction",
            "confidence_gap_notes": None,
        },
        "missing_data_declaration": [],
        "guardrails_and_disclaimers": list(STANDARD_GUARDRAILS),
    }


def _failure_response(
    *,
    reason: str,
    provider_id: str,
    model_id: str,
    prompt_version: str,
    kapman_model_version: str,
) -> Dict[str, Any]:
    return {
        "snapshot_metadata": {
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
        "confidence_summary": {
            "confidence_type": "RELATIVE",
            "ranking_basis": "Primary outranks alternatives by construction",
            "confidence_gap_notes": None,
        },
        "missing_data_declaration": [f"Normalization failure: {reason}"],
        "guardrails_and_disclaimers": list(STANDARD_GUARDRAILS),
    }


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
        if isinstance(raw_response, dict) and "_error" in raw_response:
            normalized = _failure_response(
                reason=error_reason,
                provider_id=provider_id,
                model_id=model_id,
                prompt_version=prompt_version,
                kapman_model_version=kapman_model_version,
            )
            if _ai_dump_enabled():
                logger.info(
                    "[AI_DUMP] "
                    + json.dumps(
                        {"event": "ai_parse_dump", "ticker": "UNKNOWN", "normalized": "NO_TRADE", "reason": error_reason},
                        ensure_ascii=True,
                        separators=(",", ":"),
                    )
                )
            return normalized
        recommendation = normalize_recommendation(raw_response)
        normalized = _build_simple_recommendation(
            recommendation=recommendation,
            candidate=None,
            provider_id=provider_id,
            model_id=model_id,
            prompt_version=prompt_version,
            kapman_model_version=kapman_model_version,
        )
        logger.debug("ai_parsed_recommendation", extra={"recommendation": normalized})
        if _ai_dump_enabled():
            logger.info(
                "[AI_DUMP] "
                + json.dumps(
                    {
                        "event": "ai_parse_dump",
                        "ticker": normalized.get("snapshot_metadata", {}).get("ticker"),
                        "normalized": normalized,
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )
        return normalized
    assert candidate is not None
    if isinstance(candidate, dict) and isinstance(candidate.get("output"), list):
        texts = extract_output_text(candidate)
        if not texts:
            raise ValueError("No output_text found in OpenAI response")
        raw = texts[0]
        try:
            rec = json.loads(raw)
        except Exception as exc:
            raise ValueError(f"Invalid JSON from model: {raw}") from exc
        if not isinstance(rec, dict):
            raise ValueError("Model output is not a JSON object")
        required = {"action", "confidence", "rationale"}
        missing = required - rec.keys()
        if missing:
            raise ValueError(f"Missing required fields: {missing}")
        recommendations = [rec]
        if not recommendations:
            raise RuntimeError(f"Parser produced zero recommendations from valid model output: {raw}")
        recommendation = normalize_recommendation(rec)
        normalized = _build_simple_recommendation(
            recommendation=recommendation,
            candidate=None,
            provider_id=provider_id,
            model_id=model_id,
            prompt_version=prompt_version,
            kapman_model_version=kapman_model_version,
        )
        return normalized
    valid, reason = _validate_candidate(candidate)
    if not valid:
        recommendation = normalize_recommendation(candidate)
        normalized = _build_simple_recommendation(
            recommendation=recommendation,
            candidate=candidate,
            provider_id=provider_id,
            model_id=model_id,
            prompt_version=prompt_version,
            kapman_model_version=kapman_model_version,
        )
        logger.debug("ai_parsed_recommendation", extra={"recommendation": normalized})
        if _ai_dump_enabled():
            logger.info(
                "[AI_DUMP] "
                + json.dumps(
                    {
                        "event": "ai_parse_dump",
                        "ticker": normalized.get("snapshot_metadata", {}).get("ticker"),
                        "normalized": normalized,
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )
        return normalized
    snapshot_metadata = candidate["snapshot_metadata"]
    snapshot_metadata["model_version"] = prompt_version
    snapshot_metadata["ai_provider"] = provider_id
    snapshot_metadata["ai_model"] = model_id
    snapshot_metadata.setdefault("ai_model_version", None)
    snapshot_metadata["kapman_model_version"] = kapman_model_version
    candidate["guardrails_and_disclaimers"] = list(STANDARD_GUARDRAILS)
    logger.debug("ai_parsed_recommendation", extra={"recommendation": candidate})
    if _ai_dump_enabled():
        logger.info(
            "[AI_DUMP] "
            + json.dumps(
                {
                    "event": "ai_parse_dump",
                    "ticker": candidate.get("snapshot_metadata", {}).get("ticker"),
                    "normalized": candidate,
                },
                ensure_ascii=True,
                separators=(",", ":"),
            )
        )
    return candidate
