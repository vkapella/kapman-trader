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

Wait until healthcheck passes (docker compose ps shows db healthy).

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

Step 3 — Load Canonical Ticker Universe (A0 – Tickers Only)

This establishes the symbol → ticker_id mapping required for historical OHLCV.

python -m scripts.ingest_tickers –force

Expected outcome:
	•	tickers populated
	•	Symbol universe reflects current Polygon reference, not historical survivorship

This step must occur before any OHLCV ingestion.

⸻

Step 4 — Base OHLCV Hydration from S3 (A0 – Data Only)

This performs full deterministic backfill into ohlcv.

python -m scripts.ingest_ohlcv base

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

⸻

One-Line Story Invariant

At all times, KapMan maintains a single canonical OHLCV hypertable (public.ohlcv), populated only by A0 after deterministic schema creation via A6/A5, with no alternate tables, views, or ingestion paths.

⸻

End of Runbook