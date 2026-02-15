---
system: KapMan
doc_type: strategy
version: 1.0
last_validated: 2026-02-13
market_regime: all
confidence: strong
tags:
  - pipeline
  - orchestration
  - dependencies
  - scheduling
---

# PIPELINE_ORCHESTRATION

## [KapMan] Objective
Capture implemented pipeline phase ordering, dependency gates, and sequencing constraints across daily and catch-up execution scripts.

## [KapMan] Decision Table
| Script | Implemented Order |
|---|---|
| `scripts/cron/kapman_daily_run.sh` | A1 watchlist -> A0 OHLCV -> A1 options -> A2 -> A4 -> A3 -> B2 -> B1 -> B4 -> B4.1 -> dashboards |
| `scripts/cron/catchup_START_DATE_to_END_DATE.sh` | A0 -> A1 -> A2 -> A4 -> A3 -> B2 -> B1 -> B4.1 -> B4 |
| `scripts/cron/resume-from-A3.sh` | A3 -> B2 -> B1 -> B4 -> B4.1 |

| B2 Dependency Gate | Rule |
|---|---|
| Driver dates | Use existing `daily_snapshots` NY dates, not prior B2 output |
| Snapshot coverage | Fail fast unless every `(ticker, target_date)` snapshot exists |
| OHLCV quality | Reject duplicate/non-monotonic/gapped (`>4` days) histories |

## [KapMan] Rule Catalog
### RULE PIPELINE_001
RULE_ID: PIPELINE_001  
SOURCE_FILE: scripts/cron/kapman_daily_run.sh  
SOURCE_LINE: 95-176  
CATEGORY: Strategy  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: Daily cron execution enforces full stage order ending with B4 before B4.1.
LOGIC:
- IF: Running daily cron path
- THEN: Execute A-stage metrics before B-stage Wyckoff modules
- AND: Run B4 before B4.1
- THRESHOLD: Fixed script order
CONTEXT: Defines canonical daily orchestration path for production runbook.

### RULE PIPELINE_002
RULE_ID: PIPELINE_002  
SOURCE_FILE: scripts/cron/catchup_START_DATE_to_END_DATE.sh  
SOURCE_LINE: 13-23, 53-142  
CATEGORY: Strategy  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: Catch-up orchestration runs B4.1 before B4.
LOGIC:
- IF: Running catch-up script
- THEN: Execute B4.1 sequence generation before B4 derived aggregation
- THRESHOLD: Fixed script order
CONTEXT: Introduces order divergence versus daily run path.

### RULE PIPELINE_003
RULE_ID: PIPELINE_003  
SOURCE_FILE: scripts/cron/resume-from-A3.sh  
SOURCE_LINE: 6-44  
CATEGORY: Strategy  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: Resume-from-A3 path executes A3 first, then B2/B1, then B4 before B4.1.
LOGIC:
- IF: Resuming pipeline from A3
- THEN: Run A3 -> B2 -> B1 -> B4 -> B4.1
- THRESHOLD: Fixed script order
CONTEXT: Matches daily-run B4-before-B4.1 ordering, unlike catch-up script.

### RULE PIPELINE_004
RULE_ID: PIPELINE_004  
SOURCE_FILE: core/metrics/b2_wyckoff_structural_events_job.py  
SOURCE_LINE: 97-132, 135-177, 421-426  
CATEGORY: Strategy  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: B2 uses authoritative daily snapshot dates and requires complete per-date snapshot coverage before processing.
LOGIC:
- IF: Running B2
- THEN: Load target dates from `daily_snapshots` in NY time
- AND: Verify each target date has all requested ticker snapshots
- IF: Any date is incomplete
- THEN: Raise error and stop
- THRESHOLD: Full ticker coverage required per target date
CONTEXT: Prevents synthetic B2 rows when upstream snapshot state is incomplete.

### RULE PIPELINE_005
RULE_ID: PIPELINE_005  
SOURCE_FILE: core/metrics/b2_wyckoff_structural_events_job.py  
SOURCE_LINE: 180-182, 241-245  
CATEGORY: Strategy  
RULE_TYPE: Formula  
CONFIDENCE: STRONG  
DESCRIPTION: B2 OHLCV lookback start is extended by `required_bars * 3` days to absorb weekends/holidays.
LOGIC:
- IF: Computing OHLCV fetch window for B2
- THEN: `required_bars = max(min_bars_in_range, range_lookback, vol_lookback, lookback_trend)`
- AND: `lookback_start = start_date - required_bars*3 days`
- THRESHOLD: Multiplier `3`
CONTEXT: Reduces underfetch risk without trading-calendar dependency.

### RULE PIPELINE_006
RULE_ID: PIPELINE_006  
SOURCE_FILE: core/metrics/b2_wyckoff_structural_events_job.py  
SOURCE_LINE: 355-370, 448-457  
CATEGORY: Validation  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: B2 rejects OHLCV series with empty data, missing/null dates, duplicate dates, non-monotonic ordering, or gaps above limit.
LOGIC:
- IF: Any contiguity check fails
- THEN: Skip ticker and count data-quality error
- THRESHOLD: `MAX_GAP_DAYS = 4`
CONTEXT: Protects event detection from broken time series continuity.

### RULE PIPELINE_007
RULE_ID: PIPELINE_007  
SOURCE_FILE: core/metrics/b4_wyckoff_derived_job.py  
SOURCE_LINE: 539-540, 598-606  
CATEGORY: Strategy  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: Snapshot evidence writing in B4 is feature-gated.
LOGIC:
- IF: `include_evidence == True`
- THEN: Build and persist `wyckoff_snapshot_evidence`
- ELSE: Skip evidence row generation
- THRESHOLD: Boolean gate default false unless CLI flag provided
CONTEXT: Allows operational control over enriched downstream evidence payload.

### RULE PIPELINE_008
RULE_ID: PIPELINE_008  
SOURCE_FILE: core/metrics/b4_1_wyckoff_sequences_job.py  
SOURCE_LINE: 371-393, 484  
CATEGORY: Validation  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: B4.1 fails fast if required tables are missing.
LOGIC:
- IF: Any required table in `{daily_snapshots, wyckoff_regime_transitions, wyckoff_sequences, wyckoff_sequence_events}` is absent
- THEN: Raise runtime error before ticker loop
- THRESHOLD: All required tables must exist
CONTEXT: Prevents partial sequence writes against incomplete schema.

### RULE PIPELINE_009
RULE_ID: PIPELINE_009  
SOURCE_FILE: scripts/cron/kapman_daily_run.sh; scripts/cron/catchup_START_DATE_to_END_DATE.sh; scripts/cron/resume-from-A3.sh  
SOURCE_LINE: 159-175; 126-142; 29-44  
CATEGORY: Strategy  
RULE_TYPE: Classification  
CONFIDENCE: STRONG  
DESCRIPTION: B4/B4.1 ordering is inconsistent across scripts.
LOGIC:
- IF: Daily or resume script
- THEN: B4 runs before B4.1
- IF: Catch-up script
- THEN: B4.1 runs before B4
- THRESHOLD: N/A
CONTEXT: Operational inconsistency can change timing of derived vs canonical sequence availability.

## [KapMan] Anti-Patterns
- NEVER run B2 without upstream daily snapshot coverage checks.
- NEVER assume B4 and B4.1 order is uniform across all orchestration scripts.
- NEVER ignore OHLCV contiguity errors when running structural event detection.
- NEVER assume evidence rows are always present; they are gated by `include_evidence`.

## [KapMan] Source Mapping
- `scripts/cron/kapman_daily_run.sh`: 95-176
- `scripts/cron/catchup_START_DATE_to_END_DATE.sh`: 13-23, 53-142
- `scripts/cron/resume-from-A3.sh`: 6-44
- `core/metrics/b2_wyckoff_structural_events_job.py`: 97-132, 135-182, 241-245, 355-370, 421-457
- `core/metrics/b4_wyckoff_derived_job.py`: 539-540, 598-606
- `core/metrics/b4_1_wyckoff_sequences_job.py`: 371-393, 484

## [KapMan] Change Log
| Date | Version | Change |
|---|---|---|
| 2026-02-13 | 1.0 | Initial orchestration and dependency extraction. |
