---
system: KapMan
doc_type: metric
version: 1.0
last_validated: 2026-02-13
market_regime: all
confidence: strong
tags:
  - scoring
  - spring_score
  - validation
---

# SCORING_SPRING_SCORE

## [KapMan] Objective
Document implemented Spring Score behavior in runtime code and identify missing Spring Score formula logic.

## [KapMan] Implementation Status
[NOT YET IMPLEMENTED] for Spring Score formula and component scoring model.  
Implemented behavior is currently storage-range validation plus pass-through consumption.

## [KapMan] Decision Table
| Condition | Action | Threshold |
|---|---|---|
| Spring Score persisted to `daily_snapshots.spring_score` | Accept | Integer `0..12` |
| Spring Score outside range | Reject by DB constraint | `<0` or `>12` |
| C4 context payload build | Read Spring Score field without recomputation | N/A |

## [KapMan] Rule Catalog
### RULE SPRING_SCORE_001
RULE_ID: SPRING_SCORE_001  
SOURCE_FILE: db/migrations/0001_schema_baseline_2026_01.sql  
SOURCE_LINE: 148  
CATEGORY: Scoring  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: Spring Score persistence is hard-bounded by database check constraint.
LOGIC:
- IF: Writing `daily_snapshots.spring_score`
- THEN: Value must satisfy `0 <= spring_score <= 12`
- THRESHOLD: 0 to 12 inclusive
CONTEXT: Protects fixed Spring Score scale integrity.

### RULE SPRING_SCORE_002
RULE_ID: SPRING_SCORE_002  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 187, 207  
CATEGORY: Scoring  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: Spring Score is read from `daily_snapshots` and passed into AI context unchanged.
LOGIC:
- IF: C4 loads daily snapshot row
- THEN: Copy `spring_score` into `daily_snapshot` payload
- THRESHOLD: None
CONTEXT: Confirms Spring Score is upstream context, not computed in C4.

### RULE SPRING_SCORE_003
RULE_ID: SPRING_SCORE_003  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 177-213  
CATEGORY: Scoring  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: No Spring Score formula branch exists in active runtime metrics jobs inspected here.
LOGIC:
- IF: Looking for Spring Score feature components, weighted formula, or signal thresholds
- THEN: No runtime implementation found; only data-field pass-through exists
- THRESHOLD: N/A
CONTEXT: Documents implementation gap explicitly to prevent false assumptions.

## [KapMan] Anti-Patterns
- NEVER treat stored Spring Score as proof of current formula implementation.
- NEVER write Spring Score outside `0..12`.
- NEVER infer Spring Score decision logic from C4; no formula is applied there.

## [KapMan] Source Mapping
- `db/migrations/0001_schema_baseline_2026_01.sql`: 148
- `core/metrics/c4_batch_ai_screening_job.py`: 177-213

## [KapMan] Change Log
| Date | Version | Change |
|---|---|---|
| 2026-02-13 | 1.0 | Initial Spring Score implementation status and constraint extraction. |
