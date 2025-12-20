KapMan Developer Quick Reset Runbook (Pave / Repave)

Purpose

This runbook defines the authoritative, deterministic procedure to completely destroy and rebuild the KapMan database from scratch in a way that is fully aligned with the architecture and the A6 → A5 → A0 contract.

This is the only supported reset flow. Any deviation is undefined behavior.

⸻

Canonical Invariants (Architecture-Aligned)
	•	Single canonical OHLCV table: public.ohlcv
	•	No compatibility views (ohlcv_daily does not exist)
	•	A6 owns schema creation only
	•	A5 owns deterministic rebuild + baseline validation
	•	A0 owns data hydration only
	•	Base layer is the only ingress from S3
	•	Analytical layer never touches S3
	•	Retention is enforced deterministically (730 trading days)
	•	Watchlists are the authoritative symbol scope for all non-OHLCV ingestion	

⸻

Preconditions
	•	Docker is running
	•	Repo root is current working directory
	•	.env is loaded (DATABASE_URL points to localhost / Docker DB)
	•	All containers except db may remain running

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

Wait until healthcheck passes and shows db health

docker compose ps 

⸻

Step 2 — Apply A6 Schema Baseline (Schema Only)

A6 is responsible for creating tables, types, hypertables, and nothing else.

python -m scripts.db.a5_deterministic_rebuild

Expected outcome:
	•	tickers table exists
	•	ohlcv table exists and is a hypertable
	•	No OHLCV rows exist
	•	No ingestion has occurred

If ohlcv does not exist after this step, the rebuild is invalid.

⸻

Step 2.5 — Persist MVP Watchlists (A7 – Data Seeding Only)

This seeds the authoritative symbol scopes used by downstream ingestion and analytics.

python -m scripts.ingest_watchlists

docker exec -it kapman-db psql -U kapman -d kapman -c "
SELECT watchlist_id,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE active) AS active
FROM public.watchlists
GROUP BY watchlist_id
ORDER BY watchlist_id;
"


Preconditions:
	•	data/watchlists/ directory exists
	•	All watchlist files are .txt
	•	One ticker per line
	•	Filenames define watchlist_id

Behavior:
	•	Creates watchlists deterministically from files
	•	Adds missing symbols
	•	Soft-deactivates removed symbols
	•	Idempotent across re-runs
	•	Uses advisory locks to prevent concurrent execution

Expected outcome:
	•	public.watchlists table populated
	•	One row per (watchlist_id, symbol)
	•	active = true for symbols present in files

This step must complete successfully before:
	•	Options ingestion
	•	Metrics computation
	•	Snapshot generation

If watchlists are empty or missing, the rebuild is invalid.



Step 3 — Load Canonical Ticker Universe (A0 – Tickers Only)

This establishes the symbol → ticker_id mapping required for historical OHLCV.

python -m scripts.ingest_tickers --force

docker exec -it kapman-db psql -U kapman -d kapman -c "
SELECT COUNT(*) FROM public.tickers;
"

Expected outcome:
	•	tickers populated
	•	Symbol universe reflects current Polygon reference, not historical survivorship

This step must occur before any OHLCV ingestion.

⸻

Step 4 — Base OHLCV Hydration from S3 (A0 – Data Only)

This performs full deterministic backfill into ohlcv.

python -m scripts.ingest_ohlcv base

docker exec -it kapman-db psql -U kapman -d kapman -c "
SELECT COUNT(*) FROM ohlcv;
SELECT MIN(date), MAX(date) FROM ohlcv;
"

Behavior:
	•	Reads S3 flatfiles (Base Layer ingress)
	•	Resolves duplicate rows deterministically
	•	Ignores symbols not present in tickers
	•	Enforces rolling retention (default 730 trading days)
	•	Writes only to public.ohlcv

Expected outcome:
	•	ohlcv populated
	•	No writes to any other OHLCV table
	•	No S3 access after completion

⸻

Step 5 — Optional Validation

#get to the docker sql prompt
docker compose exec db psql -U kapman -d kapman

List tables
\dt
#confirm the rogue ohlcv_daily does not exist
\dt ohlcv_daily
SELECT table_name
FROM information_schema.tables
WHERE table_name LIKE '%ohlcv%';

                 List of relations
 Schema |          Name           | Type  | Owner  
--------+-------------------------+-------+--------
 public | daily_snapshots         | table | kapman
 public | ohlcv                   | table | kapman
 public | options_chains          | table | kapman
 public | recommendation_outcomes | table | kapman
 public | recommendations         | table | kapman
 public | tickers                 | table | kapman
(6 rows)
Confirm invariants manually if needed:
	•	SELECT COUNT(*) FROM ohlcv;
	•	SELECT MIN(date), MAX(date) FROM ohlcv;
	•	No table named ohlcv_daily exists

⸻

Explicitly Forbidden Actions
	•	Running A0 before A6 or A5
	•	Creating ohlcv_daily or compatibility views
	•	Loading OHLCV before tickers
	•	Allowing analytical jobs to read from S3
	•	Partial resets (schema without volume removal)

Confirm watchlists exist and are populated:
	•	SELECT watchlist_id, COUNT(*) FROM watchlists GROUP BY watchlist_id;
	•	SELECT COUNT(*) FROM watchlists WHERE active = true;

Expected:
	•	≥ 1 watchlist
	•	Active symbols > 0

⸻

One-Line Story Invariant

At all times, KapMan maintains a single canonical OHLCV hypertable (public.ohlcv), populated only by A0 after deterministic schema creation via A6/A5, with no alternate tables, views, or ingestion paths.

⸻

End of Runbook