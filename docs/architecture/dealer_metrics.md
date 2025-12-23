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
    - `walls_top_n` (int)
    - `gex_slope_range_pct` (float)
  - `filter_stats` (object): Counts of filtered contracts:
    - `total`, `expired`, `dte_exceeded`, `missing_gamma`, `low_open_interest`, `low_volume`, `other`
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

**Wall Filte Assumption**
Below is a sanity-check of ±20% moneyness as the default wall-filter in the context of Wyckoff analysis + dealer gamma mechanics, followed by a clear recommendation.

⸻

Executive Answer

Yes — ±20% is a defensible and reasonable default, but it should be treated as a configurable ceiling, not a universal truth.

For your current use case (daily / swing Wyckoff with dealer metrics as context, not scalping signals):
	•	±20% = correct default
	•	±15% = often “cleaner” for high-liquidity megacaps
	•	±25–30% = sometimes required for high-volatility / small-cap names

Your instinct to make this CLI-tunable is exactly right.

⸻

Why ±20% Works for Wyckoff Time Horizons

1. Wyckoff Is About Structure, Not Microstructure

Wyckoff phases (A–E) operate over:
	•	Days → weeks → months
	•	Not intraday pinning or expiry-day effects

Dealer walls that matter for Wyckoff must:
	•	Influence multi-day hedging behavior
	•	Be within realistic price travel distance

A ±20% band captures:
	•	Likely support / resistance zones
	•	Without polluting the signal with far-OTM “inventory noise”

⸻

2. Dealer Hedging Reality (Key Point)

Dealers dynamically hedge gamma near spot, not far OTM.

As moneyness increases:
	•	Gamma collapses rapidly
	•	Hedging urgency drops
	•	Deep OTM GEX becomes latent, not active

Empirically:
	•	20% OTM strikes rarely influence next 1–3 weeks of price action
	•	They can matter in crashes or squeezes, but not as day-to-day walls

So ±20% acts as a gamma-relevance boundary, not an arbitrary cutoff.

⸻

3. Cross-Ticker Practicality

Ticker Type	Typical Daily Move	±20% Horizon Represents
AAPL / MSFT	1–3%	~6–10 weeks
NVDA	3–6%	~3–6 weeks
PLTR / SOUN	5–10%	~1–3 weeks
Small caps	8–15%	~days–weeks

This lines up well with:
	•	Your A3 snapshot cadence
	•	Dealer metrics being recomputed daily
	•	Wyckoff phase transitions being observed over weeks

⸻

When ±20% Is Too Wide or Too Narrow

Too Wide When:
	•	Mega-caps with tight volatility (AAPL, MSFT)
	•	You see far-OTM strikes repeatedly dominating walls
	•	Walls appear “far away” and untradeable

Solution: tighten to ±15%

⸻

Too Narrow When:
	•	High-beta / speculative names
	•	Event-driven volatility
	•	You see no walls at all after filtering

Solution: widen to ±25% or ±30%

⸻

Recommended Default Strategy (Strongly Suggested)

1. Keep ±20% as the Default

It is:
	•	Conservative
	•	Explainable
	•	Matches institutional behavior
	•	Safe for most symbols

2. Make It Explicit and Visible

This is important for trust and debuggability.

Example metadata already fits your design well:

"wall_config": {
  "max_moneyness_pct": 0.20,
  "walls_top_n": 5,
  "max_dte_days": 45,
  "min_open_interest": 100
}

3. Add CLI Override (You Already Identified This Correctly)

Example:

python -m scripts.run_a3_dealer_metrics \
  --snapshot-time 2025-12-22T23:59:59+00:00 \
  --wall-max-moneyness 0.15

This enables:
	•	Per-experiment tuning
	•	Backtesting sensitivity
	•	Future automation (symbol-specific defaults)

⸻

Important: Do NOT Over-Optimize Early

Claude’s suggestions are directionally correct, but order matters.

Correct implementation order for A3.1:
	1.	✅ Moneyness filter (±20%) ← MUST
	2.	✅ Persist walls + primaries
	3.	✅ Determinism + tests
	4.	➕ Proximity weighting (later)
	5.	➕ Density normalization (only if needed)
	6.	➕ Time-decay weighting (optional)

You are right to start simple and structural.

⸻

Bottom Line
	•	±20% is the right default for your Wyckoff + dealer context
	•	It matches dealer hedging reality
	•	It avoids false walls
	•	It is neither too aggressive nor too lax
	•	Making it CLI-configurable is architecturally correct

If you want, next we can:
	•	Tune symbol-class defaults (mega-cap vs small-cap)
	•	Or wire this directly into the A3.1 single-file story with explicit acceptance criteria.