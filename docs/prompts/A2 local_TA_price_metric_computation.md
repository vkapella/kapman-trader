# CODEX / WINDSURF IMPLEMENTATION PROMPT
## Story [A2] — Local TA + Price Metric Computation (RSI / MACD / SMA / EMA, RVOL / VSI / HV)

You are acting as a Windsurf / Codex execution agent implementing exactly one GitHub issue for the KapMan Trading System.

This document is authoritative, complete, and self-contained.
Do not infer scope beyond what is written here.
Do not introduce new architecture, abstractions, or execution models.

--------------------------------------------------------------------
FROZEN CONTEXT & RULES
--------------------------------------------------------------------
- Architecture, roadmap, and sprint sequencing are frozen.
- MVP, slice-A, blocking work.
- Batch-only, deterministic, re-runnable execution.
- No event-driven logic.
- No async workers.
- No schedulers.
- No external APIs.
- No research code.
- No schema redesign unless unavoidable to compile.

--------------------------------------------------------------------
STORY IDENTITY
--------------------------------------------------------------------
- Story ID: A2
- Title: Local TA + Price Metric Computation
- Roadmap Reference: S-MET-03
- Labels: metrics, slice-A, mvp, blocking
- Primary Output: Persist computed metrics to daily_snapshots

--------------------------------------------------------------------
OBJECTIVE
--------------------------------------------------------------------
Compute core technical indicators and price-derived metrics locally using persisted OHLCV data.

These metrics are inputs only for downstream Wyckoff and recommendation logic.
This story does not interpret signals.

--------------------------------------------------------------------
IN SCOPE (EXACT)
--------------------------------------------------------------------
Technical Indicators:
- RSI(14)
- MACD(12, 26, 9)
  - macd_line
  - macd_signal
  - macd_histogram
- SMA(20)
- SMA(50)
- EMA(12)
- EMA(26)

Price-Derived Metrics:
- RVOL(20)
- VSI(20)
  - MVP definition: identical to RVOL, persisted separately
- HV(20)
  - Log-return based
  - Annualized with sqrt(252)

--------------------------------------------------------------------
OUT OF SCOPE (HARD EXCLUSIONS)
--------------------------------------------------------------------
- Dealer metrics
- Options-derived volatility (IV, skew, term structure)
- Wyckoff logic (phase, events, scoring)
- Recommendations
- Event listeners
- Async / background workers
- External APIs (Polygon, MCP, etc.)
- Research or benchmarking code
- New schemas or migrations

--------------------------------------------------------------------
DATA CONTRACTS
--------------------------------------------------------------------
Tables Read:
- ohlcv_daily
  - Required columns: symbol, date, open, high, low, close, volume

Tables Written:
- daily_snapshots
  - Key: (symbol, date) (or (symbol, time) if schema uses time)
  - Columns written only by this story:
    - rsi_14
    - macd_line
    - macd_signal
    - macd_histogram
    - sma_20
    - sma_50
    - ema_12
    - ema_26
    - rvol
    - vsi
    - hv_20
No other columns may be modified.

--------------------------------------------------------------------
EXECUTION MODEL
--------------------------------------------------------------------
- Batch-only.
- Default execution computes metrics for most recent trading day.
- Optional override: --date YYYY-MM-DD
- Symbol set:
  - Use existing watchlist source if present in repo.
  - Otherwise accept CLI --symbols AAPL,MSFT,...

--------------------------------------------------------------------
LOOKBACK WINDOWS (FIXED)
--------------------------------------------------------------------
| Metric       | Window |
|--------------|--------|
| RSI          | 14     |
| MACD slow    | 26     |
| SMA max      | 50     |
| RVOL / VSI   | 20     |
| HV           | 20     |

- Minimum OHLCV rows required: 50
- If insufficient history:
  - Write NULL for affected metrics
  - Do not fail batch

--------------------------------------------------------------------
METRIC DEFINITIONS (AUTHORITATIVE)
--------------------------------------------------------------------
RSI(14):
- Computed from close using standard rolling RSI.
- Persist value at target_date.

MACD(12,26,9):
- ema_12 = EMA(close, 12)
- ema_26 = EMA(close, 26)
- macd_line = ema_12 - ema_26
- macd_signal = EMA(macd_line, 9)
- macd_histogram = macd_line - macd_signal

SMA / EMA:
- Standard rolling mean / exponential mean.
- Persist values at target_date.

RVOL(20):
RVOL = volume[target_date] / mean(volume over prior 20 trading days)
- Exclude target_date from denominator.

VSI(20):
- MVP alias of RVOL; persist independently.

HV(20):
r_t = ln(close_t / close_{t-1})
hv_20 = stddev(r_t over 20 days) * sqrt(252)

--------------------------------------------------------------------
FAILURE HANDLING RULES
--------------------------------------------------------------------
- Missing OHLCV on target date:
  - Skip symbol
  - Log WARNING
- Insufficient lookback:
  - Write NULLs
  - Log WARNING
- Invalid data (NaN, non-positive close):
  - Write NULL metrics
  - Log ERROR
- Per-symbol failure must not abort batch.

--------------------------------------------------------------------
IDEMPOTENCY RULES
--------------------------------------------------------------------
- Upsert on (symbol, date).
- Re-running for same date produces identical results.
- Only overwrite columns owned by this story.

--------------------------------------------------------------------
TESTING REQUIREMENTS (MANDATORY)
--------------------------------------------------------------------
Unit Tests (Primary):
- Pure computation only (no DB).
- Deterministic fixtures.

Required unit tests:
- RSI correctness
- MACD component correctness
- SMA / EMA window correctness
- HV log-return annualization
- RVOL excludes target day
- Insufficient history returns NULL
- Determinism: same input -> same output

Integration Tests (Minimal, Required):
Purpose: validate persistence contract.

Required integration tests:
- Metrics written for target date
- Idempotent upsert on rerun
- Missing OHLCV date skips symbol
- Partial history writes NULLs
- One symbol failure does not abort others

Coverage:
- >=80% coverage for new code.
- 100% coverage for:
  - metric formulas
  - NULL-handling branches
  - upsert logic

--------------------------------------------------------------------
IMPLEMENTATION GUIDANCE
--------------------------------------------------------------------
- Keep metric computation pure and DB-free.
- Separate: OHLCV retrieval, computation, persistence.
- No generalized metric engine.
- No premature abstractions.
- Prefer clarity over cleverness.

--------------------------------------------------------------------
ACCEPTANCE CHECKLIST
--------------------------------------------------------------------
You are complete only when all are true:
- [ ] All specified metrics computed locally from OHLCV.
- [ ] Metrics persisted to daily_snapshots.
- [ ] Deterministic and re-runnable execution.
- [ ] Unit tests implemented and passing.
- [ ] Integration tests implemented and passing.
- [ ] Coverage >=80%.
- [ ] No scope expansion.

--------------------------------------------------------------------
FINAL DIRECTIVE
--------------------------------------------------------------------
Implement exactly this story, no more and no less.