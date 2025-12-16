# docs/stories/A1_options_ingestion_watchlist_to_options_chains.md

# STORY A1 — Options Ingestion (Watchlist → options_chains)

Story ID: A1  
Roadmap Reference: S-OPT-02  
Sprint: 2.x  
Status: Planned  

---

## Story Intent

Downstream MVP capabilities (dealer positioning, options-based volatility, and recommendation validation) require real, persisted option contract data. Although the `options_chains` table exists, there is currently no production ingestion path that hydrates it deterministically.

This story establishes the single authoritative ingestion mechanism for options chains so all downstream analytics operate on persisted data rather than live API calls.

---

## Scope

### In Scope
- Ingest full option-chain snapshots for watchlist tickers only
- Two invocation modes using a single shared execution path:
  - Batch (primary): nightly refresh for all watchlist tickers
  - Event-driven (secondary): ingestion when one or more tickers are added to a watchlist
- Source: Polygon Options REST API only (no S3 / Massive)
- Persist data into `options_chains`
- Idempotent, deterministic execution
- Full contract-surface completeness per snapshot (all expirations, strikes, calls, and puts)

### Out of Scope
- Dealer metrics
- Options-based volatility metrics
- Strategy or strike selection logic
- Historical date backfills (date iteration across prior days)
- Schema changes
- UI or API exposure

---

## Inputs and Outputs

### Inputs
- `tickers` table for symbol → symbol_id resolution
- `portfolio_tickers` for watchlist membership and event triggers
- Polygon Options REST API (per-underlying options snapshot, paginated)

### Outputs
- `options_chains` TimescaleDB hypertable

Primary key:
- (time, symbol_id, expiration_date, strike_price, option_type)

Columns populated:
- time
- symbol_id
- expiration_date
- strike_price
- option_type
- bid, ask, last
- volume, open_interest
- implied_volatility
- delta, gamma, theta, vega

---

## Invariants

- Watchlist tickers only
- REST API only (no S3 / Massive)
- One snapshot_time per invocation
- Idempotent upserts; safe re-runs (no duplicates for same PK)
- Full contract-surface completeness per snapshot
- No analytical interpretation
- No historical date iteration / gap-filling

---

## Execution Flow

Shared interface:
- ingest_options_chains(symbols: list[str], snapshot_time: datetime, mode: "batch" | "event")

### Batch flow (primary)
1. Resolve all watchlist symbols from `portfolio_tickers` joined to `tickers`
2. Resolve symbol → symbol_id mappings from `tickers`
3. Assign a single snapshot_time at run start
4. For each symbol (bounded concurrency):
   - Fetch full options chain snapshot via Polygon REST (paginate using next_url)
   - Normalize all returned contracts (calls + puts, multiple expirations, full strike surface)
   - Bulk upsert into `options_chains`
5. Commit per symbol or per fixed-size chunk
6. Emit run summary (symbols attempted/succeeded/failed; rows written)

### Event-driven flow (secondary)
1. Trigger after insert(s) into `portfolio_tickers`
2. Collect all symbols added in that operation (supports multi-symbol add)
3. Assign a single snapshot_time for the invocation
4. Invoke the shared ingestion logic for the symbol list
5. Return aggregated status (per-symbol outcome)

---

## Failure Handling and Idempotency

### Failure isolation
- Failures are isolated per symbol
- API, pagination, or data-shape failures do not block other symbols

### Idempotency
- Upserts are keyed by: (time, symbol_id, expiration_date, strike_price, option_type)
- Re-running ingestion with the same snapshot_time produces no duplicates
- Different timestamps intentionally represent distinct snapshots (multiple snapshots per day are allowed if invoked)

### Explicitly excluded
- Historical date backfills (loading prior days)
- Gap-filling across missed dates
- Cross-day delta calculations (e.g., OI change)

---

## Testing Requirements

### Unit tests
- Normalize Polygon responses into `options_chains` rows
- Handle calls vs puts, multiple expirations, multiple strikes
- Tolerate missing optional fields (persist NULLs)
- Skip malformed contracts safely without aborting the symbol

### Integration tests
- Batch ingestion with multiple symbols
- Event-driven ingestion with multiple symbols
- Pagination handling (multiple pages)
- Idempotent re-run using the same snapshot_time

Out of scope for this story’s tests:
- Financial correctness of dealer/volatility metrics
- Strategy outcomes
- Performance benchmarking at production scale

---

## Operational Notes

- Manual re-runs for the same day are safe (no duplicates when snapshot_time is held constant)
- Full option-surface completeness enables downstream analytics immediately
- Logging minimum:
  - Run header (mode, snapshot_time, symbol count)
  - Per-symbol summary (pages, contracts, rows, elapsed, error)
  - Run footer (success/fail counts, total rows, elapsed)
- Use bounded concurrency and bulk upserts to protect API and DB
- Retention (90 days) is enforced by TimescaleDB policies, not code

---

## Acceptance Criteria

- [ ] Options chains fetched daily for all watchlist tickers
- [ ] Event-driven ingestion fires when one or more tickers are added
- [ ] Data persisted to `options_chains`
- [ ] Idempotent upserts (safe re-runs)
- [ ] Polygon REST API only (no S3 / Massive)
- [ ] No schema changes
- [ ] Full option-surface completeness per snapshot

END OF STORY A1