import json
from typing import Any, Dict


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
    response_schema = {
        "snapshot_metadata": {
            "ticker": "",
            "snapshot_time": "",
            "model_version": "",
            "wyckoff_regime": "",
            "wyckoff_primary_event": "",
            "data_completeness_flags": {},
        },
        "primary_recommendation": {
            "action": "ENTER|WAIT|DEFER|NO_TRADE",
            "strategy_class": "NONE|LONG_CALL|LONG_PUT|CALL_DEBIT_SPREAD|PUT_DEBIT_SPREAD|CSP|COVERED_CALL|HEDGE_OVERLAY",
            "direction": "BULLISH|BEARISH|NEUTRAL",
            "confidence_score": 0,
            "time_horizon": "short|medium|long",
            "rationale_summary": "",
        },
        "alternative_recommendations": [
            {
                "label": "",
                "action": "ENTER|WAIT|DEFER|NO_TRADE",
                "strategy_class": "NONE|LONG_CALL|LONG_PUT|CALL_DEBIT_SPREAD|PUT_DEBIT_SPREAD|CSP|COVERED_CALL|HEDGE_OVERLAY",
                "direction": "BULLISH|BEARISH|NEUTRAL",
                "confidence_score": 0,
                "blocking_reason": "",
                "promotion_conditions": "",
            }
        ],
        "reasoning_trace": {
            "fired_rules": [],
            "cluster_contributions": [{"cluster": "", "impact": ""}],
            "supporting_factors": [],
            "blocking_factors": [],
        },
        "confidence_summary": {
            "confidence_type": "RELATIVE",
            "ranking_basis": "Primary outranks alternatives by construction",
            "confidence_gap_notes": None,
        },
        "missing_data_declaration": [],
        "guardrails_and_disclaimers": [],
    }
    payload_json = _canonical_json(payload)
    response_schema_json = _canonical_json(response_schema)
    return "\n".join(
        [
            "KAPMAN_C1_PROMPT",
            f"PROMPT_VERSION: {prompt_version}",
            "Return a single JSON object that conforms to the KapMan agent response contract.",
            "No prose. No markdown.",
            "RESPONSE_SCHEMA:",
            response_schema_json,
            "REQUEST_PAYLOAD:",
            payload_json,
        ]
    )
