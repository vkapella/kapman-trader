# KapMan Tools Syntax

## Establish Environment

source venv/bin/activate

set -a
source .env
set +a

## DATABASE ACCESS

docker exec -it kapman-db psql -U kapman -d kapman 

---
## Deterministic Rebuild

A5 deterministic DB rebuild orchestrator (reuses A6 wipe-and-migrate).

python -m scripts.db.a5_deterministic_rebuild
                                                                                                                 
usage: a5_deterministic_rebuild.py [-h] [--iterations ITERATIONS] [--print-migrations]

optional arguments:
  -h, --help            #show this help message and exit
  --iterations ITERATIONS #Number of rebuild iterations (default: env KAPMAN_REBUILD_ITERATIONS or 1).
  --print-migrations    #Print migrations in deterministic apply order and exit.

---
## Ingest Tickers

Bootstrap the full ticker universe from Polygon Reference API.

python -m scripts.ingest_tickers
python -m scripts.ingest_tickers --force

usage: ingest_tickers.py [-h] [--db-url DB_URL] [--force]

optional arguments:
  -h, --help            # show this help message and exit
  --db-url DB_URL       # Overrides DATABASE_URL (default: env DATABASE_URL)
  --force               # Force re-ingest even if tickers already exist

## Ingest Tickers Dashboard

ocker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0002-A1.1-tickers_and_watchlists_dashboard.sql

---

## Ingest Watchlists

Persist deterministic MVP watchlists (A7). Reads data/watchlists/*.txt and reconciles into public.watchlists.

python -m scripts.ingest_watchlists

usage: ingest_watchlists.py [-h] [--db-url DB_URL] [--effective-date EFFECTIVE_DATE]

optional arguments:
  -h, --help            # show this help message and exit
  --db-url DB_URL       # Overrides DATABASE_URL (default: env DATABASE_URL)
  --effective-date EFFECTIVE_DATE # Effective date (YYYY-MM-DD) applied during reconciliation (default: today)


## Ingest Watchlists Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0002-A1.1-tickers_and_watchlists_dashboard.sql

---

## Ingest OHLCV

Canonical OHLCV ingestion pipeline (A0). Reads Polygon S3 flat files and upserts into public.ohlcv.

python -m scripts.ingest_ohlcv
python -m scripts.ingest_ohlcv base --days 1 --as-of <yesterdays date> #loads 1 day through yesterday

usage: ingest_ohlcv.py [-h] [--db-url DB_URL] {base,incremental,backfill} ...


positional arguments:
  {base,incremental,backfill}
    base                # Full-universe base load ( OHLCV_HISTORY_DAYS or 730)
    incremental         # Incremental daily ingestion (--date, --start, --end)
    backfill            # Bounded historical backfill (--start, --end)

optional arguments:
  -h, --help            # show this help message and exit
  --db-url DB_URL       # Overrides DATABASE_URL (default: env DATABASE_URL)

* base *
base option arguments:
  -h, --help            # show this help message and exit
  --db-url DB_URL                      # Overrides DATABASE_URL (default: env DATABASE_URL)
  --verbosity {quiet,normal,debug}     # Output mode: quiet (summary only), normal (heartbeat), debug (per-date + samples)
  --max-symbol-sample MAX_SYMBOL_SAMPLE #Max symbols to show when samples are printed (debug only; default: 10)
  --symbols SYMBOLS                  #Comma-separated symbol subset (NON-AUTHORITATIVE; default: full universe from tickers table)
  --strict-missing-symbols           #Fail if flatfile contains symbols missing from tickers (default: base load skips missing symbols)
  --no-ticker-bootstrap              #Disable automatic ticker bootstrapping; if tickers is empty, fail as-is
  --days DAYS                        #Number of available daily files to ingest (default: OHLCV_HISTORY_DAYS or 730)
  --as-of AS_OF                      #Latest date to consider (default: yesterday)

* backfill *

usage: ingest_ohlcv.py backfill [-h] [--db-url DB_URL] [--verbosity {quiet,normal,debug}] [--max-symbol-sample MAX_SYMBOL_SAMPLE] [--symbols SYMBOLS] [--strict-missing-symbols] [--no-ticker-bootstrap] --start START --end END

optional arguments:
  -h, --help                              # show this help message and exit
  --db-url DB_URL                         # Overrides DATABASE_URL (default: env DATABASE_URL)
  --verbosity {quiet,normal,debug}        # Output mode: quiet (summary only), normal (heartbeat), debug (per-date + samples)
  --max-symbol-sample MAX_SYMBOL_SAMPLE   #Max symbols to show when samples are printed (debug only; default: 10)
  --symbols SYMBOLS                       #Comma-separated symbol subset (NON-AUTHORITATIVE; default: full universe from tickers table)
  --strict-missing-symbols                #Fail if flatfile contains symbols missing from tickers (default: base load skips missing symbols)
  --no-ticker-bootstrap                   #Disable automatic ticker bootstrapping; if tickers is empty, fail as-is
  --start START                           # Start date (YYYY-MM-DD)
  --end END                               # End date (YYYY-MM-DD)

## Ingest OHLCV Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0000-A0-ohlcv_dashboard.sql

---

## Options Chain Ingestion

A1 options chain ingestion (watchlists -> options_chains). Reads active symbols from public.watchlists, fetches options snapshots from the selected provider, and upserts into public.options_chains.

python -m scripts.ingest_options
python -m scripts.ingest_options --symbols AVGO --concurrency 1 #avoid overruning rate limits    

usage: ingest_options.py [-h] [--db-url DB_URL] [--api-key API_KEY] [--as-of AS_OF] [--snapshot-time SNAPSHOT_TIME] [--start-date START_DATE] [--end-date END_DATE] [--concurrency CONCURRENCY] [--symbols SYMBOLS] [--provider {unicorn,polygon}] [--large-symbols LARGE_SYMBOLS] [--log-level {DEBUG,INFO,WARNING,ERROR}] [--verbose] [--quiet] [--heartbeat HEARTBEAT] [--run-id RUN_ID] [--emit-summary] [--dry-run]

optional arguments:
  -h, --help                     #show this help message and exit
  --db-url DB_URL                #Overrides DATABASE_URL (default: env DATABASE_URL)
  --api-key API_KEY              #Overrides provider API key (default: env POLYGON_API_KEY or UNICORN_API_TOKEN depending on provider)
  --as-of AS_OF                  #Provider as_of date (YYYY-MM-DD)
  --snapshot-time SNAPSHOT_TIME  #Snapshot time used for idempotent re-runs (ISO-8601; default: now UTC)
  --start-date START_DATE        #Start date for range-mode historical ingestion (YYYY-MM-DD)
  --end-date END_DATE            #End date for range-mode historical ingestion (inclusive, YYYY-MM-DD)
  --concurrency CONCURRENCY      #Max concurrent symbols (default: 5)
  --symbols SYMBOLS              #Comma-separated subset of symbols (still intersected with active watchlists)
  --provider {unicorn,polygon}   #Options provider (override env OPTIONS_PROVIDER; default: unicorn)
  --large-symbols LARGE_SYMBOLS  #Comma-separated symbols that should be ingested serially (default: AAPL,MSFT,NVDA,TSLA)
  --log-level {DEBUG,INFO,WARNING,ERROR} #Overrides the default logging level (default: INFO)
  --verbose                      #Shorthand for --log-level DEBUG
  --quiet                        #Suppress INFO logs (overrides --log-level unless DEBUG explicitly set)
  --heartbeat HEARTBEAT          #Emit a heartbeat log every N symbols processed (default: 25)
  --run-id RUN_ID                #Optional run identifier for observability and tracing
  --emit-summary                 #Emit a structured INFO summary at the end of the run
  --dry-run                      #Resolve symbols and scheduling 



## Ingest Options Chain Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0001-A1-options_chains_dashboard.sql
---

## COMPUTE LOCAL TA + PRICE METRICS INTO DAILY SNAPSHOTS

KapMan A2: Compute local TA + price metrics into daily_snapshots

python -m scripts.run_a2_local_ta
python -m scripts.run_a2_local_ta --date 2025-12-21 

usage: run_a2_local_ta.py [-h] [--db-url DB_URL] [--date DATE] [--start-date START_DATE] [--end-date END_DATE] [--fill-missing] [--verbose] [--debug] [--quiet] [--heartbeat HEARTBEAT] [--enable-pattern-indicators] [--ticker-chunk-size TICKER_CHUNK_SIZE] [--workers WORKERS] [--max-workers MAX_WORKERS]


optional arguments:
  -h, --help                            #show this help message and exit
  --db-url DB_URL                       #Override DATABASE_URL
  --date DATE                           #Single trading date (YYYY-MM-DD)
  --start-date START_DATE               #Start trading date (YYYY-MM-DD)
  --end-date END_DATE                   #End trading date (YYYY-MM-DD)
  --fill-missing                        #Only compute rows missing in daily_snapshots
  --verbose                             #INFO-level per-ticker logging
  --debug                               #DEBUG-level indicator logging (implies --verbose)
  --quiet                               #Only warnings + final summary
  --heartbeat HEARTBEAT                 #Heartbeat every N tickers (default: 50)
  --enable-pattern-indicators           #Enable TA-Lib candlestick pattern indicators (CDL*)
  --ticker-chunk-size TICKER_CHUNK_SIZE #Tickers per chunk (default: 500)
  --workers WORKERS                     #Worker processes (default: auto)
  --max-workers MAX_WORKERS             #Hard cap on workers (default: 6)




## Compute Dealer Metrics

KapMan A3: Compute dealer metrics into daily_snapshots 

python -m scripts.run_a3_dealer_metrics   

usage: run_a3_dealer_metrics.py [-h] [--db-url DB_URL] [--snapshot-time SNAPSHOT_TIME] [--max-dte-days MAX_DTE_DAYS] [--min-open-interest MIN_OPEN_INTEREST] [--min-volume MIN_VOLUME]
[--walls-top-n WALLS_TOP_N] [--gex-slope-range-pct GEX_SLOPE_RANGE_PCT] [--max-moneyness MAX_MONEYNESS] [--spot-override SPOT_OVERRIDE] [--log-level {DEBUG,INFO,WARNING}]


optional arguments:
  -h, --help                            #show this help message and exit
  --db-url DB_URL                       #Override DATABASE_URL
  --snapshot-time SNAPSHOT_TIME         #Snapshot time (ISO 8601)
  --max-dte-days MAX_DTE_DAYS           #Max DTE days (default 90)
  --min-open-interest MIN_OPEN_INTEREST #Min open interest per contract (default 100)
  --min-volume MIN_VOLUME               #Min volume per contract (default 1)
  --walls-top-n WALLS_TOP_N             #Number of call/put walls to retain (default 3)
  --gex-slope-range-pct GEX_SLOPE_RANGE_PCT #Price window percentage for GEX slope (default 0.02)
  --max-moneyness MAX_MONEYNESS         #Max moneyness fraction for wall eligibility (default 0.2)
  --spot-override SPOT_OVERRIDE         #Override spot price for all tickers (diagnostics only)
  --log-level {DEBUG,INFO,WARNING}      #Log level (default INFO)

## Daily Snapshot Integrity and Coverage Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0005-A2-daily_snapshot_dashboard.sql

## Compute Volatility Metrics

KapMan A4: Compute volatility metrics into daily_snapshots

python -m scripts.run_a4_volatility_metrics    

optional arguments:
  -h, --help                          #show this help message and exit
  --db-url DB_URL                     #Override DATABASE_URL
  --date DATE                         #Single trading date (YYYY-MM-DD)
  --start-date START_DATE             #Start trading date (YYYY-MM-DD)
  --end-date END_DATE                 #End trading date (YYYY-MM-DD)
  --fill-missing                      #Ensure a snapshot exists for every watchlist ticker
  --verbose                           #INFO-level per-ticker logging
  --debug                             #DEBUG-level per-metric detail (implies --verbose)
  --quiet                             #Only warnings + summaries
  --heartbeat HEARTBEAT               #Heartbeat every N tickers (default: 50)  

## Compute Wyckoff Structural Events

KapMan B2: Compute Wyckoff events into daily_snapshots

usage: run_b2_wyckoff_structural_events.py [-h] [--watchlist] [--symbols SYMBOLS] [--verbose] [--heartbeat]  

python -m scripts.run_b2_wyckoff_structural_events --heartbeat  


## ComputeWyckoff Structural Events Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0008-B2-wyckoff_structural_events_dashboard.sql


## Compute Wyckoff Regime

KapMan B1: Persist daily Wyckoff regime state into daily_snapshots

usage: run_b1_wyckoff_regime.py [-h] [--watchlist] [--symbols SYMBOLS] [--verbose] [--heartbeat] [--workers WORKERS] [--max-workers MAX_WORKERS]

python -m scripts.run_b1_wyckoff_regime --heartbeat  

optional arguments:
  -h, --help                        #show this help message and exit
  --watchlist                       #Restrict to active watchlist symbols
  --symbols SYMBOLS                 #Comma-separated symbols (e.g., AAPL,MSFT)
  --verbose                         #Enable step-level logging
  --heartbeat                       #Emit periodic progress logs
  --workers WORKERS                 #Worker processes (default: auto)
  --max-workers MAX_WORKERS         #Hard cap on workers (default: 6)    

## Create Wyckoff Regime Dashboard

docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0007-B1-wyckoff_regime_dashboard.sql

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
