# Story: [A2] Local TA + Price Metric Computation (RSI/MACD/SMA/EMA, RVOL/VSI/HV)

**Roadmap Ref:** S-MET-03  
**Labels:** metrics, metrics computations, slice-A, mvp, blocking  
**Execution Model:** Batch-only, deterministic, re-runnable  
**Primary Output:** Persist computed metrics to `daily_snapshots` for the target trading day

---

## 1. Intent

### 1.1 Why this issue exists
This story implements KapMan’s foundational local analytics layer by computing core technical indicators and price-derived metrics directly from persisted OHLCV data. These metrics are required inputs for downstream Wyckoff interpretation and recommendation generation, and must be deterministic and re-runnable.

### 1.2 What this story delivers
- Batch computation of:
  - **Technical indicators:** RSI(14), MACD(12,26,9), SMA(20/50), EMA(12/26)
  - **Price metrics:** RVOL(20), VSI(20), HV(20)
- Reads **only** from persisted OHLCV tables.
- Writes results to `daily_snapshots` for `(symbol, target_date)`.
- Deterministic, idempotent upsert behavior.

### 1.3 What this story does NOT do
- No dealer metrics, options-derived volatility, IV/skew/term structure.
- No Wyckoff phase/event logic or scoring.
- No recommendations or trade interpretation.
- No event-driven listeners or async workers.
- No new schemas/migrations unless explicitly required by the repo state.
- No external API calls.

---

## 2. Inputs, Outputs, and Invariants

### 2.1 Tables Read
- `ohlcv_daily` (base OHLCV hypertable)
  - Required columns: `symbol`, `date`, `open`, `high`, `low`, `close`, `volume`

> Note: This story assumes watchlist symbol selection exists elsewhere (e.g., `portfolio_tickers` or equivalent). If no watchlist table exists, the symbol list must be passed explicitly via CLI option (see §4.2) for MVP execution.

### 2.2 Tables Written
- `daily_snapshots`
  - Key: `(symbol, date)` (or `(symbol, time)` if the schema uses `time`)
  - Columns written by this story (scalar or JSONB, depending on schema):
    - `rsi_14`
    - `macd_line`, `macd_signal`, `macd_histogram`
    - `sma_20`, `sma_50`
    - `ema_12`, `ema_26`
    - `rvol`
    - `vsi`
    - `hv_20`

### 2.3 External Services
- None.

### 2.4 Invariants / Constraints
- **Determinism:** Outputs are pure functions of (OHLCV slice, fixed windows). No randomness, no external calls.
- **Re-runnable:** Safe to re-run for the same `target_date`; results are identical given same OHLCV inputs.
- **Idempotent writes:** Upsert on `(symbol, date)`; no duplicate rows; overwrites only the metrics owned by this story.
- **Lookback sufficiency:** If insufficient history exists for a metric, write `NULL` for that metric (no interpolation).
- **Batch-only:** No event-driven designs or background scheduling introduced.

---

## 3. Metric Definitions (MVP)

### 3.1 Lookback Windows (Fixed)
- RSI: 14 trading days
- MACD: fast=12 EMA, slow=26 EMA, signal=9 EMA of MACD line
- SMA: 20, 50
- EMA: 12, 26
- RVOL: 20
- VSI: 20 (MVP definition aligns to RVOL)
- HV: 20 (annualized)

### 3.2 RSI(14)
- Compute price changes on `close`
- Gains/losses use standard Wilder-style smoothing or simple rolling mean (choose one and document in code)
- Output is RSI value for `target_date`

### 3.3 MACD(12,26,9)
- `ema_12 = EMA(close, 12)`
- `ema_26 = EMA(close, 26)`
- `macd_line = ema_12 - ema_26`
- `macd_signal = EMA(macd_line, 9)`
- `macd_histogram = macd_line - macd_signal`
- Persist values for `target_date`

### 3.4 SMA(20/50), EMA(12/26)
- Standard rolling mean for SMA
- Standard exponential moving average for EMA
- Persist values for `target_date`

### 3.5 RVOL(20) and VSI(20)
- **RVOL(20):** `volume[target_date] / mean(volume over prior 20 trading days)`
  - Use *prior* days only (exclude `target_date` from the denominator) to avoid self-influence:
    - `mean(volume[-20:-1])` relative to `target_date`
- **VSI(20):** MVP definition is the same as RVOL(20), persisted as a separate field for future refinement.

### 3.6 HV(20) (Historical Volatility)
- Compute daily log returns: `r_t = ln(close_t / close_{t-1})`
- Compute rolling stddev over last 20 returns
- Annualize: `hv_20 = stddev_20 * sqrt(252)`
- Persist value for `target_date`

---

## 4. Data Flow & Control Flow

### 4.1 Batch Boundaries
- One run computes metrics for **one trading day** (`target_date`) across the symbol set.

### 4.2 Execution Parameters (CLI)
- `--date YYYY-MM-DD` (optional)
  - If omitted: resolve `target_date = MAX(date)` from `ohlcv_daily`
- `--symbols AAPL,MSFT,...` (optional)
  - If omitted: use watchlist symbol source (preferred) if available in repo
- `--lookback-days N` (optional, default=60)
  - Must be ≥ 50 to support SMA50 and MACD slow leg; recommended default 60 for buffer

### 4.3 Step-by-Step Control Flow
1. Resolve `target_date`
2. Resolve symbol set (watchlist or CLI `--symbols`)
3. Fetch OHLCV slice for all symbols covering `target_date` and `lookback_days` prior trading sessions
4. For each symbol:
   - Validate OHLCV presence for `target_date`
   - Build ordered DataFrame (`date` ascending)
   - Compute indicators and metrics across the window
   - Extract values at `target_date`
   - Build snapshot payload (with explicit `NULL` for insufficient history)
   - Upsert into `daily_snapshots` on `(symbol, target_date)`

### 4.4 Batch Behavior
- Per-symbol failures do not abort the batch.
- Only the affected symbol is skipped/partially written (see §5).

---

## 5. Failure Modes & Idempotency

### 5.1 Failure Modes and Handling
- **Insufficient lookback history**
  - Write `NULL` for metrics that cannot be computed.
  - Log `WARNING` with symbol/date and missing-metric list.
- **Missing OHLCV row on target_date**
  - Do not write a snapshot row for that symbol/date.
  - Log `WARNING`.
- **Invalid input values (NaNs, non-positive close, etc.)**
  - Write `NULL` for affected metrics and continue.
  - Log `ERROR` with symbol/date context.
- **Computation exceptions**
  - Catch per symbol; log `ERROR`; continue other symbols.
- **DB write failures**
  - Fail for the symbol write; log `ERROR`; continue remaining symbols.

### 5.2 Idempotent Write Strategy
- Upsert keyed on `(symbol, target_date)`:
  - If exists: update only the metric columns owned by this story.
  - If not: insert new row with metric columns plus identity fields.
- Re-running for the same day overwrites identical values without side effects.

### 5.3 Retry Strategy
- No automatic retries inside the run.
- Operator re-run is the retry mechanism (safe due to idempotency).

---

## 6. Testing Strategy

### 6.1 Unit Tests (Primary)
**Goal:** validate formulas, edge cases, determinism.

**Proposed files**
- `tests/unit/metrics/test_ta_price_metrics.py`

**Required unit tests**
- `test_rsi_computation_known_series`
- `test_macd_line_signal_histogram_present`
- `test_sma_ema_windows_match_expected`
- `test_hv20_log_return_annualization`
- `test_rvol_uses_prior_window_excludes_target_day`
- `test_insufficient_lookback_returns_nulls`
- `test_determinism_same_input_same_output`

**Notes**
- Use fixed OHLCV fixtures (no DB).
- Keep numeric tolerance explicit (e.g., `abs(actual-expected) < 1e-6` where relevant).

### 6.2 Integration Tests (Minimal, Contract-Focused)
**Goal:** validate persistence contract and idempotent upsert.

**Proposed files**
- `tests/integration/metrics/test_snapshot_persistence.py`

**Required integration tests**
- `test_metrics_written_for_target_date`
  - Seed OHLCV; run job; assert `daily_snapshots` row exists with expected fields non-null where applicable.
- `test_idempotent_upsert_rerun`
  - Run job twice; assert values unchanged and only one row exists per `(symbol,date)`.
- `test_missing_target_date_ohlcv_skips_symbol`
  - Seed OHLCV missing target date; assert no snapshot row created.
- `test_partial_history_writes_nulls`
  - Seed limited history; assert row exists with null fields for insufficient metrics.
- `test_one_symbol_failure_does_not_abort_others`
  - Induce one symbol computation error; ensure others persisted.

### 6.3 Coverage Gates
- New code coverage ≥ 80%
- 100% coverage for:
  - metric formula helpers
  - NULL-handling branches
  - upsert path logic

---

## 7. Operational Considerations

### 7.1 Reruns and Backfills
- Default run processes most recent trading day.
- Historical recompute supported via `--date`.
- No async backfill introduced.

### 7.2 Logging
- `INFO`: run start/end, target_date, symbol count, success summary
- `WARNING`: missing OHLCV row for target_date, insufficient history
- `ERROR`: per-symbol compute or write failures

### 7.3 Performance
- Expect ≤140 symbols, ≤60 rows each
- Runs in seconds to low tens of seconds on a Mac
- No premature optimization required.

---

## 8. Acceptance Criteria Checklist

- [ ] RSI(14), MACD(12,26,9), SMA(20/50), EMA(12/26) computed from persisted OHLCV
- [ ] RVOL(20), VSI(20), HV(20) computed from persisted OHLCV
- [ ] Results persisted to `daily_snapshots` for `(symbol, target_date)`
- [ ] Deterministic and re-runnable execution (idempotent upsert)
- [ ] Unit tests implemented and passing
- [ ] Minimal integration tests implemented and passing
- [ ] Coverage ≥ 80% for new code

---

## 9. Implementation Notes (Non-Normative)

- Prefer a single module responsible for:
  - fetching OHLCV window
  - computing metrics
  - producing `(symbol, date) -> payload`
  - persisting via upsert
- Keep computation functions pure and testable (DB-free).
- Persistence layer should be thin and isolated to enable integration testing.