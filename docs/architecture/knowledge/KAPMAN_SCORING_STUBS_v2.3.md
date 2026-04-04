---
system: KapMan
doc_type: metric
version: 2.3
last_validated: 2026-04-04
market_regime: all
confidence: strong
tags:
  - scoring
  - bc_score
  - spring_score
  - composite_score
  - stubs
---

# KAPMAN_SCORING_STUBS

## [KapMan] Objective
Consolidated stub record for BC Score, Spring Score, and Composite Score.
All three scoring modules are NOT YET IMPLEMENTED in the production
pipeline. This file replaces SCORING_BC_SCORE.md, SCORING_SPRING_SCORE.md,
and SCORING_COMPOSITE.md (archived 2026-04-04).

## [KapMan] Implementation Status
[NOT YET IMPLEMENTED] — BC Score formula, Spring Score formula, and
Composite Score formula are all absent from active runtime code.
Current behavior: values are read from daily_snapshots and passed to
AI context as-is. No computation occurs in C4 or any metrics job.

## [KapMan] Storage Bounds (DB-enforced)
| Score           | Column                          | Type         | Constraint     |
|-----------------|---------------------------------|--------------|----------------|
| BC Score        | daily_snapshots.bc_score        | Integer      | 0 ≤ value ≤ 28 |
| Spring Score    | daily_snapshots.spring_score    | Integer      | 0 ≤ value ≤ 12 |
| Composite Score | daily_snapshots.composite_score | NUMERIC(6,2) | Precision only |

## [KapMan] Interpretation Thresholds (Claude report use only)
Interim guidance for report output until formulas are implemented.
NOT computed by C4. Do not treat as authoritative signal logic.

### Spring Score
| Range | Interpretation             | Report Action                            |
|-------|----------------------------|------------------------------------------|
| 10-12 | High-quality Spring        | Eligible for ACT, full size per RISK_005 |
| 7-9   | Moderate Spring signal     | MONITOR → upgrade to ACT if SOS follows  |
| 4-6   | Weak Spring                | CONDITIONAL only, undersized             |
| 0-3   | No Spring or failed Spring | Skip / MONITOR only                      |

### BC Score
| Range | Interpretation         | Report Action                              |
|-------|------------------------|--------------------------------------------|
| 22-28 | High-conviction BC     | Strong DISTRIBUTION — block long calls     |
| 14-21 | Moderate BC            | Caution on long entries, reduce size       |
| 7-13  | Weak BC signal         | Monitor for SOW confirmation before acting |
| 0-6   | No BC or minimal       | Neutral, no BC-driven action               |

### Composite Score
No interpretation thresholds defined pending formula implementation.
Pass through as context only. Do not gate entries on Composite Score.

## [KapMan] Rule Catalog

### RULE SCORING_001
RULE_ID: SCORING_001
SOURCE_FILE: db/migrations/0001_schema_baseline_2026_01.sql;
             core/metrics/c4_batch_ai_screening_job.py
SOURCE_LINE: 147-149; 177-213
CATEGORY: Scoring
RULE_TYPE: Constraint
CONFIDENCE: STRICT
DESCRIPTION: All three scores are pass-through context values only.
No formula computation occurs anywhere in the active pipeline.
LOGIC:
- IF: BC Score, Spring Score, or Composite Score is present in data
- THEN: Include as context in AI payload unchanged
- NEVER: Compute, recalculate, or infer these scores in Claude output
- NEVER: Write BC Score outside 0..28 or Spring Score outside 0..12
- NEVER: Block or approve a trade entry based solely on Composite Score
  until a formula and threshold are formally implemented

## [KapMan] Anti-Patterns
- NEVER treat stored scores as proof of computed formula results.
- NEVER infer BC Score component weights or Spring Score components
  from C4 payload — C4 does not compute these values.
- NEVER assume Composite Score has conviction thresholds in current runtime.
- NEVER exceed storage bounds (0..28 for BC Score, 0..12 for Spring Score).

## [KapMan] Source Mapping
- `db/migrations/0001_schema_baseline_2026_01.sql`: 147-149
- `core/metrics/c4_batch_ai_screening_job.py`: 177-213
- Replaces: SCORING_BC_SCORE.md, SCORING_SPRING_SCORE.md,
  SCORING_COMPOSITE.md (all archived 2026-04-04)

## [KapMan] Change Log
| Date       | Version | Change |
|------------|---------|--------|
| 2026-04-04 | 2.3     | Initial file. Consolidated three scoring stub files into one. Added interim interpretation thresholds for Spring Score and BC Score. Added SCORING_001 pass-through constraint. Standardized to v2.3 production baseline. |
