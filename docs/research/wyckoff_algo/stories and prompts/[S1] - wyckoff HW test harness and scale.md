🚀 WINDSURF CODEX PROMPT — WYCKOFF RESEARCH HARNESS v0 (DEV DB)

You are working in an existing repository with a running dev Postgres database (TimescaleDB) managed via Docker Compose.

Your task is to complete Step 4 (benchmark execution) of the Wyckoff research harness using the existing dev database, while preserving the original benchmarking approach from archive/research/wyckoff_bench.

⚠️ CRITICAL CONSTRAINTS (READ CAREFULLY)
	•	DO NOT refactor or “improve” legacy algorithm logic
	•	DO NOT change benchmark math or definitions
	•	DO NOT introduce new indicators, filters, or tuning
	•	DO NOT touch production pipelines
	•	DO NOT invent new abstractions
	•	DO NOT bypass the dev database
	•	DO NOT use S3, files, or external APIs for OHLCV

This is a rewiring and reuse task only.

⸻

ENVIRONMENT (AUTHORITATIVE)

The dev database is already running via Docker Compose.

Use only these environment variables for DB access:

DATABASE_URL=postgresql://kapman:kapman123@127.0.0.1:5432/kapman
ASYNC_DATABASE_URL=postgresql+asyncpg://kapman:kapman123@127.0.0.1:5432/kapman

Assume:
	•	Daily OHLCV data already exists in the dev DB
	•	Schema matches what existing KapMan loaders expect
	•	Two years of data is available per symbol

DO NOT redefine credentials.
DO NOT inline passwords elsewhere.

⸻

CONTEXT

The following directory already exists:

docs/research/wyckoff_algo/
├── legacy/
│   ├── structural.py
│   ├── kapman_v0_handwritten_structural.py
│   └── __init__.py
├── data/
│   └── watchlist_105.txt
├── outputs/
│   └── (empty)

The original benchmark implementation (math + aggregation) lives here and MUST be reused:

archive/research/wyckoff_bench/

The watchlist MUST be loaded from:

docs/research/wyckoff_algo/data/watchlist_105.txt


⸻

OBJECTIVE

Produce a first complete benchmark run using:
	•	Legacy handwritten Wyckoff detector
	•	OHLCV loaded directly from the dev Postgres database
	•	Existing benchmark math from wyckoff_bench
	•	A ~105-symbol watchlist

At the end:
	•	events.parquet exists
	•	benchmark_results.parquet exists
	•	Console summary is printed
	•	System is ready for filter experimentation

⸻

REQUIRED FILES TO CREATE / MODIFY

Create or modify only the following:

docs/research/wyckoff_algo/
├── runner/
│   ├── load_ohlcv.py
│   ├── run_detector.py
│   └── __init__.py
├── benchmark/
│   ├── run_bench.py
│   └── __init__.py

You may copy or lightly adapt code from:

archive/research/wyckoff_bench/


⸻

STEP-BY-STEP REQUIREMENTS

⸻

STEP 2 — OHLCV Loader (DEV DATABASE ONLY)

Create:

docs/research/wyckoff_algo/runner/load_ohlcv.py

Requirements:
	•	Connect using DATABASE_URL
	•	Load symbols from data/watchlist_105.txt
	•	Query daily OHLCV for each symbol
	•	Limit to last 2 years
	•	Return:

dict[str, pandas.DataFrame]

DataFrame constraints:
	•	Columns compatible with legacy/structural.py
	•	Sorted ascending by date
	•	No indicators
	•	No caching
	•	No S3
	•	No CSV fallback

Add logging:
	•	number of symbols loaded
	•	row count per symbol
	•	min/max date per symbol

⸻

STEP 3 — Legacy Detector Runner

Create:

docs/research/wyckoff_algo/runner/run_detector.py

Responsibilities:

For each symbol:
	1.	Load OHLCV via load_ohlcv.py
	2.	Run legacy structural.py
	3.	Normalize via kapman_v0_handwritten_structural.py
	4.	Emit one row per event with schema:

symbol
event
direction
role
event_date
bar_index
impl = "kapman_v0_handwritten_structural"

Persist to:

docs/research/wyckoff_algo/outputs/events.parquet

Constraints:
	•	Deterministic
	•	Idempotent
	•	No benchmark math here
	•	No DB writes

⸻

STEP 4 — Benchmark Execution (REUSE ORIGINAL BENCH)

Create:

docs/research/wyckoff_algo/benchmark/run_bench.py

This file must:
	1.	Reuse benchmark logic from:

archive/research/wyckoff_bench/

specifically:
	•	return calculations
	•	MAE calculations
	•	horizon slicing (5 / 10 / 20 / 40)
	•	aggregation + grouping

	2.	Replace ONLY the inputs:
	•	Signals: outputs/events.parquet
	•	OHLCV: runner/load_ohlcv.py
	•	Symbols: data/watchlist_105.txt
	3.	Explicitly disable:
	•	OHLCV parquet caching
	•	legacy signal generators
	4.	Produce:

docs/research/wyckoff_algo/outputs/benchmark_results.parquet

	5.	Print a console table consistent with prior benchmark output.

DO NOT modify formulas.
DO NOT reweight signals.
DO NOT optimize.

⸻

ACCEPTANCE CRITERIA (ALL REQUIRED)
	•	Dev Postgres DB is the only OHLCV source
	•	Legacy algorithm code remains unchanged
	•	All ~105 symbols processed
	•	events.parquet written
	•	benchmark_results.parquet written
	•	Horizons: 5 / 10 / 20 / 40
	•	Results directionally match prior benchmarks
	•	Ready for filter experimentation

⸻

DEFINITION OF DONE

This task is complete when:

A full Wyckoff benchmark run has executed using legacy handwritten logic across the 105-symbol watchlist, powered by dev database OHLCV, with results persisted under docs/research/wyckoff_algo/outputs.

⸻

FINAL WARNING

Do not “helpfully” redesign anything.
Parity first. Learning second. MVP later.

Proceed carefully.

⸻

If you want next, I can:
	•	Validate the expected OHLCV table schema for load_ohlcv.py
	•	Provide the exact SQL query to use
	•	Prepare the next story for controlled filter experiments
	•	Help you promote this into /core once validated

Just say the word.