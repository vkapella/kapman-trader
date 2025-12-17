# Wyckoff Benchmark (Research Only)

Research harness for benchmarking multiple Wyckoff implementations against shared OHLCV data. Production code under `core/` is untouched.

## What It Does
- Loads OHLCV from Postgres/Timescale (`ohlcv_daily`) with optional parquet caching.
- Runs multiple Wyckoff implementations (handwritten structural, Claude rules, ChatGPT deterministic rules, public-style baselines).
- Computes forward returns (+5/+10/+20/+40) and MAE/MFE (20-bar window).
- Emits signals, summaries, and comparison tables under `research/wyckoff_bench/outputs/`.

## Key Paths
- Config: `research/wyckoff_bench/config/bench.default.yaml`
- Harness: `research/wyckoff_bench/harness/`
- Implementations: `research/wyckoff_bench/implementations/`
- Inputs (rulebooks/prompts/configs): `docs/research_inputs/`

## Quickstart
```bash
python research/wyckoff_bench/run_bench.py --impl all
```

See `docs/WINDSURF_RESEARCH_GUIDE_v1.0.md` for full instructions.
