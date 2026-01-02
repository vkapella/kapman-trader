from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, root_validator, validator

logger = logging.getLogger("kapman.ai")


class MarketStructure(BaseModel):
    wyckoff_regime: str
    wyckoff_events: List[str]
    regime_confidence: float

    class Config:
        extra = "forbid"


class RequestContext(BaseModel):
    symbol: str
    snapshot_time: str
    market_structure: MarketStructure
    technical_summary: Dict[str, Any]
    volatility_summary: Dict[str, Any]
    dealer_summary: Dict[str, Any]

    class Config:
        extra = "forbid"


class LiquidityConstraints(BaseModel):
    min_open_interest: int
    min_volume: int

    class Config:
        extra = "forbid"


class ExpirationBucket(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class MoneynessBand(str, Enum):
    ATM = "ATM"
    SLIGHTLY_OTM = "slightly_OTM"
    FAR_OTM = "far_OTM"


class OptionContext(BaseModel):
    spot_price: float
    expiration_buckets: List[ExpirationBucket]
    moneyness_bands: List[MoneynessBand]
    liquidity_constraints: LiquidityConstraints
    volatility_regime_summary: Optional[Dict[str, Any]] = None
    strategy_eligibility_constraints: Optional[Dict[str, Any]] = None

    class Config:
        extra = "forbid"


class AuthorityConstraints(BaseModel):
    wyckoff_veto: bool
    iv_forbids_long_premium: bool
    dealer_timing_veto: bool

    class Config:
        extra = "forbid"


class InstructionBlock(BaseModel):
    objective: str
    forbidden_actions: List[str]

    class Config:
        extra = "forbid"


class AIRequest(BaseModel):
    context: RequestContext
    option_context: OptionContext
    authority_constraints: AuthorityConstraints
    instructions: InstructionBlock

    class Config:
        extra = "forbid"


class InvocationConfig(BaseModel):
    ai_debug: bool = False
    ai_dry_run: bool = False
    model_version: str
    invocation_id: Optional[str] = None

    class Config:
        extra = "forbid"


class Action(str, Enum):
    ENTER = "ENTER"
    WAIT = "WAIT"
    DEFER = "DEFER"
    NO_TRADE = "NO_TRADE"


class StrategyClass(str, Enum):
    NONE = "NONE"
    LONG_CALL = "LONG_CALL"
    LONG_PUT = "LONG_PUT"
    CALL_DEBIT_SPREAD = "CALL_DEBIT_SPREAD"
    PUT_DEBIT_SPREAD = "PUT_DEBIT_SPREAD"
    CSP = "CSP"
    COVERED_CALL = "COVERED_CALL"
    HEDGE_OVERLAY = "HEDGE_OVERLAY"


class Direction(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class TimeHorizon(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class SnapshotMetadata(BaseModel):
    ticker: str
    snapshot_time: str
    model_version: str
    wyckoff_regime: str
    wyckoff_primary_event: str
    data_completeness_flags: Dict[str, str]
    ai_provider: str
    ai_model: str
    ai_model_version: Optional[str] = None
    kapman_model_version: str

    class Config:
        extra = "forbid"


class PrimaryRecommendation(BaseModel):
    action: Action
    strategy_class: StrategyClass
    direction: Direction
    confidence_score: int
    time_horizon: TimeHorizon
    rationale_summary: str

    class Config:
        extra = "forbid"

    @validator("confidence_score")
    def _confidence_range(cls, value: int) -> int:
        if value < 0 or value > 100:
            raise ValueError("confidence_score must be between 0 and 100")
        return value

    @root_validator
    def _no_trade_strategy(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        action = values.get("action")
        strategy_class = values.get("strategy_class")
        if action == Action.NO_TRADE and strategy_class != StrategyClass.NONE:
            raise ValueError("strategy_class must be NONE when action is NO_TRADE")
        return values


class AlternativeRecommendation(BaseModel):
    label: str
    action: Action
    strategy_class: StrategyClass
    direction: Direction
    confidence_score: int
    blocking_reason: str
    promotion_conditions: str

    class Config:
        extra = "forbid"

    @validator("confidence_score")
    def _alt_confidence_range(cls, value: int) -> int:
        if value < 0 or value > 100:
            raise ValueError("confidence_score must be between 0 and 100")
        return value

    @root_validator
    def _alt_no_trade_strategy(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        action = values.get("action")
        strategy_class = values.get("strategy_class")
        if action == Action.NO_TRADE and strategy_class != StrategyClass.NONE:
            raise ValueError("strategy_class must be NONE when action is NO_TRADE")
        return values


class ClusterContribution(BaseModel):
    cluster: str
    impact: str

    class Config:
        extra = "forbid"


class ReasoningTrace(BaseModel):
    fired_rules: List[str]
    cluster_contributions: List[ClusterContribution]
    supporting_factors: List[str]
    blocking_factors: List[str]

    class Config:
        extra = "forbid"

    @validator("fired_rules", each_item=True)
    def _rule_id_allowed(cls, value: str) -> str:
        if value not in ALLOWED_RULE_IDS:
            raise ValueError(f"unknown rule id: {value}")
        return value


class ConfidenceSummary(BaseModel):
    confidence_type: str
    ranking_basis: str
    confidence_gap_notes: Optional[str] = None

    class Config:
        extra = "forbid"

    @validator("confidence_type")
    def _confidence_type_relative(cls, value: str) -> str:
        if value != "RELATIVE":
            raise ValueError("confidence_type must be RELATIVE")
        return value


class TradeRecommendation(BaseModel):
    snapshot_metadata: SnapshotMetadata
    primary_recommendation: PrimaryRecommendation
    alternative_recommendations: List[AlternativeRecommendation]
    reasoning_trace: ReasoningTrace
    confidence_summary: ConfidenceSummary
    missing_data_declaration: List[str]
    guardrails_and_disclaimers: List[str]

    class Config:
        extra = "forbid"

    @root_validator
    def _alternatives_below_primary(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        primary: PrimaryRecommendation = values.get("primary_recommendation")
        alternatives: List[AlternativeRecommendation] = values.get("alternative_recommendations") or []
        if primary and alternatives:
            primary_confidence = primary.confidence_score
            for alt in alternatives:
                if alt.confidence_score >= primary_confidence:
                    raise ValueError("alternative confidence must be lower than primary")
        return values


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    model_version: Optional[str] = None


class AIProvider(ABC):
    provider_id: str

    @abstractmethod
    async def invoke(self, model_id: str, system_prompt: str, user_prompt: str) -> ProviderResponse:
        pass


ALLOWED_RULE_IDS = {
    "WYC-01",
    "WYC-02",
    "WYC-03",
    "TA-01",
    "TA-02",
    "TA-03",
    "TA-04",
    "TA-05",
    "PV-01",
    "PV-02",
    "PV-03",
    "VOL-01",
    "VOL-02",
    "VOL-03",
    "VOL-04",
    "EM-01",
    "DLR-01",
    "DLR-02",
    "DLR-03",
    "DATA-01",
}

ALLOWED_PROVIDERS = {"anthropic", "openai"}

GUARDRAILS_AND_DISCLAIMERS = [
    "This recommendation is rule-based, not predictive.",
    "It is conditioned only on computed inputs.",
    "It does not guarantee execution, fills, or outcomes.",
    "It does not replace position sizing or risk controls.",
    "It reflects current conditions only.",
]


def _model_dump(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _model_validate(model_cls: Any, data: Any) -> BaseModel:
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)
    return model_cls.parse_obj(data)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _invocation_id_from_request(request: AIRequest) -> str:
    return f"{request.context.symbol}:{request.context.snapshot_time}"


def _primary_event(events: Sequence[str]) -> str:
    return str(events[0]) if events else "NONE"


def _summary_computed(summary: Dict[str, Any]) -> bool:
    if not summary:
        return False
    for value in summary.values():
        if value is not None:
            return True
    return False


def _data_completeness_flags(request: AIRequest) -> Dict[str, str]:
    flags = {}
    flags["technical_summary"] = "COMPUTED" if _summary_computed(request.context.technical_summary) else "NOT COMPUTED"
    flags["volatility_summary"] = "COMPUTED" if _summary_computed(request.context.volatility_summary) else "NOT COMPUTED"
    flags["dealer_summary"] = "COMPUTED" if _summary_computed(request.context.dealer_summary) else "NOT COMPUTED"
    return flags


def _missing_data_declaration(flags: Dict[str, str]) -> List[str]:
    missing = []
    if flags.get("technical_summary") != "COMPUTED":
        missing.append("Technical indicators: NOT COMPUTED")
    if flags.get("volatility_summary") != "COMPUTED":
        missing.append("Volatility metrics: NOT COMPUTED")
    if flags.get("dealer_summary") != "COMPUTED":
        missing.append("Dealer metrics: NOT COMPUTED")
    return missing


def _direction_from_events(events: Sequence[str]) -> Direction:
    upper = {str(event).upper() for event in events}
    if "SOS" in upper:
        return Direction.BULLISH
    if "SOW" in upper:
        return Direction.BEARISH
    return Direction.NEUTRAL


def _long_premium_strategy(strategy_class: StrategyClass) -> bool:
    return strategy_class in {StrategyClass.LONG_CALL, StrategyClass.LONG_PUT}


def _build_system_prompt() -> str:
    return (
        "You are a deterministic planning agent. Follow KapMan Slice C constraints strictly. "
        "Return JSON only, no prose, no markdown.\n\n"
        "Hard constraints:\n"
        "- Wyckoff veto => primary action NO_TRADE.\n"
        "- Dealer timing veto => primary action must not be ENTER.\n"
        "- Extreme IV forbids long-premium as primary; emit countervailing long-premium alternative.\n"
        "- Confidence is relative; primary confidence is highest.\n"
        "- NO_TRADE is first-class and scorable.\n"
        "- Do not infer from missing data.\n"
        "- Never assume strike or expiration validity.\n"
        "- Do not include strikes, expirations, or option chains.\n\n"
        "Use only rule IDs from the rule catalog:\n"
        + ", ".join(sorted(ALLOWED_RULE_IDS))
        + "\n\n"
        "Output schema (JSON keys required):\n"
        "{\n"
        "  \"snapshot_metadata\": {\"ticker\": \"\", \"snapshot_time\": \"\", \"model_version\": \"\", "
        "\"wyckoff_regime\": \"\", \"wyckoff_primary_event\": \"\", \"data_completeness_flags\": {}, "
        "\"ai_provider\": \"\", \"ai_model\": \"\", \"ai_model_version\": null, \"kapman_model_version\": \"\"},\n"
        "  \"primary_recommendation\": {\"action\": \"ENTER|WAIT|DEFER|NO_TRADE\", "
        "\"strategy_class\": \"NONE|LONG_CALL|LONG_PUT|CALL_DEBIT_SPREAD|PUT_DEBIT_SPREAD|CSP|COVERED_CALL|HEDGE_OVERLAY\", "
        "\"direction\": \"BULLISH|BEARISH|NEUTRAL\", \"confidence_score\": 0, "
        "\"time_horizon\": \"short|medium|long\", \"rationale_summary\": \"\"},\n"
        "  \"alternative_recommendations\": [{\"label\": \"\", \"action\": \"ENTER|WAIT|DEFER|NO_TRADE\", "
        "\"strategy_class\": \"NONE|LONG_CALL|LONG_PUT|CALL_DEBIT_SPREAD|PUT_DEBIT_SPREAD|CSP|COVERED_CALL|HEDGE_OVERLAY\", "
        "\"direction\": \"BULLISH|BEARISH|NEUTRAL\", \"confidence_score\": 0, "
        "\"blocking_reason\": \"\", \"promotion_conditions\": \"\"}],\n"
        "  \"reasoning_trace\": {\"fired_rules\": [], "
        "\"cluster_contributions\": [{\"cluster\": \"\", \"impact\": \"\"}], "
        "\"supporting_factors\": [], \"blocking_factors\": []},\n"
        "  \"confidence_summary\": {\"confidence_type\": \"RELATIVE\", "
        "\"ranking_basis\": \"Primary outranks alternatives by construction\", "
        "\"confidence_gap_notes\": null},\n"
        "  \"missing_data_declaration\": [],\n"
        "  \"guardrails_and_disclaimers\": []\n"
        "}\n"
    )


def _build_user_prompt(request_json: str, missing_data: Sequence[str]) -> str:
    missing_block = "\n".join(f"- {item}" for item in missing_data) if missing_data else "- None"
    return (
        "Request payload (canonical JSON):\n"
        f"{request_json}\n\n"
        "Missing data declarations (copy verbatim into output):\n"
        f"{missing_block}\n"
    )


def _log_structured(event: str, payload: Dict[str, Any]) -> None:
    log_payload = {"event": event, **payload}
    logger.info(_canonical_json(log_payload))


def _validate_constraints(
    request: AIRequest, recommendation: TradeRecommendation
) -> Optional[str]:
    constraints = request.authority_constraints
    primary = recommendation.primary_recommendation
    if constraints.wyckoff_veto and primary.action != Action.NO_TRADE:
        return "Wyckoff veto requires primary NO_TRADE"
    if constraints.dealer_timing_veto and primary.action == Action.ENTER:
        return "Dealer timing veto forbids ENTER primary"
    if constraints.iv_forbids_long_premium and _long_premium_strategy(primary.strategy_class):
        return "IV forbid requires non-long-premium primary"
    if constraints.iv_forbids_long_premium:
        long_premium_alts = [
            alt for alt in recommendation.alternative_recommendations if _long_premium_strategy(alt.strategy_class)
        ]
        if not long_premium_alts:
            return "IV forbid requires long-premium alternative"
    if constraints.wyckoff_veto or constraints.dealer_timing_veto or constraints.iv_forbids_long_premium:
        if not recommendation.alternative_recommendations:
            return "Alternatives required when trade is blocked"
    return None


def _build_base_metadata(
    request: AIRequest,
    provider_id: str,
    model_id: str,
    model_version: str,
    ai_model_version: Optional[str],
    flags: Dict[str, str],
) -> SnapshotMetadata:
    return SnapshotMetadata(
        ticker=request.context.symbol,
        snapshot_time=request.context.snapshot_time,
        model_version=model_version,
        wyckoff_regime=request.context.market_structure.wyckoff_regime,
        wyckoff_primary_event=_primary_event(request.context.market_structure.wyckoff_events),
        data_completeness_flags=flags,
        ai_provider=provider_id,
        ai_model=model_id,
        ai_model_version=ai_model_version,
        kapman_model_version=model_version,
    )


def _build_fallback_output(
    request: AIRequest,
    provider_id: str,
    model_id: str,
    model_version: str,
    flags: Dict[str, str],
    missing_data: List[str],
    reason: str,
) -> TradeRecommendation:
    constraints = request.authority_constraints
    action = Action.NO_TRADE
    confidence = 75 if constraints.wyckoff_veto else 60

    direction = Direction.NEUTRAL
    primary = PrimaryRecommendation(
        action=action,
        strategy_class=StrategyClass.NONE,
        direction=direction,
        confidence_score=confidence,
        time_horizon=TimeHorizon.MEDIUM,
        rationale_summary=reason[:200],
    )

    alternatives: List[AlternativeRecommendation] = []
    alternatives.append(
        AlternativeRecommendation(
            label="Conditional wait",
            action=Action.WAIT,
            strategy_class=StrategyClass.NONE,
            direction=direction,
            confidence_score=max(0, confidence - 20),
            blocking_reason=reason,
            promotion_conditions="Provide complete inputs and re-run.",
        )
    )

    if constraints.iv_forbids_long_premium:
        alt_direction = _direction_from_events(request.context.market_structure.wyckoff_events)
        alternatives.append(
            AlternativeRecommendation(
                label="Counter-IV long premium",
                action=Action.ENTER,
                strategy_class=StrategyClass.LONG_CALL if alt_direction != Direction.BEARISH else StrategyClass.LONG_PUT,
                direction=alt_direction,
                confidence_score=max(0, confidence - 30),
                blocking_reason="Extreme IV forbids long premium as primary.",
                promotion_conditions="IV regime normalizes and timing constraints clear.",
            )
        )

    reasoning_trace = ReasoningTrace(
        fired_rules=[],
        cluster_contributions=[
            ClusterContribution(cluster="Wyckoff", impact="VETO" if constraints.wyckoff_veto else "NEUTRAL"),
            ClusterContribution(
                cluster="Trend",
                impact="NEUTRAL" if flags.get("technical_summary") == "COMPUTED" else "NOT_COMPUTED",
            ),
            ClusterContribution(
                cluster="Momentum",
                impact="NEUTRAL" if flags.get("technical_summary") == "COMPUTED" else "NOT_COMPUTED",
            ),
            ClusterContribution(
                cluster="Volatility",
                impact=(
                    "FORBID_LONG_PREMIUM"
                    if constraints.iv_forbids_long_premium
                    else ("NEUTRAL" if flags.get("volatility_summary") == "COMPUTED" else "NOT_COMPUTED")
                ),
            ),
            ClusterContribution(
                cluster="Dealer",
                impact=(
                    "TIMING_VETO"
                    if constraints.dealer_timing_veto
                    else ("NEUTRAL" if flags.get("dealer_summary") == "COMPUTED" else "NOT_COMPUTED")
                ),
            ),
            ClusterContribution(
                cluster="Meta",
                impact="MISSING_DATA" if missing_data else "NEUTRAL",
            ),
        ],
        supporting_factors=[],
        blocking_factors=[reason],
    )

    confidence_summary = ConfidenceSummary(
        confidence_type="RELATIVE",
        ranking_basis="Primary outranks alternatives by construction",
        confidence_gap_notes=None,
    )

    metadata = _build_base_metadata(request, provider_id, model_id, model_version, None, flags)
    return TradeRecommendation(
        snapshot_metadata=metadata,
        primary_recommendation=primary,
        alternative_recommendations=alternatives,
        reasoning_trace=reasoning_trace,
        confidence_summary=confidence_summary,
        missing_data_declaration=missing_data,
        guardrails_and_disclaimers=list(GUARDRAILS_AND_DISCLAIMERS),
    )


async def invoke_planning_agent(
    provider_id: str,
    model_id: str,
    request_payload: Any,
    invocation_config: Any,
) -> TradeRecommendation:
    try:
        request = _model_validate(AIRequest, request_payload)
    except Exception as exc:
        fallback_request = AIRequest(
            context=RequestContext(
                symbol="UNKNOWN",
                snapshot_time="UNKNOWN",
                market_structure=MarketStructure(
                    wyckoff_regime="UNKNOWN",
                    wyckoff_events=[],
                    regime_confidence=0.0,
                ),
                technical_summary={},
                volatility_summary={},
                dealer_summary={},
            ),
            option_context=OptionContext(
                spot_price=0.0,
                expiration_buckets=[ExpirationBucket.SHORT],
                moneyness_bands=[MoneynessBand.ATM],
                liquidity_constraints=LiquidityConstraints(min_open_interest=0, min_volume=0),
            ),
            authority_constraints=AuthorityConstraints(
                wyckoff_veto=True,
                iv_forbids_long_premium=False,
                dealer_timing_veto=False,
            ),
            instructions=InstructionBlock(
                objective="produce ranked trade recommendations",
                forbidden_actions=[],
            ),
        )
        flags = _data_completeness_flags(fallback_request)
        missing = _missing_data_declaration(flags)
        reason = f"Missing inputs: {str(exc)}"
        provider_key = str(provider_id or "unknown").lower()
        return _build_fallback_output(
            fallback_request,
            provider_key,
            model_id or "UNKNOWN",
            "unknown",
            flags,
            missing,
            reason,
        )

    config = _model_validate(InvocationConfig, invocation_config)
    provider_key = str(provider_id or "").lower()
    if provider_key not in ALLOWED_PROVIDERS or not model_id:
        flags = _data_completeness_flags(request)
        missing = _missing_data_declaration(flags)
        reason = "Invalid provider or model selection"
        return _build_fallback_output(
            request,
            provider_key or "unknown",
            model_id or "UNKNOWN",
            config.model_version,
            flags,
            missing,
            reason,
        )
    invocation_id = config.invocation_id or _invocation_id_from_request(request)

    flags = _data_completeness_flags(request)
    missing = _missing_data_declaration(flags)

    request_json = _canonical_json(_model_dump(request))
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(request_json, missing)

    if config.ai_debug:
        _log_structured(
            "ai_request",
            {
                "invocation_id": invocation_id,
                "ai_provider": provider_key,
                "ai_model": model_id,
                "request_payload": request_json,
            },
        )

    if config.ai_dry_run:
        response = _build_fallback_output(
            request,
            provider_key,
            model_id,
            config.model_version,
            flags,
            missing,
            "Dry-run mode: deterministic stub response",
        )
        if config.ai_debug:
            _log_structured(
                "ai_response_raw",
                {
                    "invocation_id": invocation_id,
                    "ai_provider": provider_key,
                    "ai_model": model_id,
                    "raw_response": _canonical_json(_model_dump(response)),
                },
            )
            _log_structured(
                "ai_response_validation",
                {
                    "invocation_id": invocation_id,
                    "status": "PASS",
                    "reasons": [],
                },
            )
        return response

    from core.providers import get_ai_provider

    try:
        provider = get_ai_provider(provider_key)
        provider_response = await provider.invoke(model_id, system_prompt, user_prompt)
        raw_response = provider_response.content.strip()
    except Exception as exc:
        if config.ai_debug:
            _log_structured(
                "ai_response_validation",
                {"invocation_id": invocation_id, "status": "FAIL", "reasons": [str(exc)]},
            )
        reason = f"AI invocation failed: {str(exc)}"
        return _build_fallback_output(
            request,
            provider_key,
            model_id,
            config.model_version,
            flags,
            missing,
            reason,
        )

    if config.ai_debug:
        _log_structured(
            "ai_response_raw",
            {
                "invocation_id": invocation_id,
                "ai_provider": provider_key,
                "ai_model": model_id,
                "raw_response": raw_response,
            },
        )

    try:
        parsed = json.loads(raw_response)
        candidate = _model_validate(TradeRecommendation, parsed)
    except Exception as exc:
        if config.ai_debug:
            _log_structured(
                "ai_response_validation",
                {"invocation_id": invocation_id, "status": "FAIL", "reasons": [str(exc)]},
            )
        reason = f"Malformed AI output: {str(exc)}"
        return _build_fallback_output(
            request,
            provider_key,
            model_id,
            config.model_version,
            flags,
            missing,
            reason,
        )

    constraint_error = _validate_constraints(request, candidate)
    if constraint_error:
        if config.ai_debug:
            _log_structured(
                "ai_response_validation",
                {"invocation_id": invocation_id, "status": "FAIL", "reasons": [constraint_error]},
            )
        return _build_fallback_output(
            request,
            provider_key,
            model_id,
            config.model_version,
            flags,
            missing,
            constraint_error,
        )

    confidence_summary = ConfidenceSummary(
        confidence_type="RELATIVE",
        ranking_basis="Primary outranks alternatives by construction",
        confidence_gap_notes=None,
    )

    final_metadata = _build_base_metadata(
        request,
        provider_key,
        model_id,
        config.model_version,
        provider_response.model_version,
        flags,
    )

    final_output = TradeRecommendation(
        snapshot_metadata=final_metadata,
        primary_recommendation=candidate.primary_recommendation,
        alternative_recommendations=candidate.alternative_recommendations,
        reasoning_trace=candidate.reasoning_trace,
        confidence_summary=confidence_summary,
        missing_data_declaration=missing,
        guardrails_and_disclaimers=list(GUARDRAILS_AND_DISCLAIMERS),
    )

    if config.ai_debug:
        _log_structured(
            "ai_response_validation",
            {"invocation_id": invocation_id, "status": "PASS", "reasons": []},
        )
    return final_output


AnalysisContext = AIRequest
