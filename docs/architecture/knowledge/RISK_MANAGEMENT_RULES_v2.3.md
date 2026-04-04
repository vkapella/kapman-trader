---
system: KapMan
doc_type: risk_rule
version: 2.3
last_validated: 2026-04-04
market_regime: all
confidence: strong
tags:
  - risk
  - stop_loss
  - position_size
  - guardrails
---

# RISK_MANAGEMENT_RULES

## [KapMan] Objective
Document implemented risk-management behavior and identify missing deterministic risk controls.

## [KapMan] Implementation Status
[NOT YET IMPLEMENTED] for deterministic Position Size, Stop Loss, portfolio heat, and hedging formulas in active production recommendation flow.

## [KapMan] Decision Table
| Risk-Control Area | Current Runtime Behavior |
|---|---|
| Position Size | No runtime formula found |
| Stop Loss | Persisted recommendation row sets null |
| Profit Target | Persisted recommendation row sets null |
| Risk-Reward Ratio | Persisted recommendation row sets null |
| Portfolio Heat | No runtime formula found |
| Hedging Rules | No deterministic engine rule found (only action enum supports `HEDGE`) |

## [KapMan] Rule Catalog
### RULE RISK_001
RULE_ID: RISK_001  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 633-647  
CATEGORY: Risk  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: C4 persistence intentionally omits Stop Loss, profit target, and risk-reward values.
LOGIC:
- IF: Writing recommendation tuple
- THEN: `entry_price_target = None`
- AND: `stop_loss = None`
- AND: `profit_target = None`
- AND: `risk_reward_ratio = None`
- THRESHOLD: Hardcoded null assignment
CONTEXT: Prevents unvalidated risk numbers from entering production recommendations.

### RULE RISK_002
RULE_ID: RISK_002  
SOURCE_FILE: core/providers/ai/base.py  
SOURCE_LINE: 306-311  
CATEGORY: Risk  
RULE_TYPE: Constraint  
CONFIDENCE: STRONG  
DESCRIPTION: Built-in disclaimers explicitly state recommendations do not replace risk controls.
LOGIC:
- IF: Final recommendation output is produced
- THEN: Include disclaimer text that recommendation is not a substitute for risk controls
- THRESHOLD: N/A
CONTEXT: Soft guardrail against treating signal output as complete risk plan.

### RULE RISK_003
RULE_ID: RISK_003  
SOURCE_FILE: db/migrations/0001_schema_baseline_2026_01.sql  
SOURCE_LINE: 175-178  
CATEGORY: Risk  
RULE_TYPE: Constraint  
CONFIDENCE: STRONG  
DESCRIPTION: Recommendation schema has fields for entry/Stop Loss/profit/risk-reward but no DB check constraints on these values.
LOGIC:
- IF: Writing recommendation pricing/risk fields
- THEN: Field type must match numeric schema
- AND: No bounded validation rule is enforced at DB level
- THRESHOLD: Numeric precision only
CONTEXT: Confirms storage support exists before formula implementation.

### RULE RISK_004
RULE_ID: RISK_004  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 36-39, 743-748, 949-951  
CATEGORY: Risk  
RULE_TYPE: Classification  
CONFIDENCE: STRONG  
DESCRIPTION: Risk-relevant option-context constants and authority constraints are not actively injected in current C4 invocation path.
LOGIC:
- IF: C4 invokes planning agent
- THEN: `option_context={}` and `authority_constraints={}` and `instructions={}`
- THRESHOLD: constants (`min_open_interest=500`, `min_volume=100`, expiration/moneyness defaults) remain unused
CONTEXT: Highlights gap between configured intent and runtime-enforced risk controls.

### RULE RISK_005
RULE_ID: RISK_005
SOURCE_FILE: KAPMAN_PROJECT_INSTRUCTIONS_v2.3.md (interim guidance)
SOURCE_LINE: N/A
CATEGORY: Risk
RULE_TYPE: Threshold
CONFIDENCE: STRONG
DESCRIPTION: Interim regime-adaptive position size caps for Claude trade
output. Active until deterministic formula is implemented in C4.
LOGIC:
- IF: Wyckoff MARKUP + DGPI ≥ 50 + Full chain (≥25 contracts) + IV/HV < 1.2
- THEN: Max position 3% of portfolio. Structure: long call.
- IF: Wyckoff MARKUP + DGPI 20-49 + Full chain + IV/HV < 1.2
- THEN: Max position 2% of portfolio. Structure: long call.
- IF: Wyckoff MARKUP + DGPI ≥ 20 + Full chain + IV/HV ≥ 1.2
- THEN: Max position 2% of portfolio. Structure: vertical spread mandatory.
- IF: Wyckoff MARKUP + Limited chain (5-24 contracts) + any DGPI
- THEN: Max position 1% of portfolio. Max 2-3 contracts.
- IF: Wyckoff ACCUMULATION (pre-SOS, no confirmed Spring)
- THEN: Max position 0.5-1% of portfolio. CONDITIONAL status only.
- IF: Wyckoff DISTRIBUTION or MARKDOWN
- THEN: No new long-premium entries. CSPs and hedges only.
- IF: Macro gate active (SPY below flip AND SPY DGPI ≤ -20)
- THEN: Override all above. No new long-call entries regardless of
  individual ticker regime.
- ABSOLUTE MAX: No single position exceeds 5% of total portfolio.
- THRESHOLD: Percentages apply to combined portfolio value across
  both Schwab and Fidelity accounts.
CONTEXT: Interim caps for Claude HTML report output only. C4 persistence
continues to store null for position size per RISK_001. When a
deterministic formula is implemented in C4, this rule will be superseded
by POSITION_SIZING_001 in a new POSITION_SIZING_RULES_v2.3.md file.

## [KapMan] Anti-Patterns
- NEVER assume Stop Loss exists in persisted recommendations today.
- NEVER assume Position Size logic is computed by the current C4 pipeline.
- NEVER treat schema fields alone as proof of active risk control.
- NEVER assume authority constraints are active in C4 without explicit payload injection.
- NEVER recommend a long-call position when macro gate is active
  (SPY below flip AND DGPI ≤ -20), regardless of individual ticker score.
- NEVER exceed 5% single-position allocation under any condition.
- NEVER apply RISK_005 percentage caps to CSP margin requirement
  calculations — CSP sizing is governed by margin capacity, not premium
  percentage.

## [KapMan] Source Mapping
- `core/metrics/c4_batch_ai_screening_job.py`: 36-39, 633-647, 743-748, 949-951
- `core/providers/ai/base.py`: 306-311
- `db/migrations/0001_schema_baseline_2026_01.sql`: 175-178

## [KapMan] Change Log
| Date       | Version | Change |
|------------|---------|--------|
| 2026-02-13 | 1.0     | Initial risk-control implementation gap extraction. |
| 2026-04-04 | 2.3     | Added RULE RISK_005: interim regime-adaptive position size caps for Claude report output. Added macro gate override. Updated anti-patterns. Standardized to v2.3 production baseline. |
