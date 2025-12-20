Windsurf Implementation Prompt — Polygon Options Contracts + Snapshots Ingestion (Single File)

Objective

Implement a correct, observable, restart-safe options ingestion pipeline using Polygon (Massive) Options Contracts and Option Contract Snapshot APIs, fully aligned to the existing options_chains schema.

The implementation must:

• Populate options_chains deterministically
• Be safe to interrupt and restart
• Provide clear progress visibility without noisy logs
• Avoid leaking credentials
• Correctly map Polygon snapshot fields to schema
• Ensure rows are actually inserted (currently zero rows)

This prompt replaces assumptions about /snapshot/options/{ticker} and fixes the root cause of empty tables.

⸻

1. Canonical Data Flow (REQUIRED)

Phase A — Discover contracts (per underlying symbol)

Use Options Contracts API to enumerate all option contracts for a symbol.

Endpoint:
GET /v3/reference/options/contracts

Filter:
• underlying_ticker = SYMBOL
• expired = false

This produces canonical contract identifiers like:
O:AAPL230616C00150000

This phase determines what contracts exist.

⸻

Phase B — Snapshot each contract

For each contract ticker returned in Phase A, call:

Endpoint:
GET /v3/snapshot/options/{underlying}/{contract}

Example:
/v3/snapshot/options/AAPL/O:AAPL230616C00150000

This produces greeks, IV, bid/ask, OI, etc.

This phase determines current market state.

⸻

Phase C — Normalize + Upsert

Normalize each snapshot into a single options_chains row keyed by:

PRIMARY KEY:
(time, ticker_id, expiration_date, strike_price, option_type)

Use snapshot timestamp (or ingestion time) as time.

Upsert idempotently.

⸻

2. REQUIRED Schema → Snapshot Field Mapping

Table: public.options_chains

Column	Source
time	snapshot.results.last_quote.last_updated OR ingestion timestamp
ticker_id	FK lookup from tickers.symbol = underlying_asset.ticker
expiration_date	snapshot.results.details.expiration_date
strike_price	snapshot.results.details.strike_price
option_type	snapshot.results.details.contract_type (call / put)
bid	snapshot.results.last_quote.bid
ask	snapshot.results.last_quote.ask
last	snapshot.results.last_trade.price
volume	snapshot.results.day.volume
open_interest	snapshot.results.open_interest
implied_volatility	snapshot.results.implied_volatility
delta	snapshot.results.greeks.delta
gamma	snapshot.results.greeks.gamma
theta	snapshot.results.greeks.theta
vega	snapshot.results.greeks.vega
created_at	NOW()

If any optional field is missing, insert NULL. Do not skip the row.

⸻

3. Why Rows Are Currently Zero (Root Cause)

The existing pipeline:

• Calls /snapshot/options/{underlying}
• Does NOT enumerate contracts
• Receives aggregated responses without per-contract identity
• Cannot derive expiration / strike / option_type correctly
• Produces no valid primary keys
• Silently inserts nothing

This must be fixed by explicitly enumerating contracts.

⸻

4. Logging & Observability (STRICT REQUIREMENTS)

Must answer at a glance:

• Is the job running or hung?
• How many symbols completed?
• How many contracts processed?
• Processing rate (contracts/sec)
• Estimated remaining work

Required Logs (INFO only)

At run start:
Options ingestion started: symbols=N

Per symbol completion:
Symbol complete: AAPL | contracts=432 | elapsed=12.4s

Heartbeat every 30s:
Progress: symbols 12/415 | contracts 4,820 | rate 185/sec | ETA 00:03:12

At run end:
Options ingestion complete: symbols=415 | contracts=87,214 | duration=00:07:54

Warnings only for:

• Per-symbol failures
• API errors
• Partial symbol skips

Never log:

• Full URLs with query strings
• API keys
• Per-request HTTP noise

⸻

5. Concurrency & Restart Safety

• Global advisory lock remains REQUIRED
• Per-symbol concurrency allowed
• Each symbol processed in its own transaction scope
• CTRL-C mid-run must:
– Release advisory lock
– Leave committed rows intact
– Allow safe restart without cleanup

Upserts must be idempotent.

⸻

6. Validation Queries (Must Pass After Run)

After ingestion:

SELECT COUNT(*) FROM options_chains;

Must be > 0.

SELECT
  MIN(time),
  MAX(time),
  COUNT(DISTINCT ticker_id)
FROM options_chains;

Must show recent timestamps and multiple tickers.

SELECT t.symbol, COUNT(*)
FROM options_chains o
JOIN tickers t ON t.id = o.ticker_id
GROUP BY t.symbol
ORDER BY COUNT(*) DESC
LIMIT 10;

Must show real contract volumes per symbol.

⸻

7. Files To Modify / Create

Required changes will touch:

• core/providers/market_data/polygon_options.py
– Add contract enumeration
– Add contract snapshot fetch
– Pagination support

• core/ingestion/options/pipeline.py
– Replace snapshot-only logic
– Add Phases A/B/C
– Add progress metrics + heartbeat

• core/ingestion/options/normalizer.py
– Map snapshot → schema exactly as specified

• core/ingestion/options/db.py
– Ensure idempotent upsert works with real PKs

Tests may be updated if assumptions change, but ingestion correctness takes priority.

⸻

8. Non-Goals (Explicit)

• Do NOT compute metrics
• Do NOT trigger downstream pipelines
• Do NOT persist daily_snapshots
• Do NOT optimize prematurely

Correctness, visibility, and data presence are the only goals.

⸻

Deliverable Definition

When complete:

• Running scripts.ingest_options.py produces rows
• Progress is visible and intelligible
• Restarting the job is safe
• Tables are populated correctly
• No credentials appear in logs

Proceed to implement exactly as specified.