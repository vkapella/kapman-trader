# Dealer Metrics Status Taxonomy

KapMan A3 emits a deterministic status for each ticker in `dealer_metrics_json.status`. This classification is numeric and auditable; dealer math and filters are unchanged.

- **FULL**  
  - Conditions (all): `eligible_options >= 25`, `gex_total` and `gex_net` are not null, `abs(gex_total) > 0`, `position != "unknown"`, and `confidence` is `high` or `medium`.  
  - Usage: Actionable dealer signal; suitable for Wyckoff overlays, dashboards, scoring, and regime analysis.

- **LIMITED**  
  - Conditions (all): `eligible_options >= 1`, `gex_total` and `gex_net` are not null, `abs(gex_total) > 0`, `position` in (`long_gamma`, `short_gamma`, `neutral`), and `confidence` is `medium` or `invalid`.  
  - Usage: Valid but thin/fragile signal; display with reduced weight, avoid using as primary driver for ranking or Wyckoff decisions.

- **INVALID**  
  - Conditions (any): `eligible_options == 0`, `gex_total` is null, `gex_net` is null, spot missing or spot resolution failed, diagnostics include `all_contracts_filtered` or `no_options_available`.  
  - Usage: Insufficient signal; exclude from scoring, ranking, and strategy logic.

Supporting context is stored in `dealer_metrics_json.metadata`, including `eligible_options`, `total_options`, `confidence`, and `status_reason` for downstream auditing.
# Dealer Metrics Status Taxonomy and JSON Schema

## Overview
KapMan A3 produces dealer positioning metrics per ticker into `daily_snapshots.dealer_metrics_json` whenever options snapshots, spot resolution, and guardrails succeed. Results describe dealer gamma exposure, positioning, and wall structure for the resolved snapshot time. Runs occur on watchlist tickers at the most recent options snapshot time (or provided `--snapshot-time`), using deterministic option/spot selection rules.

## Dealer Metrics JSON Schema
- `status` (string: `FULL` | `LIMITED` | `INVALID`): Quality classification derived from the computed metrics and eligibility counts.
- `failure_reason` (string | null): Failure code when computation could not be completed; null on successful computation.
- `spot_price` (float | null): Resolved underlying spot price (override, price_metrics, or OHLCV fallback).
- `spot_price_source` (string | null): Provenance of `spot_price` (`override`, `price_metrics.<key>`, or `ohlcv`).
- `eligible_options_count` (int): Count of option contracts that passed all filters.
- `total_options_count` (int): Count of option contracts ingested for the ticker at the effective options time.
- `gex_total` (float | null): Sum of absolute gamma exposure across strikes (rounded to 2 decimals).
- `gex_net` (float | null): Net gamma exposure across strikes (rounded to 2 decimals).
- `gamma_flip` (float | null): Strike level where cumulative GEX crosses zero (None if no crossing).
- `call_walls` (list of objects): Top-N call walls; each `{ "strike": float, "open_interest": int, "volume": int }`.
- `put_walls` (list of objects): Top-N put walls; each `{ "strike": float, "open_interest": int, "volume": int }`.
- `gex_slope` (float | null): GEX slope around spot using configured range_pct; null if insufficient data.
- `dgpi` (float | null): Dealer Gamma Pressure Index derived from gex_net and gex_slope.
- `position` (string): Dealer positioning label (`long_gamma`, `short_gamma`, `neutral`, `unknown`).
- `confidence` (string): Confidence bucket from dealer calc (`high`, `medium`, `low`, `invalid`).
- `metadata` (object):
  - `snapshot_time` (ISO datetime): Snapshot timestamp used for resolution/logging.
  - `snapshot_date` (ISO date): Date portion of `snapshot_time`.
  - `ticker_id` (string): Internal ticker identifier.
  - `symbol` (string): Uppercase ticker symbol.
  - `processing_status` (string): A3 processing outcome (`SUCCESS`, `FAIL_*`, or `COMPUTATION_ERROR`).
  - `spot` (float | null): Echo of `spot_price`.
  - `spot_source` (string | null): Echo of `spot_price_source`.
  - `spot_resolution_strategy` (string | null): Strategy used (`override`, `price_metrics`, `ohlcv_fallback`).
  - `effective_options_time` (ISO datetime | null): Resolved options snapshot time (max `options_chains.time <= snapshot_time`).
  - `options_time_resolution_strategy` (string | null): Currently `max_leq_snapshot`.
  - `effective_trading_date` (ISO date | null): Trading date aligned to OHLCV for spot/filters.
  - `spot_attempted_sources` (list[string]): Ordered spot sources attempted.
  - `eligible_options` (int): Echo of eligible option count.
  - `total_options` (int): Echo of total option count.
  - `confidence` (string): Echo of top-level confidence.
  - `status_reason` (string): Reason code for the quality `status`.
  - `filters` (object): Parameterization used:
    - `max_dte_days` (int)
    - `min_open_interest` (int)
    - `min_volume` (int)
    - `max_spread_pct` (float)
    - `walls_top_n` (int)
    - `gex_slope_range_pct` (float)
  - `filter_stats` (object): Counts of filtered contracts:
    - `total`, `expired`, `dte_exceeded`, `missing_gamma`, `low_open_interest`, `low_volume`, `wide_spread`, `other`
  - `contracts_total` (int): Alias of `filter_stats.total`.
  - `contracts_used` (int): Number of option contracts that fed dealer math.
  - `diagnostics` (list[string]): Guardrail and failure annotations (e.g., `missing_spot_price`, `no_eligible_options`, `all_contracts_filtered`, `spot_resolution_failed`, `no_options_before_snapshot`).

Null / missing values reflect upstream data insufficiency, guardrail blocks, or ineligible contract sets; they are persisted as `null` rather than omitted.

## Status & Confidence Semantics
- `status` is derived post-computation:
  - **FULL**: `eligible_options >= 25`, `gex_total` and `gex_net` present and non-zero magnitude, `position != "unknown"`, `confidence` in (`high`, `medium`).
  - **LIMITED**: `eligible_options >= 1`, `gex_total` and `gex_net` present and non-zero magnitude, `position` in (`long_gamma`, `short_gamma`, `neutral`), `confidence` in (`medium`, `invalid`).
  - **INVALID**: Any of `eligible_options == 0`, missing `gex_total` or `gex_net`, spot missing/failed, diagnostics containing `all_contracts_filtered` or `no_options_available`, or other unmet criteria.
- `confidence` comes directly from dealer math and is not altered by the taxonomy; combine with `status` to decide downstream usability.
- `diagnostics` and `filter_stats` explain why contracts were rejected or why metrics are absent; `no_eligible_options` indicates filters removed all contracts despite options being present.

## Determinism & Provenance
- `snapshot_time`: Options heartbeat time driving the run (or user-provided).
- `effective_options_time`: Per-ticker resolved options snapshot (max `options_chains.time <= snapshot_time`); prevents empty results when ingestion is intraday.
- `effective_trading_date`: OHLCV-aligned trading date (latest market close on/before snapshot); anchors DTE and spot fallback.
- `spot_source` / `spot_resolution_strategy` / `spot_attempted_sources`: Track how spot was resolved to avoid silent fallbacks and to audit failures.
