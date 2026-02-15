---
system: KapMan
doc_type: risk_rule
version: 1.0
last_validated: 2026-02-13
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

## [KapMan] Anti-Patterns
- NEVER assume Stop Loss exists in persisted recommendations today.
- NEVER assume Position Size logic is computed by the current C4 pipeline.
- NEVER treat schema fields alone as proof of active risk control.
- NEVER assume authority constraints are active in C4 without explicit payload injection.

## [KapMan] Source Mapping
- `core/metrics/c4_batch_ai_screening_job.py`: 36-39, 633-647, 743-748, 949-951
- `core/providers/ai/base.py`: 306-311
- `db/migrations/0001_schema_baseline_2026_01.sql`: 175-178

## [KapMan] Change Log
| Date | Version | Change |
|---|---|---|
| 2026-02-13 | 1.0 | Initial risk-control implementation gap extraction. |
