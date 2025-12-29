WINDSURF TASK — EXPORT OHLCV TO PARQUET FOR FAST BENCH

Objective

Create a read-only OHLCV Parquet export from the existing PostgreSQL database used by kapman_trader, suitable for full-universe analytical benchmarking in a separate repository (wyckoff_fast_bench).

The output must be stored at:

data/fast_bench/ohlcv_parquet/

and must be partitioned by symbol for efficient predicate pushdown.

This export is explicitly for research use only and must not modify any database state.

⸻

Constraints (Non-Negotiable)
	1.	Read-only access to Postgres
	2.	No schema changes
	3.	No writes back to the database
	4.	Deterministic output for the same source data
	5.	Parquet output only (no CSV)
	6.	Partition by symbol
	7.	Use existing database connection configuration
	8.	Compatible with full universe (8K–15K symbols, ~2 years)

⸻

Source Data Assumptions

The repository already contains:
	•	PostgreSQL / TimescaleDB with OHLCV data
	•	An ohlcv or ohlcv_daily table (time-series, daily bars)
	•	A working DATABASE_URL environment variable or equivalent config
	•	Python environment with pandas available

If multiple OHLCV tables exist, select the canonical daily OHLCV table used by analytics.

⸻

Required Output Schema (Exact)

The Parquet dataset must contain exactly these columns:
	•	symbol (string)
	•	date (date, not timestamp)
	•	open (float)
	•	high (float)
	•	low (float)
	•	close (float)
	•	volume (float or bigint)

No additional columns.

⸻

File Layout (Required)

data/fast_bench/ohlcv_parquet/
symbol=AAPL/
part.parquet
symbol=MSFT/
part.parquet
symbol=NVDA/
part.parquet
…

Partitioning must be done via directory structure using symbol=.

⸻

Implementation Tasks
	1.	Create a new script at:

scripts/export/export_ohlcv_to_fast_bench_parquet.py
	2.	The script must:
	•	Connect to Postgres using existing configuration
	•	Query the most recent ~730 trading days of daily OHLCV data
	•	Order results by symbol, then date ascending
	•	Normalize timestamps to date
	•	Write Parquet output to data/fast_bench/ohlcv_parquet
	•	Overwrite existing output atomically (delete target dir first, then write)
	3.	Use pandas + pyarrow for Parquet writing.
	4.	The script must be runnable as:

python scripts/export/export_ohlcv_to_fast_bench_parquet.py

⸻

SQL Selection Rules
	•	Select all symbols in the universe (no watchlist filtering)
	•	Use the database’s authoritative OHLCV table
	•	Limit history to the most recent 730 trading days
	•	Do not assume symbol count
	•	Do not hardcode symbol lists

Example logic (conceptual, not prescriptive):
	•	WHERE time >= CURRENT_DATE - INTERVAL ‘730 days’
	•	GROUPING IS NOT REQUIRED
	•	One row per symbol per trading day

⸻

Error Handling Requirements
	•	Fail fast if database connection fails
	•	Fail fast if zero rows are returned
	•	Log:
	•	Row count
	•	Unique symbol count
	•	Date range exported
	•	Output directory path

⸻

Verification Step (Mandatory)

At the end of the script, include a verification step that:
	•	Reads back one symbol partition
	•	Prints:
	•	Symbol name
	•	Row count
	•	Min/max date
	•	Column list

This confirms Parquet correctness before Fast Bench consumes it.

⸻

Deliverables
	1.	New script:
scripts/export/export_ohlcv_to_fast_bench_parquet.py
	2.	New directory created (or replaced):
data/fast_bench/ohlcv_parquet/
	3.	Console output confirming:
	•	Successful export
	•	Symbol count
	•	Row count
	•	Date range

⸻

Acceptance Criteria
	•	Script runs without modifying any database tables
	•	Parquet output is partitioned by symbol
	•	Fast Bench can later read data using:
pandas.read_parquet(path, filters=[(“symbol”, “==”, “AAPL”)])
	•	No Docker changes required
	•	No new dependencies beyond pandas / pyarrow / sqlalchemy (if already used)

⸻

Execution Authorization

You are authorized to:
	•	Inspect repository files
	•	Inspect database access patterns
	•	Reuse existing database utility code if present
	•	Create new scripts and directories under scripts/ and data/

No further confirmation is required. Proceed autonomously until complete.

⸻

End of Task

Produce the implementation directly in the repository.