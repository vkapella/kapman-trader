---
system: KapMan
doc_type: metric
version: 1.0
last_validated: 2026-02-13
market_regime: all
confidence: strong
tags:
  - scoring
  - bc_score
  - validation
---

# SCORING_BC_SCORE

## [KapMan] Objective
Document implemented BC Score behavior in runtime code and identify missing BC Score formula logic.

## [KapMan] Implementation Status
[NOT YET IMPLEMENTED] for BC Score calculation formula and component weighting.  
Implemented behavior is currently storage-range validation plus pass-through consumption.

## [KapMan] Decision Table
| Condition | Action | Threshold |
|---|---|---|
| BC Score persisted to `daily_snapshots.bc_score` | Accept | Integer `0..28` |
| BC Score outside range | Reject by DB constraint | `<0` or `>28` |
| C4 context payload build | Read BC Score field without recomputation | N/A |

## [KapMan] Rule Catalog
### RULE BC_SCORE_001
RULE_ID: BC_SCORE_001  
SOURCE_FILE: db/migrations/0001_schema_baseline_2026_01.sql  
SOURCE_LINE: 147  
CATEGORY: Scoring  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: BC Score persistence is hard-bounded by database check constraint.
LOGIC:
- IF: Writing `daily_snapshots.bc_score`
- THEN: Value must satisfy `0 <= bc_score <= 28`
- THRESHOLD: 0 to 28 inclusive
CONTEXT: Prevents invalid BC Score scale values from entering storage.

### RULE BC_SCORE_002
RULE_ID: BC_SCORE_002  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 186, 206  
CATEGORY: Scoring  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: BC Score is read from `daily_snapshots` and included in AI context payload without formula recomputation.
LOGIC:
- IF: C4 loads daily snapshot row
- THEN: Copy `bc_score` field into `daily_snapshot` payload
- THRESHOLD: None
CONTEXT: Confirms BC Score is treated as upstream-provided context only.

### RULE BC_SCORE_003
RULE_ID: BC_SCORE_003  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 177-213  
CATEGORY: Scoring  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: No BC Score formula branch exists in the inspected runtime scoring pipeline.
LOGIC:
- IF: Looking for BC Score component formula, weighted sum, or threshold-to-signal conversion
- THEN: No implementation found in active metrics jobs; only field read-through occurs
- THRESHOLD: N/A
CONTEXT: Flags scoring gap between schema support and implemented computation.

## [KapMan] Anti-Patterns
- NEVER assume BC Score values represent a computed formula in current runtime.
- NEVER bypass the `0..28` bound when writing BC Score.
- NEVER infer BC Score component weights from C4 payload usage; C4 does not compute BC Score.

## [KapMan] Source Mapping
- `db/migrations/0001_schema_baseline_2026_01.sql`: 147
- `core/metrics/c4_batch_ai_screening_job.py`: 177-213

## [KapMan] Change Log
| Date | Version | Change |
|---|---|---|
| 2026-02-13 | 1.0 | Initial BC Score implementation status and constraint extraction. |
