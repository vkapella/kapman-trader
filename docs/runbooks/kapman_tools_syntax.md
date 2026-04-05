# KapMan Tools Syntax

## Establish Environment

source venv/bin/activate

set -a
source .env
set +a

## Start/Stop Docker Env

docker compose up -d
docker compose down

## Database Access

docker exec -it kapman-db psql -U kapman -d kapman

---
## Deterministic Rebuild

A5 deterministic DB rebuild orchestrator (reuses A6 wipe-and-migrate).

python -m scripts.db.a5_deterministic_rebuild
python -m scripts.db.a5_deterministic_rebuild --iterations 3
python -m scripts.db.a5_deterministic_rebuild --print-migrations

Usage:

python -m scripts.db.a5_deterministic_rebuild [--iterations ITERATIONS] [--print-migrations]

Supported arguments:
- --iterations ITERATIONS: Number of rebuild iterations. Defaults to KAPMAN_REBUILD_ITERATIONS or 1.
- --print-migrations: Print migrations in deterministic apply order and exit.

---
## Ingest Tickers

Bootstrap the full ticker universe from Polygon Reference API.

python -m scripts.ingest_tickers
python -m scripts.ingest_tickers --force
python -m scripts.ingest_tickers --db-url postgresql://...

Usage:

python -m scripts.ingest_tickers [--db-url DB_URL] [--force]

Supported arguments:
- --db-url DB_URL: Override DATABASE_URL.
- --force: Re-fetch and upsert even if tickers is non-empty.

## Ingest Tickers Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db \
  psql -U kapman -d kapman < db/dashboards/0002-A1.1-tickers_and_watchlists_dashboard.sql

---
## Ingest Watchlists

Persist deterministic MVP watchlists (A7). Reads data/watchlists/*.txt and reconciles into public.watchlists.

python -m scripts.ingest_watchlists
python -m scripts.ingest_watchlists --effective-date 2026-04-05
python -m scripts.ingest_watchlists --db-url postgresql://...

Usage:

python -m scripts.ingest_watchlists [--db-url DB_URL] [--effective-date EFFECTIVE_DATE]

Supported arguments:
- --db-url DB_URL: Override DATABASE_URL.
- --effective-date EFFECTIVE_DATE: Effective date in YYYY-MM-DD. Defaults to today.

## Ingest Watchlists Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db \
  psql -U kapman -d kapman < db/dashboards/0002-A1.1-tickers_and_watchlists_dashboard.sql

---
## Ingest OHLCV

Canonical OHLCV ingestion pipeline (A0). Reads Polygon S3 flat files and upserts into public.ohlcv.

Top-level usage:

python -m scripts.ingest_ohlcv [--db-url DB_URL] {base,incremental,backfill} ...

Examples:

python -m scripts.ingest_ohlcv base --days 1 --as-of 2026-04-04
python -m scripts.ingest_ohlcv incremental --date 2026-04-04
python -m scripts.ingest_ohlcv backfill --start 2026-04-01 --end 2026-04-04

Common arguments for all subcommands:
- --db-url DB_URL: Override DATABASE_URL.
- --verbosity {quiet,normal,debug}: Output mode.
- --max-symbol-sample MAX_SYMBOL_SAMPLE: Max sample size in debug output.
- --symbols SYMBOLS: Comma-separated symbol subset.
- --strict-missing-symbols: Fail if flatfiles contain symbols missing from tickers.
- --no-ticker-bootstrap: Disable automatic ticker bootstrap if tickers is empty.

### base

python -m scripts.ingest_ohlcv base [--db-url DB_URL] [--verbosity {quiet,normal,debug}] \
  [--max-symbol-sample MAX_SYMBOL_SAMPLE] [--symbols SYMBOLS] [--strict-missing-symbols] \
  [--no-ticker-bootstrap] [--days DAYS] [--as-of AS_OF]

Additional arguments:
- --days DAYS: Number of available daily files to ingest. Defaults to OHLCV_HISTORY_DAYS or 730.
- --as-of AS_OF: Latest date to consider. Defaults to yesterday.

### incremental

python -m scripts.ingest_ohlcv incremental [--db-url DB_URL] [--verbosity {quiet,normal,debug}] \
  [--max-symbol-sample MAX_SYMBOL_SAMPLE] [--symbols SYMBOLS] [--strict-missing-symbols] \
  [--no-ticker-bootstrap] [--date DATE] [--start START] [--end END]

Additional arguments:
- --date DATE: Single date in YYYY-MM-DD.
- --start START: Start date in YYYY-MM-DD.
- --end END: End date in YYYY-MM-DD.

### backfill

python -m scripts.ingest_ohlcv backfill [--db-url DB_URL] [--verbosity {quiet,normal,debug}] \
  [--max-symbol-sample MAX_SYMBOL_SAMPLE] [--symbols SYMBOLS] [--strict-missing-symbols] \
  [--no-ticker-bootstrap] --start START --end END

Required arguments:
- --start START: Start date in YYYY-MM-DD.
- --end END: End date in YYYY-MM-DD.

## Ingest OHLCV Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db \
  psql -U kapman -d kapman < db/dashboards/0000-A0-ohlcv_dashboard.sql

---
## Options Chain Ingestion

A1 options chain ingestion (watchlists -> options_chains). Reads active symbols from public.watchlists, fetches options snapshots from the selected provider, and upserts into public.options_chains.

python -m scripts.ingest_options
python -m scripts.ingest_options --as-of 2026-04-04
python -m scripts.ingest_options --symbols AVGO --concurrency 1
python -m scripts.ingest_options --start-date 2026-04-01 --end-date 2026-04-04 --provider polygon

Usage:

python -m scripts.ingest_options [--db-url DB_URL] [--api-key API_KEY] [--as-of AS_OF] \
  [--snapshot-time SNAPSHOT_TIME] [--start-date START_DATE] [--end-date END_DATE] \
  [--concurrency CONCURRENCY] [--symbols SYMBOLS] [--provider {unicorn,polygon}] \
  [--large-symbols LARGE_SYMBOLS] [--log-level {DEBUG,INFO,WARNING,ERROR}] \
  [--verbose] [--quiet] [--heartbeat HEARTBEAT] [--run-id RUN_ID] [--emit-summary] [--dry-run]

Supported arguments:
- --db-url DB_URL: Override DATABASE_URL.
- --api-key API_KEY: Override the provider API key.
- --as-of AS_OF: Provider as_of date in YYYY-MM-DD.
- --snapshot-time SNAPSHOT_TIME: Optional snapshot identity in ISO-8601. Normal runs should let this derive from --as-of or the range.
- --start-date START_DATE: Start date for historical range mode.
- --end-date END_DATE: Inclusive end date for historical range mode.
- --concurrency CONCURRENCY: Max concurrent symbols. Default 5.
- --symbols SYMBOLS: Comma-separated subset. Still intersected with active watchlists.
- --provider {unicorn,polygon}: Options provider. Defaults to env OPTIONS_PROVIDER or unicorn.
- --large-symbols LARGE_SYMBOLS: Comma-separated symbols forced to serial ingestion.
- --log-level {DEBUG,INFO,WARNING,ERROR}: Base log level.
- --verbose: Shorthand for debug logging.
- --quiet: Suppress INFO logs unless DEBUG is explicitly set.
- --heartbeat HEARTBEAT: Emit heartbeat every N symbols. Default 25.
- --run-id RUN_ID: Optional run identifier.
- --emit-summary: Emit structured summary at the end.
- --dry-run: Resolve scheduling without fetching provider data or writing to the DB.

## Ingest Options Chain Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db \
  psql -U kapman -d kapman < db/dashboards/0001-A1-options_chains_dashboard.sql

---
## Compute Local TA + Price Metrics

KapMan A2: compute local TA + price metrics into daily_snapshots.

python -m scripts.run_a2_local_ta
python -m scripts.run_a2_local_ta --date 2026-04-04
python -m scripts.run_a2_local_ta --start-date 2026-04-01 --end-date 2026-04-04 --workers 4
python -m scripts.run_a2_local_ta --fill-missing --quiet

Usage:

python -m scripts.run_a2_local_ta [--db-url DB_URL] [--date DATE] [--start-date START_DATE] \
  [--end-date END_DATE] [--fill-missing] [--verbose] [--debug] [--quiet] \
  [--heartbeat HEARTBEAT] [--enable-pattern-indicators] \
  [--ticker-chunk-size TICKER_CHUNK_SIZE] [--workers WORKERS] [--max-workers MAX_WORKERS]

Supported arguments:
- --db-url DB_URL: Override DATABASE_URL.
- --date DATE: Single trading date.
- --start-date START_DATE: Start trading date.
- --end-date END_DATE: End trading date.
- --fill-missing: Only compute rows missing in daily_snapshots.
- --verbose: INFO-level per-ticker logging.
- --debug: DEBUG-level indicator logging. Implies --verbose.
- --quiet: Only warnings and final summary.
- --heartbeat HEARTBEAT: Heartbeat every N tickers. Default 50.
- --enable-pattern-indicators: Enable TA-Lib candlestick pattern indicators (CDL*).
- --ticker-chunk-size TICKER_CHUNK_SIZE: Tickers per chunk. Default 500.
- --workers WORKERS: Worker processes. Default auto.
- --max-workers MAX_WORKERS: Hard cap on workers. Default 6.

## Daily Snapshot Integrity and Coverage Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db \
  psql -U kapman -d kapman < db/dashboards/0005-A2-daily_snapshot_dashboard.sql

## Compute Dealer Metrics

KapMan A3: compute dealer metrics into daily_snapshots.

python -m scripts.run_a3_dealer_metrics
python -m scripts.run_a3_dealer_metrics --date 2026-04-04
python -m scripts.run_a3_dealer_metrics --snapshot-time 2026-04-03T04:59:59.999999+00:00
python -m scripts.run_a3_dealer_metrics --start-date 2026-04-01 --end-date 2026-04-04 --fill-missing

Usage:

python -m scripts.run_a3_dealer_metrics [--db-url DB_URL] [--date DATE] \
  [--snapshot-time SNAPSHOT_TIME] [--start-date START_DATE] [--end-date END_DATE] \
  [--fill-missing] [--verbose] [--debug] [--quiet] \
  [--log-level {DEBUG,INFO,WARNING,ERROR}] [--heartbeat HEARTBEAT] \
  [--max-dte-days MAX_DTE_DAYS] [--min-open-interest MIN_OPEN_INTEREST] \
  [--min-volume MIN_VOLUME] [--walls-top-n WALLS_TOP_N] \
  [--gex-slope-range-pct GEX_SLOPE_RANGE_PCT] [--max-moneyness MAX_MONEYNESS] \
  [--spot-override SPOT_OVERRIDE]

Supported arguments:
- --db-url DB_URL: Override DATABASE_URL.
- --date DATE: Single trading date.
- --snapshot-time SNAPSHOT_TIME: Optional legacy snapshot timestamp. The runner normalizes it to the canonical stored daily_snapshots time for its NY trading day.
- --start-date START_DATE: Start trading date.
- --end-date END_DATE: End trading date.
- --fill-missing: Ensure a snapshot exists for every watchlist ticker.
- --verbose: INFO-level per-ticker logging.
- --debug: DEBUG-level per-metric detail. Implies --verbose.
- --quiet: Only warnings and summaries.
- --log-level {DEBUG,INFO,WARNING,ERROR}: Compatibility override for legacy callers.
- --heartbeat HEARTBEAT: Heartbeat every N tickers. Default 50.
- --max-dte-days MAX_DTE_DAYS: Max DTE days. Default 90.
- --min-open-interest MIN_OPEN_INTEREST: Min open interest per contract. Default 100.
- --min-volume MIN_VOLUME: Min volume per contract. Default 1.
- --walls-top-n WALLS_TOP_N: Number of call/put walls to retain. Default 3.
- --gex-slope-range-pct GEX_SLOPE_RANGE_PCT: Price window percentage for GEX slope. Default 0.02.
- --max-moneyness MAX_MONEYNESS: Max moneyness fraction for wall eligibility. Default 0.2.
- --spot-override SPOT_OVERRIDE: Override spot price for diagnostics.

## Daily Snapshot Integrity and Coverage Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db \
  psql -U kapman -d kapman < db/dashboards/0005-A2-daily_snapshot_dashboard.sql

## Compute Volatility Metrics

KapMan A4: compute volatility metrics into daily_snapshots.

python -m scripts.run_a4_volatility_metrics
python -m scripts.run_a4_volatility_metrics --date 2026-04-04
python -m scripts.run_a4_volatility_metrics --start-date 2026-04-01 --end-date 2026-04-04 --fill-missing

Usage:

python -m scripts.run_a4_volatility_metrics [--db-url DB_URL] [--date DATE] \
  [--start-date START_DATE] [--end-date END_DATE] [--fill-missing] \
  [--verbose] [--debug] [--quiet] [--heartbeat HEARTBEAT]

Supported arguments:
- --db-url DB_URL: Override DATABASE_URL.
- --date DATE: Single trading date.
- --start-date START_DATE: Start trading date.
- --end-date END_DATE: End trading date.
- --fill-missing: Ensure a snapshot exists for every watchlist ticker.
- --verbose: INFO-level per-ticker logging.
- --debug: DEBUG-level per-metric detail. Implies --verbose.
- --quiet: Only warnings and summaries.
- --heartbeat HEARTBEAT: Heartbeat every N tickers. Default 50.

## Compute Wyckoff Structural Events

KapMan B2r2: persist canonical Wyckoff structural events into daily_snapshots.

python -m scripts.run_b2_wyckoff_structural_events
python -m scripts.run_b2_wyckoff_structural_events --watchlist
python -m scripts.run_b2_wyckoff_structural_events --symbols AAPL,MSFT --start-date 2026-04-01 --end-date 2026-04-04 --verbose --heartbeat

Usage:

python -m scripts.run_b2_wyckoff_structural_events [--watchlist] [--symbols SYMBOLS] \
  [--start-date START_DATE] [--end-date END_DATE] [--verbose] [--heartbeat]

Supported arguments:
- --watchlist: Restrict to active watchlist symbols.
- --symbols SYMBOLS: Comma-separated symbols.
- --start-date START_DATE: Start date in YYYY-MM-DD.
- --end-date END_DATE: End date in YYYY-MM-DD.
- --verbose: Enable step-level logging.
- --heartbeat: Emit periodic progress logs.

## Compute Wyckoff Structural Events Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db \
  psql -U kapman -d kapman < db/dashboards/0008-B2-wyckoff_structural_events_dashboard.sql

## Compute Wyckoff Regime

KapMan B1: persist daily Wyckoff regime state into daily_snapshots.

python -m scripts.run_b1_wyckoff_regime
python -m scripts.run_b1_wyckoff_regime --watchlist
python -m scripts.run_b1_wyckoff_regime --symbols AAPL,MSFT --verbose --workers 4 --max-workers 6

Usage:

python -m scripts.run_b1_wyckoff_regime [--watchlist] [--symbols SYMBOLS] \
  [--verbose] [--heartbeat] [--workers WORKERS] [--max-workers MAX_WORKERS]

Supported arguments:
- --watchlist: Restrict to active watchlist symbols.
- --symbols SYMBOLS: Comma-separated symbols.
- --verbose: Enable step-level logging.
- --heartbeat: Emit periodic progress logs.
- --workers WORKERS: Worker processes. Default auto.
- --max-workers MAX_WORKERS: Hard cap on workers. Default 6.

## Create Wyckoff Regime Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db \
  psql -U kapman -d kapman < db/dashboards/0007-B1-wyckoff_regime_dashboard.sql

## Compute Wyckoff Derived

KapMan B4: persist derived Wyckoff transitions, sequences, and context events.

python -m scripts.run_b4_wyckoff_derived
python -m scripts.run_b4_wyckoff_derived --watchlist
python -m scripts.run_b4_wyckoff_derived --symbols AAPL,MSFT --start-date 2026-04-01 --end-date 2026-04-04 --include-evidence

Usage:

python -m scripts.run_b4_wyckoff_derived [--watchlist] [--symbols SYMBOLS] \
  [--start-date START_DATE] [--end-date END_DATE] [--verbose] [--heartbeat] [--include-evidence]

Supported arguments:
- --watchlist: Restrict to active watchlist symbols.
- --symbols SYMBOLS: Comma-separated symbols.
- --start-date START_DATE: Start date in YYYY-MM-DD.
- --end-date END_DATE: End date in YYYY-MM-DD.
- --verbose: Enable step-level logging.
- --heartbeat: Emit periodic progress logs.
- --include-evidence: Persist per-day snapshot evidence block.

## Create Wyckoff Derived Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db \
  psql -v symbol='NVDA' -U kapman -d kapman < db/dashboards/0009-B4-wyckoff_derived_dashboard.sql

## Compute Wyckoff Sequences

KapMan B4.1: persist canonical Wyckoff sequences (benchmark-validated).

python -m scripts.run_b4_1_wyckoff_sequences
python -m scripts.run_b4_1_wyckoff_sequences --watchlist
python -m scripts.run_b4_1_wyckoff_sequences --start-date 2026-04-01 --end-date 2026-04-04 --verbose --heartbeat

Usage:

python -m scripts.run_b4_1_wyckoff_sequences [--watchlist] [--start-date START_DATE] \
  [--end-date END_DATE] [--verbose] [--heartbeat]

Supported arguments:
- --watchlist: Restrict to active watchlist symbols.
- --start-date START_DATE: Start date in YYYY-MM-DD.
- --end-date END_DATE: End date in YYYY-MM-DD.
- --verbose: Enable step-level logging.
- --heartbeat: Emit periodic progress logs.

## Produce AI Screening

KapMan C4: batch AI screening execution.

python -m scripts.run_c4_batch_ai_screening --provider openai --model gpt-5 --dry-run
python -m scripts.run_c4_batch_ai_screening --provider openai --model gpt-5 --dry-run --llm-trace full --llm-trace-dir data/llm --symbols AAPL
python -m scripts.run_c4_batch_ai_screening --provider anthropic --model claude-sonnet --snapshot-time 2026-04-02T23:59:59.999999+00:00

Usage:

python -m scripts.run_c4_batch_ai_screening [--db-url DB_URL] [--snapshot-time SNAPSHOT_TIME] \
  --provider {anthropic,openai} --model MODEL [--batch-size BATCH_SIZE] \
  [--batch-wait-seconds BATCH_WAIT_SECONDS] [--max-retries MAX_RETRIES] \
  [--backoff-base-seconds BACKOFF_BASE_SECONDS] [--dry-run] \
  [--log-level {DEBUG,INFO,WARNING,ERROR}] [--symbols SYMBOLS] \
  [--llm-trace {off,summary,full}] [--llm-trace-dir LLM_TRACE_DIR]

Supported arguments:
- --db-url DB_URL: Override DATABASE_URL.
- --snapshot-time SNAPSHOT_TIME: Snapshot time in ISO-8601. The runtime resolves screening against the canonical snapshot for the supplied NY trading day.
- --provider {anthropic,openai}: Required provider.
- --model MODEL: Required model name.
- --batch-size BATCH_SIZE: Symbols per batch.
- --batch-wait-seconds BATCH_WAIT_SECONDS: Pause between batches.
- --max-retries MAX_RETRIES: Retry cap for provider calls.
- --backoff-base-seconds BACKOFF_BASE_SECONDS: Base retry backoff.
- --dry-run: Build batches and context without provider calls.
- --log-level {DEBUG,INFO,WARNING,ERROR}: Log level.
- --symbols SYMBOLS: Comma-delimited list of symbols.
- --llm-trace {off,summary,full}: Trace level.
- --llm-trace-dir LLM_TRACE_DIR: Trace output directory.

## Utility to Produce Parquet of OHLCV for Wyckoff_fast_bench testing

python -m scripts.benchmark_support.export_ohlcv_to_fast_bench_parquet 

## Utility to Produce Production Benchmark data for comparison with benchmark results

Run production Wyckoff evaluation against benchmark outputs.

python -m tools.prod_vs_bench.run_prod_eval --help

python -m tools.prod_vs_bench.run_prod_eval --start-date 2023-12-28 --end-date 2025-12-24 --benchmark-dir "/Volumes/OWC Envoy Pro SX/App Development/wyckoff_fast_bench/outputs/011_Enhance_Wyckoff_Sequence" --output-dir tools/prod_vs_bench/outputs --verbose-metrics --heartbeat-every 200 --workers 6

usage: run_prod_eval.py [-h] --start-date START_DATE --end-date END_DATE [--benchmark-dir BENCHMARK_DIR] [--output-dir OUTPUT_DIR] [--symbols SYMBOLS][--verbose-metrics] [--heartbeat-every HEARTBEAT_EVERY] [--workers WORKERS] [--max-workers MAX_WORKERS]

optional arguments:
  -h, --help                        #show this help message and exit
  --start-date START_DATE           #Start date YYYY-MM-DD
  --end-date END_DATE               #End date YYYY-MM-DD
  --benchmark-dir BENCHMARK_DIR     #Benchmark output directory to mirror into outputs/bench and align schemas
  --output-dir OUTPUT_DIR           #Output directory root
  --symbols SYMBOLS                 #Comma-separated symbols override
  --verbose-metrics                 #Enable verbose progress metrics logging
  --heartbeat-every HEARTBEAT_EVERY #Emit heartbeat every N symbols when verbose metrics enabled
  --workers WORKERS                 #Worker processes (default: min(6, cpu_count))
  --max-workers MAX_WORKERS         #Hard cap on workers

## Utility to Compare Production Benchmark data for comparison with benchmark results

Compare benchmark vs production outputs.

python -m tools.prod_vs_bench.compare_outputs --prod-dir tools/prod_vs_bench/outputs/prod --bench-dir tools/prod_vs_bench/outputs/bench --output-dir tools/prod_vs_bench/outputs/comparison --verbose-metrics

usage: compare_outputs.py [-h] [--prod-dir PROD_DIR] [--bench-dir BENCH_DIR] [--output-dir OUTPUT_DIR] [--verbose-metrics]

optional arguments:
  -h, --help              #show this help message and exit
  --prod-dir PROD_DIR     #Directory containing production outputs
  --bench-dir BENCH_DIR   #Directory containing benchmark outputs
  --output-dir OUTPUT_DIR #Directory to write comparison outputs
  --verbose-metrics       #Enable verbose progress metrics logging


## Test Live Calls to AI Providers


Slice C AI dev runner

python tools/ai_dev_runner.py --provider anthropic --model claude-opus-4-5 --debug
python tools/ai_dev_runner.py --provider openai --model gpt-5.2-2025-12-11 --debug

usage: ai_dev_runner.py [-h] --provider {anthropic,openai} --model MODEL [--debug] [--dry-run]


optional arguments:
  -h, --help           show this help message and exit
  --provider {anthropic,openai}
  --model MODEL
  --debug
  --dry-run

## Chart Generation

Generate OHLCV + TA chart packs (PNG + PDF) for LLM processing from persisted KapMan OHLCV data.

python -m scripts.util.generate_ohlcv_ta_chart_pack --symbols AAPL --start-date 2025-11-01 --end-date 2026-01-09 --bars 60 

usage: generate_ohlcv_ta_chart_pack.py [-h] (--symbols SYMBOLS | --watchlist WATCHLIST) [--start-date START_DATE] [--end-date END_DATE] [--bars BARS] [--out-dir OUT_DIR]
                                       [--pdf-batch-size PDF_BATCH_SIZE] [--ta-metrics TA_METRICS]

Generate OHLCV + TA chart packs (PNG + PDF) for LLM processing from persisted KapMan OHLCV data.

optional arguments:
  -h, --help            show this help message and exit
  --symbols SYMBOLS     Comma-separated symbols (e.g., AAPL,MSFT)
  --watchlist WATCHLIST
                        Watchlist name
  --start-date START_DATE
                        Start date (YYYY-MM-DD)
  --end-date END_DATE   End date (YYYY-MM-DD)
  --bars BARS           Bars to include (default: 90)
  --out-dir OUT_DIR     Output directory (default: data/chart_packs/)
  --pdf-batch-size PDF_BATCH_SIZE
                        PNG batch size per PDF (default: 30)
  --ta-metrics TA_METRICS
                        Comma-separated TA metrics: MA,RSI,MACD,OBV,ADX


## Refreh data

Generate OHLCV + TA chart packs (PNG + PDF) for LLM processing from persisted KapMan OHLCV data.                     
