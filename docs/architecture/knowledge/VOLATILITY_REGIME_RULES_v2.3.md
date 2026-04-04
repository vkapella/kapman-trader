---
system: KapMan
doc_type: metric
version: 2.3
last_validated: 2026-04-04
market_regime: all
confidence: strong
tags:
  - volatility
  - regime
  - iv
  - term_structure
---

# VOLATILITY_REGIME_RULES

## [KapMan] Objective
Capture all implemented volatility-regime calculations, thresholds, and processing-confidence classification logic.

## [KapMan] Decision Table
| Processing Inputs | Processing Status | Diagnostic |
|---|---|---|
| No options snapshot time or no contracts | `MISSING_OPTIONS` | `missing_options_data` |
| Contracts exist but `avg_iv` is null | `PARTIAL` | `missing_average_iv`, `partial_metrics` |
| Otherwise | `SUCCESS` | add `insufficient_iv_history` when history `<20` |

| Confidence Condition (`SUCCESS` only) | Confidence |
|---|---|
| `contracts_with_iv >= 40` AND `front_month_contracts >= 5` AND `back_month_contracts >= 5` | `high` |
| `contracts_with_iv >= 20` | `medium` |
| Else | `low` |

## [KapMan] Rule Catalog
### RULE VOLATILITY_001
RULE_ID: VOLATILITY_001  
SOURCE_FILE: core/metrics/volatility_metrics.py  
SOURCE_LINE: 7-11  
CATEGORY: Volatility  
RULE_TYPE: Threshold  
CONFIDENCE: STRICT  
DESCRIPTION: Default term-structure and history windows are fixed.
LOGIC:
- IF: No override provided
- THEN: Use `short_dte=30`, `long_dte=90`, `short_tolerance=15`, `long_tolerance=30`, `min_history_points=20`
- THRESHOLD: values above
CONTEXT: Defines baseline volatility-regime horizon.

### RULE VOLATILITY_002
RULE_ID: VOLATILITY_002  
SOURCE_FILE: core/metrics/volatility_metrics.py  
SOURCE_LINE: 27-38  
CATEGORY: Volatility  
RULE_TYPE: Formula  
CONFIDENCE: STRICT  
DESCRIPTION: Average IV is open-interest-weighted when possible, otherwise arithmetic mean.
LOGIC:
- IF: Contracts with IV exist and total open interest `>0`
- THEN: `avg_iv = sum(iv*open_interest)/sum(open_interest)`
- ELSE: `avg_iv = mean(iv)`
- THRESHOLD: OI gate `>0`
CONTEXT: Emphasizes liquid contracts in volatility state measurement.

### RULE VOLATILITY_003
RULE_ID: VOLATILITY_003  
SOURCE_FILE: core/metrics/volatility_metrics.py  
SOURCE_LINE: 41-47  
CATEGORY: Volatility  
RULE_TYPE: Formula  
CONFIDENCE: STRICT  
DESCRIPTION: Put/Call OI ratio is defined only when call OI is positive.
LOGIC:
- IF: `call_oi > 0`
- THEN: `put_call_oi_ratio = put_oi / call_oi`
- ELSE: return null
- THRESHOLD: denominator must be `>0`
CONTEXT: Prevents invalid division and misleading sentiment ratio.

### RULE VOLATILITY_004
RULE_ID: VOLATILITY_004  
SOURCE_FILE: core/metrics/volatility_metrics.py  
SOURCE_LINE: 53-59  
CATEGORY: Volatility  
RULE_TYPE: Formula  
CONFIDENCE: STRICT  
DESCRIPTION: Put/Call volume ratio is defined only when call volume is positive.
LOGIC:
- IF: `call_volume > 0`
- THEN: `put_call_volume_ratio = put_volume / call_volume`
- ELSE: return null
- THRESHOLD: denominator must be `>0`
CONTEXT: Avoids divide-by-zero artifacts in volume-pressure measures.

### RULE VOLATILITY_005
RULE_ID: VOLATILITY_005  
SOURCE_FILE: core/metrics/volatility_metrics.py  
SOURCE_LINE: 61-67  
CATEGORY: Volatility  
RULE_TYPE: Formula  
CONFIDENCE: STRICT  
DESCRIPTION: OI ratio uses total volume relative to total open interest.
LOGIC:
- IF: `total_open_interest > 0`
- THEN: `oi_ratio = total_volume / total_open_interest`
- ELSE: return null
- THRESHOLD: denominator must be `>0`
CONTEXT: Measures turnover against outstanding positioning.

### RULE VOLATILITY_006
RULE_ID: VOLATILITY_006  
SOURCE_FILE: core/metrics/volatility_metrics.py  
SOURCE_LINE: 69-74  
CATEGORY: Volatility  
RULE_TYPE: Formula  
CONFIDENCE: STRONG  
DESCRIPTION: IV dispersion uses population standard deviation.
LOGIC:
- IF: At least one IV value exists
- THEN: `iv_stddev = pstdev(iv_values)`
- ELSE: return null
- THRESHOLD: population `ddof=0`
CONTEXT: Gives stable cross-sectional IV spread statistic.

### RULE VOLATILITY_007
RULE_ID: VOLATILITY_007  
SOURCE_FILE: core/metrics/volatility_metrics.py  
SOURCE_LINE: 76-100  
CATEGORY: Volatility  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: 25-delta IV retrieval uses nearest-delta with tolerance, else strike-percentile fallback.
LOGIC:
- IF: Contracts with delta exist and nearest delta is within tolerance
- THEN: Use nearest-delta IV
- ELSE IF: At least 3 strikes exist
- THEN: For puts pick 25th-percentile strike IV; for calls pick 75th-percentile strike IV
- ELSE: Use median-by-strike IV
- THRESHOLD: delta tolerance `0.15`
CONTEXT: Preserves skew computation when Greeks are sparse.

### RULE VOLATILITY_008
RULE_ID: VOLATILITY_008  
SOURCE_FILE: core/metrics/volatility_metrics.py  
SOURCE_LINE: 103-109, 112-116  
CATEGORY: Volatility  
RULE_TYPE: Formula  
CONFIDENCE: STRICT  
DESCRIPTION: IV skew metrics are computed as put IV minus call IV, scaled to percentage points.
LOGIC:
- IF: Put IV and call IV are both available
- THEN: `iv_skew = (put_iv - call_iv) * 100`
- THRESHOLD: scale factor `100`
CONTEXT: Positive values indicate put premium skew.

### RULE VOLATILITY_009
RULE_ID: VOLATILITY_009  
SOURCE_FILE: core/metrics/volatility_metrics.py  
SOURCE_LINE: 119-137, 174-184  
CATEGORY: Volatility  
RULE_TYPE: Formula  
CONFIDENCE: STRONG  
DESCRIPTION: Term-structure level and slope are computed from front/back month IV anchors.
LOGIC:
- IF: front and back month IV anchors exist
- THEN: `iv_term_structure = (long_iv - short_iv) * 100`
- AND: `iv_term_structure_slope = ((back-front)*100)/(long_dte-short_dte)`
- THRESHOLD: front target `30±15 DTE`, back target `90±30 DTE`
CONTEXT: Encodes contango/backwardation and gradient.

### RULE VOLATILITY_010
RULE_ID: VOLATILITY_010  
SOURCE_FILE: core/metrics/volatility_metrics.py  
SOURCE_LINE: 187-201  
CATEGORY: Volatility  
RULE_TYPE: Formula  
CONFIDENCE: STRICT  
DESCRIPTION: IV percentile is rank fraction of historical values less than or equal to current IV.
LOGIC:
- IF: `current_average_iv` exists and history length `>= min_history_points`
- THEN: `iv_percentile = (count(history <= current)/len(history))*100`
- AND: Clamp to `[0,100]`
- THRESHOLD: `min_history_points = 20`
CONTEXT: Provides regime-relative IV placement.

### RULE VOLATILITY_011
RULE_ID: VOLATILITY_011  
SOURCE_FILE: core/metrics/volatility_metrics.py  
SOURCE_LINE: 204-221  
CATEGORY: Volatility  
RULE_TYPE: Formula  
CONFIDENCE: STRICT  
DESCRIPTION: IV rank normalizes current IV between historical min and max.
LOGIC:
- IF: `current_average_iv` exists and history length `>= min_history_points`
- AND: `iv_max != iv_min`
- THEN: `iv_rank = (current-iv_min)/(iv_max-iv_min)*100`
- AND: Clamp to `[0,100]`
- THRESHOLD: `min_history_points = 20`
CONTEXT: Standardized IV regime gauge for cross-date comparison.

### RULE VOLATILITY_012
RULE_ID: VOLATILITY_012  
SOURCE_FILE: core/metrics/a4_volatility_metrics_job.py  
SOURCE_LINE: 277-299  
CATEGORY: Volatility  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: A4 processing status is determined from options availability and avg IV completeness.
LOGIC:
- IF: `options_snapshot_time is None` OR no contracts
- THEN: `MISSING_OPTIONS`
- IF: `metrics.avg_iv is None`
- THEN: `PARTIAL`
- ELSE: `SUCCESS`
- AND: add `insufficient_iv_history` diagnostic when history points `<20`
- THRESHOLD: history floor `20`
CONTEXT: Separates data-availability failures from partial-calculation outcomes.

### RULE VOLATILITY_013
RULE_ID: VOLATILITY_013  
SOURCE_FILE: core/metrics/a4_volatility_metrics_job.py  
SOURCE_LINE: 301-315  
CATEGORY: Volatility  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: A4 confidence levels are tiered by chain depth and tenor coverage.
LOGIC:
- IF: processing status is not `SUCCESS`
- THEN: confidence `low`
- IF: `contracts_with_iv >= 40` AND `front_month_contracts >= 5` AND `back_month_contracts >= 5`
- THEN: confidence `high`
- ELSE IF: `contracts_with_iv >= 20`
- THEN: confidence `medium`
- ELSE: confidence `low`
- THRESHOLD: cutoffs `40/20`, tenor minimums `5/5`
CONTEXT: Uses both quantity and term-structure completeness as confidence proxy.

### RULE VOLATILITY_014
RULE_ID: VOLATILITY_014  
SOURCE_FILE: core/metrics/a4_volatility_metrics_job.py  
SOURCE_LINE: 24  
CATEGORY: Volatility  
RULE_TYPE: Threshold  
CONFIDENCE: STRONG  
DESCRIPTION: IV history fetch window is capped to a fixed lookback.
LOGIC:
- IF: Loading prior average IV history
- THEN: Query up to `lookback` rows
- THRESHOLD: `DEFAULT_HISTORY_LOOKBACK = 252`
CONTEXT: Anchors percentile/rank calculations to approximately one trading year.

### RULE VOLATILITY_015
RULE_ID: VOLATILITY_015
CATEGORY: Volatility
RULE_TYPE: Constraint
CONFIDENCE: STRICT
DESCRIPTION: IV source authority is tiered by pass and use case.
LOGIC:
- IF: Computing IV for Pass 1 screening (directional classification only)
- THEN: Use Polygon avg_iv from get_options_metrics(symbol, include=['volatility'])
         for single-symbol OR get_batch_options_metrics(symbols=[], include=['volatility'])
         for multi-symbol Pass 1 screening (batch max 30 symbols per call)
- AND: Accept residual +1–4pp positive bias vs ATM IV as structurally expected
- IF: Computing IV/HV ratio for SIGNAL_008 spread decision (Pass 2)
- THEN: Use Schwab ATM chain per-contract "volatility" field at nearest-to-money strike
- NEVER: Use Schwab "theoreticalVolatility" field — hardcoded 29.0, not market IV
- NEVER: Use Polygon avg_iv as sole basis for SIGNAL_008 iv_forbids_long_premium trigger
CONTEXT: Validated 2026-03-27 via controlled 6-ticker audit. Post-fix Polygon
avg_iv multiplier = 1.02-1.07x vs Schwab ATM. Fix applied to main.py lines
879-891 and 1160-1197 (DTE>=7, iv<=2.0, moneyness<=20% filters).
Tool surface updated 2026-03-28: get_volatility_metrics deprecated.
Canonical replacement is get_options_metrics(include=['volatility']) for single-symbol
and get_batch_options_metrics(include=['volatility']) for multi-symbol Pass 1 screening.
Batch endpoint validated 30/30 symbols, 0 errors, no silent truncation (2026-03-28).

## [KapMan] Anti-Patterns
- NEVER treat missing options data as neutral success; status must be `MISSING_OPTIONS`.
- NEVER compute IV percentile/rank with fewer than 20 history points.
- NEVER assume high confidence without both depth and front/back tenor coverage.
- NEVER infer skew from unavailable put/call IV anchors.

## [KapMan] Source Mapping
- `core/metrics/volatility_metrics.py`: 7-11, 27-38, 41-74, 76-116, 119-137, 174-221
- `core/metrics/a4_volatility_metrics_job.py`: 24, 277-315

## [KapMan] Change Log
| Date | Version | Change |
|---|---|---|
| 2026-02-13 | 1.0 | Initial extraction of volatility formulas and status/confidence thresholds. |
| 2026-03-27 | 2.1 | Added IV source authority rules (Polygon avg_iv for Pass 1, Schwab ATM for Pass 2). |
| 2026-03-28 | 2.2 | Updated RULE VOLATILITY_015: replaced deprecated get_volatility_metrics with canonical get_options_metrics / get_batch_options_metrics(include=['volatility']). Batch validated 30-symbol audit 30/30, 0 errors. |



| 2026-04-04 | 2.3 | Standardized to v2.3 production baseline. No content changes. |
