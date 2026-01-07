import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("kapman.ai.response_parser")


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


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_string_list(value: Any, field: str, errors: List[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return
    for item in value:
        if not isinstance(item, str):
            errors.append(f"{field} items must be strings")
            return


def _validate_candidate(candidate: Dict[str, Any]) -> Tuple[bool, str]:
    errors: List[str] = []
    required_keys = [
        "context_label",
        "confidence_score",
        "metric_assessment",
        "metric_weights",
        "discarded_metrics",
        "conditional_recommendation",
    ]
    for key in required_keys:
        if key not in candidate:
            errors.append(f"Missing top-level key: {key}")

    context_label = candidate.get("context_label")
    if not isinstance(context_label, str):
        errors.append("context_label must be a string")

    confidence_score = candidate.get("confidence_score")
    if not _is_number(confidence_score):
        errors.append("confidence_score must be a number")
    else:
        if confidence_score < 0 or confidence_score > 1:
            errors.append("confidence_score out of range")

    metric_assessment = candidate.get("metric_assessment")
    if not isinstance(metric_assessment, dict):
        errors.append("metric_assessment must be an object")
    else:
        _validate_string_list(metric_assessment.get("supporting"), "metric_assessment.supporting", errors)
        _validate_string_list(metric_assessment.get("contradicting"), "metric_assessment.contradicting", errors)
        _validate_string_list(metric_assessment.get("neutral"), "metric_assessment.neutral", errors)

    metric_weights = candidate.get("metric_weights")
    if not isinstance(metric_weights, dict):
        errors.append("metric_weights must be an object")
    else:
        for key, value in metric_weights.items():
            if not isinstance(key, str):
                errors.append("metric_weights keys must be strings")
                break
            if not _is_number(value):
                errors.append("metric_weights values must be numbers")
                break

    _validate_string_list(candidate.get("discarded_metrics"), "discarded_metrics", errors)

    conditional = candidate.get("conditional_recommendation")
    if not isinstance(conditional, dict):
        errors.append("conditional_recommendation must be an object")
    else:
        direction = conditional.get("direction")
        action = conditional.get("action")
        option_type = conditional.get("option_type")
        option_strategy = conditional.get("option_strategy")
        if not isinstance(direction, str):
            errors.append("conditional_recommendation.direction must be a string")
        if not isinstance(action, str):
            errors.append("conditional_recommendation.action must be a string")
        if option_type is not None and not isinstance(option_type, str):
            errors.append("conditional_recommendation.option_type must be a string or null")
        if option_strategy is not None and not isinstance(option_strategy, str):
            errors.append("conditional_recommendation.option_strategy must be a string or null")

    if errors:
        logger.error("schema_validation_failed", extra={"errors": errors})
        return False, "; ".join(errors)
    return True, "PASS"


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
        raise ValueError(error_reason)
    assert candidate is not None
    valid, reason = _validate_candidate(candidate)
    if not valid:
        raise ValueError(reason)
    return candidate
