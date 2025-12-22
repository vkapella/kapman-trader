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

---

## Ingest Watchlists

Persist deterministic MVP watchlists (A7). Reads data/watchlists/*.txt and reconciles into public.watchlists.

python -m scripts.ingest_watchlists

usage: ingest_watchlists.py [-h] [--db-url DB_URL] [--effective-date EFFECTIVE_DATE]

optional arguments:
  -h, --help            # show this help message and exit
  --db-url DB_URL       # Overrides DATABASE_URL (default: env DATABASE_URL)
  --effective-date EFFECTIVE_DATE # Effective date (YYYY-MM-DD) applied during reconciliation (default: today)

---

## Ingest OHLCV

Canonical OHLCV ingestion pipeline (A0). Reads Polygon S3 flat files and upserts into public.ohlcv.

python -m scripts.ingest_ohlcv
python -m scripts.ingest_ohlcv base 

usage: ingest_ohlcv.py [-h] [--db-url DB_URL] {base,incremental,backfill} ...


positional arguments:
  {base,incremental,backfill}
    base                # Full-universe base load (last N available trading days)
    incremental         # Incremental daily ingestion
    backfill            # Bounded historical backfill

optional arguments:
  -h, --help            # show this help message and exit
  --db-url DB_URL       # Overrides DATABASE_URL (default: env DATABASE_URL)


---

## Options Chain Ingestion

A1 options chain ingestion (watchlists -> options_chains). Reads active symbols from public.watchlists, fetches options snapshots from the selected provider, and upserts into public.options_chains.

python -m scripts.ingest_options
python -m scripts.ingest_options --provider unicorn --concurrency 4    

usage: ingest_options.py [-h] [--db-url DB_URL] [--api-key API_KEY] [--as-of AS_OF] [--snapshot-time SNAPSHOT_TIME] [--concurrency CONCURRENCY] [--symbols SYMBOLS] [--provider {unicorn,polygon}]

optional arguments:
  -h, --help                    #show this help message and exit
  --db-url DB_URL               #Overrides DATABASE_URL (default: env DATABASE_URL)
  --api-key API_KEY             #Overrides provider API key (default: env POLYGON_API_KEY or UNICORN_API_TOKEN depending on provider)
  --as-of AS_OF                 #Provider as_of date (YYYY-MM-DD)
  --snapshot-time SNAPSHOT_TIME #Snapshot time used for idempotent re-runs (ISO-8601; default: now UTC)
  --concurrency CONCURRENCY     #Max concurrent symbols (default: 5)
  --symbols SYMBOLS             #Comma-separated subset of symbols (still intersected with active watchlists)
  --provider {unicorn,polygon}  #Options provider (override env OPTIONS_PROVIDER; default: unicorn)

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
[--max-spread-pct MAX_SPREAD_PCT] [--walls-top-n WALLS_TOP_N] [--gex-slope-range-pct GEX_SLOPE_RANGE_PCT] [--spot-override SPOT_OVERRIDE] [--log-level {DEBUG,INFO,WARNING}]



optional arguments:
  -h, --help            show this help message and exit
  --db-url DB_URL       Override DATABASE_URL
  --snapshot-time SNAPSHOT_TIME
                        Snapshot time (ISO 8601)
  --max-dte-days MAX_DTE_DAYS
                        Max DTE days (default 90)
  --min-open-interest MIN_OPEN_INTEREST
                        Min open interest per contract (default 100)
  --min-volume MIN_VOLUME
                        Min volume per contract (default 1)
  --max-spread-pct MAX_SPREAD_PCT
                        Max bid-ask spread percentage (default 10.0)
  --walls-top-n WALLS_TOP_N
                        Number of call/put walls to retain (default 3)
  --gex-slope-range-pct GEX_SLOPE_RANGE_PCT
                        Price window percentage for GEX slope (default 0.02)
  --spot-override SPOT_OVERRIDE
                        Override spot price for all tickers (diagnostics only)
  --log-level {DEBUG,INFO,WARNING}
                        Log level (default INFO)