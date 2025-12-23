KapMan Developer Quick Reset Runbook (Pave / Repave) — Through Options Chains Hydration

Purpose
This runbook defines the authoritative, deterministic procedure to completely destroy and rebuild the KapMan database from scratch, aligned with the architecture and the A6 → A5 → A0 contract, including hydration of options_chains.

This is the only supported reset flow. Any deviation is undefined behavior.

⸻

Canonical Invariants (Architecture-Aligned)
	•	Single canonical OHLCV table: public.ohlcv (TimescaleDB hypertable)
	•	No compatibility views (ohlcv_daily does not exist)
	•	A6 owns schema creation only (tables/types/hypertables/policies)
	•	A5 owns deterministic rebuild + baseline validation (schema apply, invariants)
	•	A0 owns data hydration only (tickers/OHLCV); options ingestion is snapshot-based into options_chains
	•	Retention is enforced deterministically via TimescaleDB policies (730 days)
	•	Watchlists are the authoritative symbol scope for all non-OHLCV ingestion
	•	Options contracts are implicit (derived from snapshot rows); no contracts table; no cron cleanup

⸻

Preconditions
	•	Docker is running
	•	Repo root is current working directory
	•	.env is loaded (DATABASE_URL points to localhost / Docker DB)
	•	All containers except db may remain running

source venv/bin/activate

set -a
source .env
set +a

echo $DATABASE_URL
echo $POLYGON_API_KEY
⸻

Step 0 — Stop and Destroy the Database (Pave)
This removes all persisted state, including schema and data.

docker compose stop db
docker compose rm -f db
docker volume rm kapman-trader_pgdata

⸻

Step 1 — Recreate Empty Database Container
This starts Postgres with zero user tables.

docker compose up -d db
docker compose ps

⸻

Step 2 — Apply A6/A5 Schema Baseline (Schema Only)
A6 is responsible for creating tables, types, hypertables, and policies. No data.

python -m scripts.db.a5_deterministic_rebuild

SQL Verification (Schema + Timescale presence):

docker exec -it kapman-db psql -U kapman -d kapman -c "SELECT extname, extversion FROM pg_extension WHERE extname IN ('timescaledb','uuid-ossp') ORDER BY extname;"

docker exec -it kapman-db psql -U kapman -d kapman -c "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;"

docker exec -it kapman-db psql -U kapman -d kapman -c "SELECT hypertable_schema, hypertable_name, num_chunks, compression_enabled FROM timescaledb_information.hypertables WHERE hypertable_schema = 'public' AND hypertable_name IN ('ohlcv','options_chains') ORDER BY hypertable_name;"      

Confirm dimensions (time column + chunk interval):

docker exec -it kapman-db psql -U kapman -d kapman -c "SELECT hypertable_name, column_name, dimension_type, time_interval FROM timescaledb_information.dimensions WHERE hypertable_schema = 'public' AND hypertable_name IN ('ohlcv','options_chains')ORDER BY hypertable_name, dimension_number;"


2) Correct SQL to verify TimescaleDB compression & retention

A) Verify extensions are installed (COPY-PASTE SAFE)

docker exec -it kapman-db psql -U kapman -d kapman -c "

SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('timescaledb', 'uuid-ossp')
ORDER BY extname;
"

B) Verify hypertables exist (ohlcv + options_chains)

docker exec -it kapman-db psql -U kapman -d kapman -c "

SELECT
  hypertable_schema,
  hypertable_name,
  num_chunks,
  compression_enabled
FROM timescaledb_information.hypertables
WHERE hypertable_schema = 'public'
  AND hypertable_name IN ('ohlcv', 'options_chains')
ORDER BY hypertable_name;
"

Expected:
	•	Both tables listed
	•	compression_enabled = t for options_chains
	•	ohlcv depends on whether you enabled compression


C) Verify retention policies (this is the authoritative source)

docker exec -it kapman-db psql -U kapman -d kapman -c "

SELECT
  job_id,
  proc_name,
  hypertable_schema,
  hypertable_name,
  schedule_interval,
  config
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_retention'
  AND hypertable_schema = 'public'
  AND hypertable_name IN ('ohlcv', 'options_chains')
ORDER BY hypertable_name;
"
Expected:
	•	One row for ohlcv
	•	One row for options_chains
	•	drop_after = 730 days

D) Verify compression policies (this replaces your broken query)

docker exec -it kapman-db psql -U kapman -d kapman -c "

SELECT
  job_id,
  proc_name,
  hypertable_schema,
  hypertable_name,
  schedule_interval,
  config
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression'
  AND hypertable_schema = 'public'
  AND hypertable_name IN ('ohlcv', 'options_chains')
ORDER BY hypertable_name;
"

Expected:
	•	One row for ohlcv
	•	One row for options_chains
	•	compress_after = 120 days


Confirm "forbidden” compatibility table/view does not exist:

docker exec -it kapman-db psql -U kapman -d kapman -c "
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_name = 'ohlcv_daily';
"

Expected outcome after Step 2:
	•	tickers exists (0 rows)
	•	watchlists exists (0 rows) if part of baseline
	•	ohlcv exists as hypertable (0 rows)
	•	options_chains exists as hypertable (0 rows)
	•	retention policy job(s) exist
	•	no ingestion has occurred

⸻

Step 3 — Load Canonical Ticker Universe (Tickers Only)
This establishes the symbol → ticker_id mapping required for OHLCV and options_chains.

python -m scripts.ingest_tickers --force

Verify tickers populated:

docker exec -it kapman-db psql -U kapman -d kapman -c "
SELECT COUNT(*) AS ticker_count FROM public.tickers;
"

Verify watchlist symbols resolve to ticker_id (no missing mappings):

docker exec -it kapman-db psql -U kapman -d kapman -c "
SELECT w.symbol
FROM public.watchlists w
LEFT JOIN public.tickers t ON t.symbol = w.symbol
WHERE w.active = true
AND t.id IS NULL
ORDER BY w.symbol
LIMIT 50;
"

Expected: 0 rows returned (or explicitly understood exceptions if your ticker ingestor filters certain assets).

⸻
Step 4 — Persist MVP Watchlists (Data Seeding Only)
This seeds the authoritative symbol scopes used by options ingestion and analytics.

python -m scripts.ingest_watchlists

Verify watchlists populated:

docker exec -it kapman-db psql -U kapman -d kapman -c "SELECT watchlist_id, COUNT(*) AS total, COUNT(*) FILTER (WHERE active) AS active FROM public.watchlists GROUP BY watchlist_id ORDER BY watchlist_id;"

Verify active symbols > 0:

docker exec -it kapman-db psql -U kapman -d kapman -c "SELECT COUNT(*) AS active_symbols FROM public.watchlists WHERE active = true;"

Expected: 1rows = number of symbols in watchlist 

⸻

Step 5 — Base OHLCV Hydration from S3 (Data Only)
This performs full deterministic backfill into public.ohlcv.

python -m scripts.ingest_ohlcv base

Verify OHLCV rows and date coverage:

Verify retention is configured (already checked in Step 2), and that ohlcv is a hypertable:

docker exec -it kapman-db psql -U kapman -d kapman -c "SELECT COUNT(*) AS ohlcv_rows FROM public.ohlcv;"

docker exec -it kapman-db psql -U kapman -d kapman -c "SELECT MIN(date) AS min_date, MAX(date) AS max_date FROM public.ohlcv;"

docker exec -it kapman-db psql -U kapman -d kapman -c "SELECT hypertable_schema, hypertable_name, num_chunks, compression_enabled FROM timescaledb_information.hypertables WHERE hypertable_schema='public' AND hypertable_name='ohlcv';"


docker exec -i kapman-db psql -U kapman -d kapman -v ON_ERROR_STOP=1 -v DAYS_BACK=30 -v SYMBOL_LIMIT=25 < docs/runbooks/ohlcv_dashboard.sql

⸻

Step 6 — Options Chains Snapshot Hydration (Snapshot-Based into options_chains)
This ingests option snapshots for all active watchlist symbols into public.options_chains.

python -m scripts.ingest_options

**run the options dashboard to verify**

docker exec -i kapman-db psql -U kapman -d kapman -v  ON_ERROR_STOP=1 <docs/runbooks/options_chains_dashboard.sql

**run the options dashboard to verify**

If you want to scope to a subset during smoke testing:
python -m scripts.ingest_options –concurrency 1 –symbols AAPL

Verify options_chains has rows:
docker exec -it kapman-db psql -U kapman -d kapman -c "SELECT COUNT(*) AS options_rows FROM public.options_chains;"

Verify snapshot_time coverage:
docker exec -it kapman-db psql -U kapman -d kapman -c "SELECT MIN(time) AS min_snapshot_time, MAX(time) AS max_snapshot_time FROM public.options_chains;"

Verify per-symbol presence (top 100 by row
docker exec -it kapman-db psql -U kapman -d kapman -c "
SELECT t.symbol, COUNT(*) AS rows
FROM public.options_chains oc
JOIN public.tickers t ON t.id = oc.ticker_id
GROUP BY t.symbol
ORDER BY rows DESC
LIMIT 100;
"

Verify queryability by (time, ticker, expiration_date):
docker exec -it kapman-db psql -U kapman -d kapman -c "
SELECT
t.symbol,
oc.expiration_date,
COUNT(*) AS contracts_in_snapshot
FROM public.options_chains oc
JOIN public.tickers t ON t.id = oc.ticker_id
WHERE oc.time = (SELECT MAX(time) FROM public.options_chains)
GROUP BY t.symbol, oc.expiration_date
ORDER BY t.symbol, oc.expiration_date
LIMIT 100;
"

Verify a single ticker’s latest snapshot surface (sample AAPL):
docker exec -it kapman-db psql -U kapman -d kapman -c "
SELECT
    oc.time,
    t.symbol,
    oc.expiration_date,
    oc.strike_price,
    oc.option_type,
    oc.bid,
    oc.ask,
    oc.last,
    oc.volume,
    oc.open_interest,
    oc.implied_volatility,
    oc.delta,
    oc.gamma,
    oc.theta,
    oc.vega,
    oc.created_at
FROM options_chains AS oc
JOIN tickers AS t
    ON t.id = oc.ticker_id
WHERE t.symbol = 'ORCL'
ORDER BY
    oc.time DESC,
    oc.expiration_date ASC,
    oc.option_type ASC,
    oc.strike_price ASC
LIMIT 1000;"

Confirm options_chains hypertable exists and is recognized by TimescaleDB:
docker exec -it kapman-db psql -U kapman -d kapman -c “
SELECT hypertable_schema, hypertable_name, num_chunks, compression_enabled
FROM timescaledb_information.hypertables
WHERE hypertable_schema=‘public’ AND hypertable_name=‘options_chains’;
“

Confirm retention job exists for options_chains and matches 730 days:
docker exec -it kapman-db psql -U kapman -d kapman -c "
SELECT
j.job_id,
j.proc_name,
j.hypertable_schema,
j.hypertable_name,
j.schedule_interval,
j.config
FROM timescaledb_information.jobs j
WHERE j.proc_name = 'policy_retention'
AND j.hypertable_schema = 'public'
AND j.hypertable_name = 'options_chains';
"

Confirm compression policy exists for options_chains (if configured):
docker exec -it kapman-db psql -U kapman -d kapman -c "
SELECT
j.job_id,
j.proc_name,
j.hypertable_schema,
j.hypertable_name,
j.schedule_interval,
j.config
FROM timescaledb_information.jobs j
WHERE j.proc_name = 'policy_compression'
AND j.hypertable_schema = 'public'
AND j.hypertable_name = 'options_chains';
"

Confirm uniqueness key shape (should match time/ticker/exp/strike/type):
docker exec -it kapman-db psql -U kapman -d kapman -c "
SELECT conname, pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint c
JOIN pg_class r ON r.oid = c.conrelid
JOIN pg_namespace n ON n.oid = r.relnamespace
WHERE n.nspname='public'
AND r.relname='options_chains’'
AND c.contype IN ('p','u')
ORDER BY c.contype, c.conname;
"

Confirm “no contracts table exists” invariant:
docker exec -it kapman-db psql -U kapman -d kapman -c "
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema='public'
AND table_name ILIKE '%contract%'
ORDER BY table_name;
"

⸻

Step 7 — Run Local TA + Price Metrics

python -m scripts.run_a2_local_ta --date 2025-12-05  --workers 6 --ticker-chunk-size 500  

docker exec -it kapman-db psql -U kapman -d kapman

Inspect the daily snapshot schema

 \d+ daily_snapshots;

Count rows for a date range with snapshots, technical indicators and price metrics,

SELECT
  DATE(time) AS snapshot_date,
  COUNT(*)   AS total_rows
FROM daily_snapshots
WHERE time >= '2025-12-15'
  AND time <  '2025-12-20'
GROUP BY DATE(time)
ORDER BY snapshot_date;

SELECT
  DATE(time) AS snapshot_date,
  COUNT(*)   AS rows_with_ta
FROM daily_snapshots
WHERE technical_indicators_json IS NOT NULL
  AND time >= '2025-12-15'
  AND time <  '2025-12-20'
GROUP BY DATE(time)
ORDER BY snapshot_date;

SELECT
  DATE(time) AS snapshot_date,
  COUNT(*)   AS rows_with_price_metrics
FROM daily_snapshots
WHERE price_metrics_json IS NOT NULL
  AND time >= '2025-12-15'
  AND time <  '2025-12-20'
GROUP BY DATE(time)
ORDER BY snapshot_date;


Quick sanity check: latest snapshot rows

SELECT ticker_id, time, jsonb_typeof(technical_indicators_json) AS ta_type,jsonb_typeof(price_metrics_json) AS price_type FROM daily_snapshots ORDER BY time DESC LIMIT 10;

Resolve ticker_id for NVDA (UUID-safe)
SELECT id
FROM tickers
WHERE symbol = 'NVDA';

Assume this returns something like:
id
--------------------------------------
6f8d9a3e-2c7f-4c1a-9c2b-0b4c9a6d8e21

Inspect full TA metrics blob (correct, passable)
SELECT
  ds.time,
  jsonb_pretty(ds.technical_indicators_json)
FROM daily_snapshots ds
WHERE ds.ticker_id = '6f8d9a3e-2c7f-4c1a-9c2b-0b4c9a6d8e21'
ORDER BY ds.time DESC
LIMIT 1;

Inspect full price metrics blob
SELECT
  ds.time,
  jsonb_pretty(ds.price_metrics_json)
FROM daily_snapshots ds
WHERE ds.ticker_id = '6f8d9a3e-2c7f-4c1a-9c2b-0b4c9a6d8e21'
ORDER BY ds.time DESC
LIMIT 1;

This avoids manual UUID lookup and is what you should normally use.
TA metrics
SELECT
  t.symbol,
  ds.time,
  jsonb_pretty(ds.technical_indicators_json)
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE t.symbol = 'ORCL'
ORDER BY ds.time DESC
LIMIT 1;


SELECT ticker_id, jsonb_pretty(technical_indicators_json) FROM daily_snapshots WHERE ticker_id = 'NVDA' ORDER BY time DESC LIMIT 1;


Step 8 — Run Dealer Metrics

docker exec -it kapman-db psql -U kapman -d kapman

python -m scripts.run_a3_dealer_metrics --start-date 2025-12-15 --end-date 2025-12-19 --workers 6   

**dealer-dashboard to check the success of dealer metrics calculation**

docker exec -i kapman-db psql -U kapman -d kapman -v SNAPSHOT_N=1 < docs/runbooks/dealer_metrics_dashboard.sql

**dealer-dashboard to check the success of dealer metrics calculation** 

Step 9 — Optional: Full Integration Test Sweep (Schema + Invariants + A6.1 Coverage)
Use your integration tests to validate deterministic rebuild and A6.1 guarantees.

pytest -q tests/integration/test_a5_deterministic_database_rebuild.py
pytest -q tests/integration/test_a6_1_options_chains_timescaledb.py

⸻

Explicitly Forbidden Actions
	•	Running OHLCV ingestion before tickers
	•	Creating ohlcv_daily or compatibility views
	•	Cron-based deletion/cleanup of options rows
	•	Creating a separate options_contracts table
	•	Partial resets (schema without volume removal)

⸻

One-Line Story Invariant
At all times, KapMan maintains a single canonical OHLCV hypertable (public.ohlcv) and a snapshot-based options hypertable (public.options_chains), both governed by TimescaleDB lifecycle policies (retention/compression as configured), populated only by deterministic ingestion after an A6/A5 schema rebuild.