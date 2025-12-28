# Experiment: SPRING → AR Entry (exp_spring_ar_entry_v1)

What it is: keeps AR entries only when they follow a SPRING for the same symbol within a short bar window. Detection logic is unchanged; this is a sequencing filter.

Why AR (not SPRING): AR remains the execution point, using SPRING only as confirmation that selling climax was tested and demand showed up. Direction/role stay UP/ENTRY.

What changes vs baseline AR: adds temporal structure (SPRING must precede AR within `spring_to_ar_max_bars`, default 15). No volatility or score thresholds; all other events are dropped.

How to run:
```bash
DATABASE_URL=postgresql://kapman:kapman123@127.0.0.1:5432/kapman \
python3 docs/research/wyckoff_algo/experiments/exp_spring_ar_entry/run.py
```
Outputs (under `docs/research/wyckoff_algo/outputs/exp_spring_ar_entry/`):
- `events.parquet`, `events.csv` (filtered AR-only stream with `experiment_id`)
- `benchmark_results.parquet`, `benchmark_results.csv` (same horizons/math as baseline)

Notes:
- Reads raw detector output from `outputs/raw/events.parquet`.
- Baseline and qualified AR experiments remain unchanged; no chaining between experiments.
