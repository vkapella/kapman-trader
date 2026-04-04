---
system: KapMan
doc_type: strategy
version: 2.3
last_validated: 2026-04-04
market_regime: all
confidence: strong
tags:
  - constants
  - config
  - defaults
  - thresholds
---

# CONSTANTS_AND_CONFIG

## [KapMan] Objective
Inventory the hardcoded constants, default thresholds, and config toggles that materially influence KapMan trading logic behavior.

## [KapMan] Decision Table
| Subsystem | Constant Set | Default Values |
|---|---|---|
| Structural Wyckoff | Windows | trend 20, volume 40, range 40, min range bars 20 |
| Structural Wyckoff | Event thresholds | SC/BC `tr_z=2.0`, SC/BC `vol_z=2.0`, SOS/SOW `tr_z=1.5`, SPRING `vol_z=0.8` |
| Structural Wyckoff | Geometry | break pct `0.01`, reentry bars `2`, close-pos SPRING `0.6`, UT `0.4` |
| Dealer | Chain filters | max DTE 90, min OI 100, min volume 1 |
| Dealer | Wall/slope params | top walls 3, slope range 0.02, max moneyness 0.2 |
| Volatility | Term anchors | short DTE 30±15, long DTE 90±30 |
| Volatility | History thresholds | min points 20, lookback 252 |
| C4 | Batch/retry | batch 5, wait 1s, retries 3, backoff base 1s |
| DB schema | Score bounds | BC Score 0..28, Spring Score 0..12 |

## [KapMan] Rule Catalog
### RULE CONSTANTS_001
RULE_ID: CONSTANTS_001  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 23-26  
CATEGORY: Constants  
RULE_TYPE: Threshold  
CONFIDENCE: STRICT  
DESCRIPTION: Structural event model windows are fixed by default config.
LOGIC:
- IF: No config override supplied
- THEN: use `lookback_trend=20`, `vol_lookback=40`, `range_lookback=40`, `min_bars_in_range=20`
- THRESHOLD: values above
CONTEXT: Sets temporal sensitivity for event detection and phase construction.

### RULE CONSTANTS_002
RULE_ID: CONSTANTS_002  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 29-35  
CATEGORY: Constants  
RULE_TYPE: Threshold  
CONFIDENCE: STRICT  
DESCRIPTION: Core structural z-score thresholds are hardcoded in default config.
LOGIC:
- IF: Detecting Selling Climax (SC), Buying Climax (BC), Sign of Strength (SOS), Sign of Weakness (SOW), SPRING
- THEN: apply default z-score thresholds from config
- THRESHOLD: `sc_tr_z=2.0`, `sc_vol_z=2.0`, `bc_tr_z=2.0`, `bc_vol_z=2.0`, `sow_tr_z=1.5`, `sos_tr_z=1.5`, `spring_vol_z=0.8`
CONTEXT: Defines event sensitivity baseline.

### RULE CONSTANTS_003
RULE_ID: CONSTANTS_003  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 42-47  
CATEGORY: Constants  
RULE_TYPE: Threshold  
CONFIDENCE: STRICT  
DESCRIPTION: SPRING and Upthrust (UT) geometry defaults are fixed.
LOGIC:
- IF: Evaluating SPRING/UT geometry
- THEN: use default break/reentry/close-position constants
- THRESHOLD: `spring_break_pct=0.01`, `spring_reentry_bars=2`, `spring_close_pos=0.6`, `ut_break_pct=0.01`, `ut_reentry_bars=2`, `ut_close_pos=0.4`
CONTEXT: Controls false-break detection strictness.

### RULE CONSTANTS_004
RULE_ID: CONSTANTS_004  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 54-58  
CATEGORY: Constants  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: Phase-construction behavior is controlled by boolean defaults and minimum phase length.
LOGIC:
- IF: Trend gating enabled
- THEN: Selling Climax (SC)/Buying Climax (BC) require prior trend
- IF: Soft markdown disabled
- THEN: Markdown requires Sign of Weakness (SOW)
- IF: Extend-first/extend-last enabled
- THEN: phases are stretched to chart edges
- THRESHOLD: `require_prior_trend_for_sc_bc=True`, `allow_soft_markdown_without_sow=False`, `extend_first_phase_to_start=True`, `extend_last_phase_to_end=True`, `min_phase_bars=2`
CONTEXT: Governs phase continuity and strictness assumptions.

### RULE CONSTANTS_005
RULE_ID: CONSTANTS_005  
SOURCE_FILE: core/metrics/b2_wyckoff_structural_events_job.py  
SOURCE_LINE: 21-23  
CATEGORY: Constants  
RULE_TYPE: Threshold  
CONFIDENCE: STRICT  
DESCRIPTION: B2 pipeline quality/runtime defaults are fixed.
LOGIC:
- IF: Running B2 with defaults
- THEN: heartbeat every 50 tickers, unknown prior regime label, max OHLCV date gap 4
- THRESHOLD: `DEFAULT_HEARTBEAT_TICKERS=50`, `REGIME_UNKNOWN="UNKNOWN"`, `MAX_GAP_DAYS=4`
CONTEXT: Controls operational telemetry and contiguity guardrails.

### RULE CONSTANTS_006
RULE_ID: CONSTANTS_006  
SOURCE_FILE: core/metrics/b4_wyckoff_derived_job.py  
SOURCE_LINE: 41-47, 49-50  
CATEGORY: Constants  
RULE_TYPE: Threshold  
CONFIDENCE: STRICT  
DESCRIPTION: B4 sequence windows and pattern IDs are hardcoded.
LOGIC:
- IF: Deriving sequences
- THEN: enforce fixed sequence patterns and max sequence duration
- THRESHOLD: `SEQUENCE_MAX_DAYS=30`; patterns for `SEQ_ACCUM_BREAKOUT`, `SEQ_DISTRIBUTION_TOP`, `SEQ_MARKDOWN_START`, `SEQ_RECOVERY`, and `SEQ_FAILED_ACCUM`
CONTEXT: Stabilizes canonical sequence detection behavior.

### RULE CONSTANTS_007
RULE_ID: CONSTANTS_007  
SOURCE_FILE: core/metrics/b4_1_wyckoff_sequences_job.py  
SOURCE_LINE: 25-49  
CATEGORY: Constants  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: B4.1 terminal/supporting/eligible/invalidating regime sets are static.
LOGIC:
- IF: Terminal event is SOS or SOW
- THEN: use fixed supporting event list, eligible prior regimes, invalidating regimes, and sequence type IDs
- THRESHOLD: static mapping tables in source
CONTEXT: Prevents drift in canonical sequence semantics.

### RULE CONSTANTS_008
RULE_ID: CONSTANTS_008  
SOURCE_FILE: core/metrics/dealer_metrics_job.py  
SOURCE_LINE: 26-29, 562-567  
CATEGORY: Constants  
RULE_TYPE: Threshold  
CONFIDENCE: STRICT  
DESCRIPTION: Dealer runtime filter and model defaults are hardcoded.
LOGIC:
- IF: Running A3 without CLI overrides
- THEN: use `max_dte_days=90`, `min_open_interest=100`, `min_volume=1`, `walls_top_n=3`, `gex_slope_range_pct=0.02`, `max_moneyness=0.2`
- THRESHOLD: values above
CONTEXT: Determines chain eligibility and model sensitivity.

### RULE CONSTANTS_009
RULE_ID: CONSTANTS_009  
SOURCE_FILE: core/metrics/dealer_metrics_calc.py  
SOURCE_LINE: 12-14  
CATEGORY: Constants  
RULE_TYPE: Threshold  
CONFIDENCE: STRONG  
DESCRIPTION: Dealer computation wrapper mirrors authoritative defaults.
LOGIC:
- IF: calculate_metrics called without overrides
- THEN: use `DEFAULT_WALLS_TOP_N=3`, `DEFAULT_GEX_SLOPE_RANGE_PCT=0.02`, `DEFAULT_MAX_MONEYNESS=0.2`
- THRESHOLD: values above
CONTEXT: Keeps wrapper behavior aligned with authoritative dealer module.

### RULE CONSTANTS_010
RULE_ID: CONSTANTS_010  
SOURCE_FILE: core/metrics/volatility_metrics.py; core/metrics/a4_volatility_metrics_job.py  
SOURCE_LINE: 7-11; 24  
CATEGORY: Constants  
RULE_TYPE: Threshold  
CONFIDENCE: STRICT  
DESCRIPTION: Volatility calculations and history scope are controlled by fixed defaults.
LOGIC:
- IF: No override provided
- THEN: `short_dte=30`, `long_dte=90`, `short_tolerance=15`, `long_tolerance=30`, `min_history_points=20`, `history_lookback=252`
- THRESHOLD: values above
CONTEXT: Defines volatility regime anchoring and historical context depth.

### RULE CONSTANTS_011
RULE_ID: CONSTANTS_011  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 31-34  
CATEGORY: Constants  
RULE_TYPE: Threshold  
CONFIDENCE: STRICT  
DESCRIPTION: C4 throughput and retry timing are configured by fixed defaults.
LOGIC:
- IF: Running C4 with defaults
- THEN: use batch size 5, batch wait 1.0s, max retries 3, backoff base 1.0s
- THRESHOLD: `DEFAULT_BATCH_SIZE=5`, `DEFAULT_BATCH_WAIT_SECONDS=1.0`, `DEFAULT_MAX_RETRIES=3`, `DEFAULT_BACKOFF_BASE_SECONDS=1.0`
CONTEXT: Controls API rate pressure and retry cadence.

### RULE CONSTANTS_012
RULE_ID: CONSTANTS_012  
SOURCE_FILE: db/migrations/0001_schema_baseline_2026_01.sql  
SOURCE_LINE: 39, 47, 55, 147-148, 173  
CATEGORY: Constants  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: Core recommendation/scoring bounds and enums are fixed at schema layer.
LOGIC:
- IF: Persisting recommendation direction/action/strategy
- THEN: values must match enum sets
- IF: Persisting BC Score or Spring Score
- THEN: enforce range checks (`0..28`, `0..12`)
- IF: Persisting recommendation confidence
- THEN: enforce `0..1`
- THRESHOLD: enum/check definitions in schema
CONTEXT: Final layer of hard validation for downstream consumers.

### RULE CONSTANTS_013
RULE_ID: CONSTANTS_013  
SOURCE_FILE: core/metrics/structural.py; core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 49-51; 36-39  
CATEGORY: Constants  
RULE_TYPE: Classification  
CONFIDENCE: STRONG  
DESCRIPTION: Some configured constants are currently dormant in active logic paths.
LOGIC:
- IF: Looking for Secondary Test (ST) detector constants
- THEN: `max_st_deviation_pct` and `test_low_vol_factor` are defined but unused
- IF: Looking for C4 option context constants
- THEN: `DEFAULT_MIN_OPEN_INTEREST`, `DEFAULT_MIN_VOLUME`, expiration/moneyness defaults are defined but not injected into runtime payload
- THRESHOLD: N/A
CONTEXT: Distinguishes active defaults from placeholders.

## [KapMan] Anti-Patterns
- NEVER treat dormant constants as active runtime behavior.
- NEVER change defaults without tracing dependent rule logic and schema bounds.
- NEVER assume schema precision implies full scoring formula implementation.
- NEVER override orchestration thresholds without verifying downstream event sensitivity.

## [KapMan] Source Mapping
- `core/metrics/structural.py`: 23-58
- `core/metrics/b2_wyckoff_structural_events_job.py`: 21-23
- `core/metrics/b4_wyckoff_derived_job.py`: 41-50
- `core/metrics/b4_1_wyckoff_sequences_job.py`: 25-49
- `core/metrics/dealer_metrics_job.py`: 26-29, 562-567
- `core/metrics/dealer_metrics_calc.py`: 12-14
- `core/metrics/volatility_metrics.py`: 7-11
- `core/metrics/a4_volatility_metrics_job.py`: 24
- `core/metrics/c4_batch_ai_screening_job.py`: 31-39
- `db/migrations/0001_schema_baseline_2026_01.sql`: 39, 47, 55, 147-148, 173

## [KapMan] Change Log
| Date | Version | Change |
|---|---|---|
| 2026-02-13 | 1.0 | Initial constant/default inventory extraction. |
| 2026-04-04 | 2.3 | Standardized to v2.3 production baseline. No content changes. |
