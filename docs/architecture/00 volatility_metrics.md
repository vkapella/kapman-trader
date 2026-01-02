# Volatility Metrics (volatility_metrics_json)

## Overview
KapMan computes option-chain-derived volatility metrics from a set of option contracts plus an IV history series. The outputs are intended for downstream dashboards and decision context. Every metric key exists; values are `null` when inputs are missing or insufficient.

The calculation surface is implemented in `core/metrics/volatility_metrics.py`.

## Inputs

### Contract model
Each contract is treated as an `OptionContractVol` with:
- `contract_type` (`"call"` or `"put"`)
- `iv` (implied volatility as a decimal, e.g. `0.42` for 42% IV)
- `delta` (optional; decimal delta, calls positive, puts negative)
- `dte` (optional; days-to-expiration, integer)
- `volume` (integer)
- `open_interest` (integer)
- `strike` (float; used only for a fallback skew heuristic)

### History series
`history` is a sequence of past average IV values (each a float decimal or `null`), used for `iv_percentile` and `iv_rank`.

### Defaults
- `short_dte`: 30 (front-month target)
- `long_dte`: 90 (back-month target)
- `short_tolerance`: ±15 DTE
- `long_tolerance`: ±30 DTE
- `min_history_points`: 20

## Metrics dictionary (volatility_metrics_json)

### Average implied volatility
- `avg_iv` / `average_iv` (float | null)
  - Definition: average implied volatility across all contracts with `iv != null`.
  - Default behavior: **open-interest weighted** when total OI > 0.
  - Formulas:
    - Weighted: `sum(iv_i * oi_i) / sum(oi_i)`
    - Fallback (if total OI == 0): `mean(iv_i)`
  - Rounding: 4 decimals.

- `avg_call_iv` (float | null)
  - Definition: average IV for call contracts only, using the same weighting rules as `avg_iv`.
  - Rounding: 4 decimals.

- `avg_put_iv` (float | null)
  - Definition: average IV for put contracts only, using the same weighting rules as `avg_iv`.
  - Rounding: 4 decimals.

### Cross-sectional IV dispersion
- `iv_stddev` (float | null)
  - Definition: population standard deviation (`pstdev`) of contract IVs for contracts where `iv != null`.
  - Rounding: 4 decimals.

### Skew
- `iv_skew_call_put` (float | null)
  - Definition: call/put skew computed from average IVs:
    - `(avg_put_iv - avg_call_iv) * 100`
  - Units: IV points (percentage points, not a ratio).
  - Rounding: 2 decimals.

- `iv_skew` (float | null)
  - Definition: “25-delta style” skew:
    - `(put_25delta_iv - call_25delta_iv) * 100`
  - `put_25delta_iv` / `call_25delta_iv` selection:
    1. If deltas exist for the type, pick the contract whose `delta` is closest to:
       - calls: `+0.25`
       - puts: `-0.25`
       and accept it only if within `±0.15` of the target delta.
    2. Otherwise, fall back to strike-based sampling:
       - sort that type by `strike`
       - if 3+ contracts:
         - puts: choose ~25th percentile index
         - calls: choose ~75th percentile index
       - else: choose the middle contract
  - Units: IV points.
  - Rounding: 2 decimals.

### Put/Call ratios
- `put_call_oi_ratio` (float | null)
  - Definition: `total_put_open_interest / total_call_open_interest`.
  - Null when total call OI is 0.
  - Rounding: 4 decimals.

- `put_call_volume_ratio` (float | null)
  - Definition: `total_put_volume / total_call_volume`.
  - Null when total call volume is 0.
  - Rounding: 4 decimals.

### OI “turnover” ratio
- `oi_ratio` (float | null)
  - Definition: `total_volume / total_open_interest`.
  - Null when total open interest is 0.
  - Rounding: 4 decimals.

### Term structure
- `front_month_iv` (float | null)
  - Definition: average IV for contracts with `abs(dte - short_dte) <= short_tolerance` and `dte >= 0`.
  - Uses a simple mean over matching contracts’ `iv` values.
  - Rounding: 4 decimals.

- `back_month_iv` (float | null)
  - Definition: average IV for contracts with `abs(dte - long_dte) <= long_tolerance` and `dte >= 0`.
  - Uses a simple mean over matching contracts’ `iv` values.
  - Rounding: 4 decimals.

- `iv_term_structure` (float | null)
  - Definition: `(long_iv - short_iv) * 100`, where:
    - `short_iv` is the mean IV near `short_dte` (± short tolerance)
    - `long_iv` is the mean IV near `long_dte` (± long tolerance)
  - Null if either side has no matches.
  - Units: IV points.
  - Rounding: 2 decimals.

- `iv_term_structure_slope` (float | null)
  - Definition: slope per day between front/back month:
    - `((back_month_iv - front_month_iv) * 100) / (long_dte - short_dte)`
  - Null if either IV is null or `long_dte == short_dte`.
  - Units: IV points per day.
  - Rounding: 2 decimals.

### IV percentile/rank (historical context)
- `iv_percentile` (float | null)
  - Definition: percentage of history values `<= current_average_iv`:
    - `count(history_i <= current_avg_iv) / len(history) * 100`
  - Null if:
    - `current_average_iv` is null, or
    - fewer than `min_history_points` non-null history values exist
  - Clamped to `[0, 100]`.
  - Rounding: 2 decimals.

- `iv_rank` (float | null)
  - Definition: IV rank over history range:
    - `(current_avg_iv - min(history)) / (max(history) - min(history)) * 100`
  - Null if:
    - `current_average_iv` is null, or
    - fewer than `min_history_points` non-null history values exist, or
    - `max(history) == min(history)`
  - Clamped to `[0, 100]`.
  - Rounding: 2 decimals.

## Counts payload (diagnostics / completeness)
The computation also produces `VolatilityMetricsCounts`, which summarizes the input coverage (useful for debugging and gating):
- `total_contracts`
- `contracts_with_iv`
- `call_contracts`
- `call_contracts_with_iv`
- `put_contracts`
- `put_contracts_with_iv`
- `front_month_contracts` (contracts with `dte` within front-month tolerance and `dte >= 0`)
- `back_month_contracts` (contracts with `dte` within back-month tolerance and `dte >= 0`)
- `total_volume`
- `total_open_interest`

## Null / absence rules
- Any metric returns `null` when required inputs are missing or insufficient (e.g., no contracts with IV, no DTE matches, too-short history).
- Put/call ratios return `null` when their denominator is 0.
- Percentile/rank require at least `min_history_points` non-null history values.

## Output key stability
The canonical set of keys is defined by `VOLATILITY_METRIC_KEYS` in `core/metrics/volatility_metrics.py` and is intended to remain stable across runs; values may be `null` but keys should not disappear.
