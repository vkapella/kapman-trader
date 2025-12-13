# WINDSURF GUIDE — RESEARCH TRACK (WYCKOFF BENCH)
**Version:** 1.0  
**Scope:** Research-only Wyckoff benchmarking (outside `core/`)  
**Audience:** Cascade/Windsurf sessions running the research harness

---

## 1) Session Setup
- Load: `docs/KAPMAN_ARCHITECTURE_v3.1.md` and `docs/WINDSURF_GUIDE_v3.1.md` (production reference).  
- Load: `docs/KAPMAN_RESEARCH_ARCHITECTURE_v1.0.md` (this file) to keep work isolated.  
- Verify required inputs live in `docs/research_inputs/` (Claude prompt, deterministic rules, configs, handwritten code).

## 2) Scope Guardrails
- Do not touch `core/` or production pipelines; research code stays under `research/wyckoff_bench/`.  
- Read-only access to Postgres `ohlcv_daily`.  
- All configs/prompts/rulebooks must be read from `docs/research_inputs/`.  
- Outputs stay under `research/wyckoff_bench/outputs/`.

## 3) Running Benchmarks
Example (default config + all implementations):
```bash
python research/wyckoff_bench/run_bench.py --impl all
```

Custom symbols/date range:
```bash
python research/wyckoff_bench/run_bench.py \
  --symbols AAPL,MSFT,NVDA,TSLA \
  --start 2022-01-01 --end 2023-12-31 \
  --impl kapman_v0_claude \
  --cfg research/wyckoff_bench/config/bench.default.yaml
```

## 4) Outputs & Interpretation
- `signals_<run_id>.parquet`: per-implementation signals (event booleans + normalized scores + debug).  
- `summary_<run_id>.parquet` / `.csv`: per-event/horizon aggregates (density, forward returns, MAE/MFE).  
- `comparison_<run_id>.csv`: best implementation per event/horizon by composite return/MAE blend.
Interpretation:
- **Density:** fraction of days flagged per event; high density with poor returns may indicate overfitting.  
- **Returns:** forward % change from signal close to horizon close.  
- **MAE/MFE:** path risk window (20 bars); lower MAE with reasonable MFE preferred.  
- **Composite:** weighted blend of return rank and MAE rank to pick stable performers.

## 5) Adding Implementations
- Drop adapter in `research/wyckoff_bench/implementations/`, conform to `WyckoffImplementation` protocol.  
- Read all configs/rules from `docs/research_inputs/`.  
- Register in `bench.default.yaml` (name + optional per-impl cfg).

## 6) Testing
- Unit tests live in `tests/unit/research_wyckoff_bench/`.  
- Run locally:
```bash
pytest tests/unit/research_wyckoff_bench -v
```
- Coverage target: ≥80% for research modules. DB-dependent loader tests gate on `USE_TEST_DB=true`.

## 7) Troubleshooting
- Missing `DATABASE_URL`: set env before running CLI.  
- Parquet errors: install `pyarrow` or `fastparquet`.  
- Cache mismatch: remove `research/wyckoff_bench/outputs/cache/*.parquet` for a clean pull.  
- DB connectivity: ensure Postgres/Timescale is running with `ohlcv_daily` populated.

