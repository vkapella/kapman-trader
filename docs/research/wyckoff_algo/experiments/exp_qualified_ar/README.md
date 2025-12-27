# Experiment: Qualified AR Entry (exp_qualified_ar_v1)

Purpose: post-hoc filter that keeps only AR events preceded by SC or SPRING within a configurable lookback and occurring in a higher-volatility regime (ATR percentile >= threshold). Baseline detection and benchmark math remain unchanged.

How it differs from baseline:
- Uses baseline AR timestamps only (no new events, no timing changes).
- Requires prior SC or SPRING within `lookback_bars` (default 20).
- Requires ATR (lookback `atr_lookback`, default 14) to be at/above `atr_percentile_min` (default 50th percentile) using expanding percentile ranks (no lookahead).
- Drops all non-AR events; direction/role stay UP/ENTRY as in baseline mapping.

How to run:
```bash
# Ensure DATABASE_URL is set to the dev Postgres value
DATABASE_URL=postgresql://kapman:kapman123@127.0.0.1:5432/kapman \
python3 docs/research/wyckoff_algo/experiments/exp_qualified_ar/run.py
```
Outputs (under `docs/research/wyckoff_algo/outputs/exp_qualified_ar/`):
- `events.parquet` and `events.csv` (filtered AR-only stream with `experiment_id`)
- `benchmark_results.parquet` and `benchmark_results.csv` (same horizons/math as baseline)
