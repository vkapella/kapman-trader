---
system: KapMan
doc_type: metric
version: 1.0
last_validated: 2026-02-13
market_regime: all
confidence: strong
tags:
  - scoring
  - composite_score
  - conviction
---

# SCORING_COMPOSITE

## [KapMan] Objective
Document implemented composite-scoring behavior and explicitly identify missing conviction-threshold logic.

## [KapMan] Implementation Status
[NOT YET IMPLEMENTED] for Composite Score formula, conviction buckets, and signal-threshold mapping.  
Current runtime behavior is schema storage support plus context pass-through into C4.

## [KapMan] Decision Table
| Condition | Action | Threshold |
|---|---|---|
| Composite Score persisted to `daily_snapshots.composite_score` | Accept numeric value | `NUMERIC(6,2)` precision only |
| C4 context payload build | Read Composite Score as-is | N/A |
| Composite conviction logic requested | No runtime implementation branch | N/A |

## [KapMan] Rule Catalog
### RULE COMPOSITE_SCORE_001
RULE_ID: COMPOSITE_SCORE_001  
SOURCE_FILE: db/migrations/0001_schema_baseline_2026_01.sql  
SOURCE_LINE: 149  
CATEGORY: Scoring  
RULE_TYPE: Constraint  
CONFIDENCE: STRONG  
DESCRIPTION: Composite Score column exists with numeric precision constraint but no explicit min/max check.
LOGIC:
- IF: Writing `daily_snapshots.composite_score`
- THEN: Value must conform to `NUMERIC(6,2)` type
- THRESHOLD: Precision/scale only; no bounded range
CONTEXT: Data type is enforced, but semantic score range is not.

### RULE COMPOSITE_SCORE_002
RULE_ID: COMPOSITE_SCORE_002  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 188, 208  
CATEGORY: Scoring  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: Composite Score is loaded from daily snapshot and passed to AI context without transformation.
LOGIC:
- IF: C4 reads daily snapshot row
- THEN: Copy `composite_score` into payload
- THRESHOLD: None
CONTEXT: Composite Score functions as an input field, not a computed runtime signal.

### RULE COMPOSITE_SCORE_003
RULE_ID: COMPOSITE_SCORE_003  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 177-213  
CATEGORY: Scoring  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: No composite formula, conviction threshold, or branch-to-action mapping is implemented in active runtime code scanned.
LOGIC:
- IF: Looking for formula components, weighted aggregation, or conviction cutoffs
- THEN: No implementation found in active metrics modules
- THRESHOLD: N/A
CONTEXT: Prevents accidental use of nonexistent conviction rules.

## [KapMan] Anti-Patterns
- NEVER assume Composite Score has enforced conviction thresholds in current runtime.
- NEVER infer signal generation from Composite Score without explicit formula implementation.
- NEVER treat numeric precision as semantic validation of strategy quality.

## [KapMan] Source Mapping
- `db/migrations/0001_schema_baseline_2026_01.sql`: 149
- `core/metrics/c4_batch_ai_screening_job.py`: 177-213

## [KapMan] Change Log
| Date | Version | Change |
|---|---|---|
| 2026-02-13 | 1.0 | Initial Composite Score implementation status extraction. |
