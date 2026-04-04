---
system: KapMan
doc_type: strategy
version: 2.3
last_validated: 2026-04-04
market_regime: all
confidence: strong
tags:
  - signals
  - entry
  - exit
  - ai_recommendations
---

# SIGNAL_ENTRY_EXIT_RULES

## [KapMan] Objective
Document implemented entry/exit recommendation rules, normalization logic, and guardrails in C4 and AI recommendation validators.

## [KapMan] Decision Table
| Raw Recommendation Action | Normalized Direction | Stored Action |
|---|---|---|
| `PROCEED` | `LONG` | `BUY` |
| `PROCEED` | `SHORT` | `SELL` |
| `PROCEED` | `NEUTRAL` | `HOLD` |
| `HOLD` or `AVOID` | Any | `HOLD` |
| `BUY` / `SELL` / `HEDGE` | Any | Pass-through |
| null/unknown | Any | `HOLD` |

| Blocking Constraint (base agent path) | Required Primary Action | Additional Requirement |
|---|---|---|
| `wyckoff_veto=true` | `NO_TRADE` | Alternatives required |
| `dealer_timing_veto=true` | Not `ENTER` | Alternatives required |
| `iv_forbids_long_premium=true` | Primary not `LONG_CALL`/`LONG_PUT` | At least one long-premium alternative required |

## [KapMan] Rule Catalog
### RULE SIGNAL_001
RULE_ID: SIGNAL_001  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 464-474  
CATEGORY: Signal  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: Direction is normalized to LONG, SHORT, or NEUTRAL only.
LOGIC:
- IF: Raw direction in `{BULLISH, LONG}`
- THEN: Store `LONG`
- IF: Raw direction in `{BEARISH, SHORT}`
- THEN: Store `SHORT`
- ELSE: Store `NEUTRAL`
- THRESHOLD: Enumerated mapping only
CONTEXT: Prevents downstream action mapping from unbounded direction labels.

### RULE SIGNAL_002
RULE_ID: SIGNAL_002  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 484-498  
CATEGORY: Signal  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: Raw action is mapped to recommendation_action enum behavior.
LOGIC:
- IF: Action `PROCEED` and direction `LONG`
- THEN: Store `BUY`
- IF: Action `PROCEED` and direction `SHORT`
- THEN: Store `SELL`
- IF: Action `HOLD` or `AVOID`
- THEN: Store `HOLD`
- IF: Action in `{BUY, SELL, HEDGE}`
- THEN: Store value unchanged
- ELSE: Store `HOLD`
- THRESHOLD: Mapping table above
CONTEXT: Converts model phrasing into persisted trading actions.

### RULE SIGNAL_003
RULE_ID: SIGNAL_003  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 512-521  
CATEGORY: Signal  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: Confidence is accepted only as decimal score in `[0,1]` and quantized.
LOGIC:
- IF: Confidence parses as decimal and `0 <= score <= 1`
- THEN: Store `score.quantize(0.001)`
- ELSE: Store null confidence
- THRESHOLD: Lower bound `0`, upper bound `1`, precision `0.001`
CONTEXT: Aligns with DB confidence check and schema expectations.

### RULE SIGNAL_004
RULE_ID: SIGNAL_004  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 501-509  
CATEGORY: Signal  
RULE_TYPE: Classification  
CONFIDENCE: STRONG  
DESCRIPTION: Option strategy labels are normalized to supported enum set.
LOGIC:
- IF: Strategy in `{LONG_CALL, LONG_PUT, CSP, VERTICAL_SPREAD}`
- THEN: Pass-through
- IF: Strategy in `{CALL_DEBIT_SPREAD, PUT_DEBIT_SPREAD}`
- THEN: Map to `VERTICAL_SPREAD`
- ELSE: Store null
- THRESHOLD: Enumerated mapping only
CONTEXT: Ensures compatibility with persisted option strategy enum.

### RULE SIGNAL_005
RULE_ID: SIGNAL_005  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 633-653  
CATEGORY: Signal  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: Persisted recommendation row intentionally omits deterministic entry/exit pricing fields.
LOGIC:
- IF: Building recommendation tuple for persistence
- THEN: Set `entry_price_target`, `stop_loss`, `profit_target`, `risk_reward_ratio`, `option_strike`, `option_expiration` to null
- THRESHOLD: Hardcoded null assignment in tuple positions
CONTEXT: Prevents hallucinated trade construction details from being stored as facts.

### RULE SIGNAL_006
RULE_ID: SIGNAL_006  
SOURCE_FILE: core/providers/ai/base.py  
SOURCE_LINE: 169-173, 196-200  
CATEGORY: Signal  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: NO_TRADE recommendations must use strategy class NONE.
LOGIC:
- IF: `action == NO_TRADE`
- THEN: `strategy_class` must equal `NONE`
- THRESHOLD: Exact enum equality
CONTEXT: Prevents logically inconsistent "no trade" recommendations with active option structures.

### RULE SIGNAL_007
RULE_ID: SIGNAL_007  
SOURCE_FILE: core/providers/ai/base.py  
SOURCE_LINE: 255-264  
CATEGORY: Signal  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: Alternative recommendations must always have lower confidence than primary recommendation.
LOGIC:
- IF: Alternative recommendation exists
- THEN: `alt.confidence_score < primary.confidence_score`
- THRESHOLD: Strict inequality
CONTEXT: Enforces rank ordering consistency.

### RULE SIGNAL_008
RULE_ID: SIGNAL_008  
SOURCE_FILE: core/providers/ai/base.py  
SOURCE_LINE: 441-456  
CATEGORY: Signal  
RULE_TYPE: Conditional  
CONFIDENCE: STRICT  
DESCRIPTION: Authority constraints gate valid primary action and require alternatives when blocking conditions are active.
LOGIC:
- IF: `wyckoff_veto == True`
- THEN: Primary action must be `NO_TRADE`
- IF: `dealer_timing_veto == True`
- THEN: Primary action must not be `ENTER`
- IF: `iv_forbids_long_premium == True`
- THEN: Primary strategy must not be `LONG_CALL` or `LONG_PUT`
- AND: At least one long-premium alternative must exist
- AND: Alternatives list must be non-empty whenever any veto/forbid is active
- THRESHOLD: Boolean hard constraints
CONTEXT: Converts risk vetoes into deterministic recommendation structure.
CONTEXT (add): iv_forbids_long_premium trigger requires IV/HV ratio from Schwab
ATM chain (authoritative). Polygon avg_iv via get_options_metrics(symbol, include=['volatility']) or
get_batch_options_metrics(symbols=[], include=['volatility']) is acceptable
for Pass 1 directional screening only (batch: max 30 symbols per call) —
not sufficient alone to trigger this veto in Pass 2.
### RULE SIGNAL_009
RULE_ID: SIGNAL_009  
SOURCE_FILE: core/providers/ai/base.py  
SOURCE_LINE: 492-529  
CATEGORY: Signal  
RULE_TYPE: Formula  
CONFIDENCE: STRONG  
DESCRIPTION: Fallback recommendation policy sets deterministic NO_TRADE/WAIT behavior and confidence deltas.
LOGIC:
- IF: Fallback path is used
- THEN: Primary action = `NO_TRADE`
- AND: Primary confidence = `75` when `wyckoff_veto`, else `60`
- AND: Add `WAIT` alternative with confidence `primary - 20`
- AND: If `iv_forbids_long_premium`, add long-premium `ENTER` alternative with confidence `primary - 30`
- THRESHOLD: Base confidence `75/60`, deltas `-20`, `-30`
CONTEXT: Guarantees structured output even when provider output is invalid.

### RULE SIGNAL_010
RULE_ID: SIGNAL_010  
SOURCE_FILE: core/providers/ai/base.py  
SOURCE_LINE: 367-373  
CATEGORY: Signal  
RULE_TYPE: Classification  
CONFIDENCE: STRONG  
DESCRIPTION: Event-derived fallback direction uses Sign of Strength (SOS) and Sign of Weakness (SOW) priority.
LOGIC:
- IF: Events include Sign of Strength (SOS)
- THEN: Direction = `BULLISH`
- IF: Events include Sign of Weakness (SOW)
- THEN: Direction = `BEARISH`
- ELSE: Direction = `NEUTRAL`
- THRESHOLD: Event presence only
CONTEXT: Provides deterministic directional fallback from Wyckoff event context.

## [KapMan] Anti-Patterns
- NEVER persist entry price, Stop Loss, profit target, or risk-reward as inferred values in current C4 path.
- NEVER allow alternative confidence to exceed or equal primary confidence.
- NEVER emit `NO_TRADE` with non-`NONE` strategy class.
- NEVER bypass veto-driven alternatives when blocking constraints are active.

## [KapMan] Source Mapping
- `core/metrics/c4_batch_ai_screening_job.py`: 464-653
- `core/providers/ai/base.py`: 169-173, 196-200, 255-264, 367-373, 441-456, 492-529

## [KapMan] Implementation Gap
[NOT YET IMPLEMENTED]: Deterministic entry price, Stop Loss, profit target, and risk-reward formulas are not computed in current persisted recommendation flow.

## [KapMan] Change Log
| Date | Version | Change |
|---|---|---|
| 2026-02-13 | 1.0 | Initial extraction of signal normalization, gating, and fallback behavior. |
| 2026-03-27 | 2.1 | Added IV source authority rules (Polygon avg_iv for Pass 1, Schwab ATM for Pass 2). |
| 2026-03-28 | 2.2 | Updated RULE SIGNAL_008 context addendum: replaced deprecated Polygon tool name with canonical get_options_metrics / get_batch_options_metrics(include=['volatility']) references. |

| 2026-04-04 | 2.3 | Standardized to v2.3 production baseline. No content changes. |
