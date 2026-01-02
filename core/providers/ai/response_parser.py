import json
from typing import Any, Dict, List, Optional, Tuple


STANDARD_GUARDRAILS = [
    "This recommendation is rule-based, not predictive.",
    "It is conditioned only on computed inputs.",
    "It does not guarantee execution, fills, or outcomes.",
    "It does not replace position sizing or risk controls.",
    "It reflects current conditions only.",
]

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
    candidate, error_reason = _parse_raw_response(raw_response)
    if error_reason:
        return _failure_response(
            reason=error_reason,
            provider_id=provider_id,
            model_id=model_id,
            prompt_version=prompt_version,
            kapman_model_version=kapman_model_version,
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
        )
    snapshot_metadata = candidate["snapshot_metadata"]
    snapshot_metadata["model_version"] = prompt_version
    snapshot_metadata["ai_provider"] = provider_id
    snapshot_metadata["ai_model"] = model_id
    snapshot_metadata.setdefault("ai_model_version", None)
    snapshot_metadata["kapman_model_version"] = kapman_model_version
    candidate["guardrails_and_disclaimers"] = list(STANDARD_GUARDRAILS)
    return candidate
