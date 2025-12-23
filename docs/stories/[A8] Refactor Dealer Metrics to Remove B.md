[A8] Refactor Dealer Metrics to Remove Bid/Ask Dependencies (Pricing Optional)

Owner: @vkapella
Roadmap Reference: S-MET-03 (new) / supports S-MET-02 pipelines
Dependencies: A1 Options ingestion, A3 Dealer metrics job, A4 Volatility metrics job
Status: Proposed

Summary

Refactor the dealer metrics computation pipeline to eliminate any dependency on option bid/ask pricing. Bid/ask columns may remain in the schema and be populated as NULLs. Dealer metrics must compute deterministically using pricing-free inputs (OI, gamma, strike, DTE, option type, spot), while treating pricing fields as optional enrichment only.

Why This Exists
	•	Current dealer calculations (and/or filters) implicitly assume bid/ask is available, which is not reliably provided by Polygon/Massive and increases cost/latency when using Unicorn.
	•	Pipeline reliability is degraded on high-surface symbols; pricing requirements amplify failure modes without materially improving Wyckoff-context signals.
	•	KapMan dealer signals are intended as structural context; pricing is not required for the core outputs (GEX, walls, flip, regime).

Explicit Deliverables
	1.	A3 dealer-metrics job runs successfully when options_chains.bid/ask are NULL for all rows.
	2.	Any spread-based filtering becomes conditional: applied only when bid/ask is present; otherwise it is skipped and logged at DEBUG (not WARN/ERROR).
	3.	Dealer-metrics JSON output remains stable and auditable; add explicit metadata to indicate whether pricing data was available for the computation.
	4.	Existing schema is unchanged; NULL bid/ask is accepted and does not block ingestion or computation.

Explicit Non-Goals
	•	No Black-Scholes pricing or implied mid reconstruction.
	•	No new provider integrations or ingestion refactors beyond removing bid/ask dependency.
	•	No change to the definition of GEX/walls/flip that would require option pricing.

⸻

Inputs, Outputs, and Invariants

Tables Read
	•	public.watchlists (active symbols)
	•	public.tickers (symbol -> ticker_id)
	•	public.options_chains (contract rows for symbol at effective snapshot_time)
	•	public.ohlcv (or equivalent spot fallback used by A3 today)
	•	public.daily_snapshots (existing row for date/ticker_id if using upsert semantics)

Tables Written
	•	public.daily_snapshots.dealer_metrics_json (JSONB upsert by (time, ticker_id) as implemented by A3)

External Services
	•	None (A8 is compute-only; ingestion remains owned by A1)

Invariants / Constraints
	•	Deterministic: same (snapshot_time, DB state, params) yields identical outputs.
	•	Idempotent: safe re-runs for same snapshot_time/date.
	•	Bid/ask optional: NULL pricing must never cause A3 to fail or mark ticker INVALID by itself.
	•	Spread filter: if applied, must be deterministic and must never require pricing. If pricing missing, it is a no-op.

⸻

Data Flow & Control Flow (A3 changes only)

For each symbol in active watchlists:
	1.	Resolve ticker_id; if missing, mark INVALID with failure_reason=ticker_id_missing (existing behavior).
	2.	Resolve effective options snapshot time (<= snapshot_time) and load option rows.
	3.	Resolve spot (existing strategy).
	4.	Build in-memory contract objects (pricing fields optional).
	5.	Apply contract eligibility filters:
	•	max_dte_days, min_open_interest, min_volume (unchanged)
	•	max_spread_pct: apply ONLY if bid and ask are present and valid; otherwise skip
	6.	Compute pricing-free metrics:
	•	strike_gex, gex_total, gex_net, gamma_flip, walls, gex_slope, dgpi, position, confidence (unchanged math)
	7.	Persist dealer_metrics_json with:
	•	results
	•	eligibility counts
	•	filter stats
	•	diagnostics
	•	new metadata flags:
	•	pricing_available: boolean (any eligible contract has both bid and ask)
	•	spread_filter_applied: boolean
	8.	Log summary at start/end (existing A3 conventions).

⸻

Failure Modes & Idempotency

Expected Failures (Non-fatal per ticker)
	•	Missing ticker_id (watchlist symbol not present in tickers) -> INVALID + failure_reason
	•	Missing options rows for resolved snapshot_time -> INVALID + failure_reason=no_options_available
	•	Missing spot -> INVALID + diagnostics=missing_spot_price
	•	Missing bid/ask -> NOT a failure; spread filter is skipped; metrics computed as normal

Retry Behavior
	•	A3 should continue processing other tickers after per-ticker failures.
	•	A8 does not add any new retry loops; existing A3 behavior stands.

Idempotent Write Strategy
	•	Continue using the current A3 upsert strategy into daily_snapshots keyed by (time, ticker_id).
	•	When re-running, the computed dealer_metrics_json overwrites prior values for the same key.

⸻

Testing Strategy

Unit Tests (tests/unit/dealer_metrics/)

Add/adjust tests to validate pricing-free behavior:
	1.	test_spread_filter_skipped_when_pricing_missing
	•	contracts with bid=None/ask=None must not be filtered by spread logic
	2.	test_spread_filter_applied_when_pricing_present
	•	contracts with bid/ask that imply wide spread are filtered deterministically
	3.	test_metrics_compute_with_null_bid_ask
	•	ensure compute returns expected non-null gex_total/gex_net given valid gamma/OI/spot
	4.	test_json_metadata_pricing_available_flags
	•	pricing_available false when all eligible contracts lack bid/ask

Tests must be runnable via default pytest invocation with no special flags.

Integration Tests (tests/integration/)

Optional minimal integration coverage (only if existing harness supports it):
	•	Run A3 against a fixture dataset where options_chains has NULL bid/ask and verify daily_snapshots row is produced.

If integration harness is not stable, reduce scope to unit tests only.

⸻

Operational Considerations
	•	Logging:
	•	No stdout prints; use existing logging framework.
	•	When pricing missing: DEBUG log once per ticker (“spread filter skipped: pricing missing”).
	•	Do not WARN/ERROR for missing bid/ask.
	•	Performance:
	•	Removing pricing requirements should reduce ingestion coupling and improve compute success rate.

⸻

Acceptance Criteria
	•	A3 job completes on a dataset where options_chains.bid and options_chains.ask are NULL for all rows, and produces dealer_metrics_json for eligible tickers.
	•	Spread filter does not run (and does not block) when bid/ask are absent; does run when present.
	•	Dealer metrics outputs (gex_total, gex_net, walls, flip, position, confidence) remain populated when other eligibility conditions are met.
	•	New metadata flags are present and correct: pricing_available and spread_filter_applied.
	•	Unit tests added/updated and passing under default pytest.

⸻

Implementation Notes (Developer Checklist)
	•	Ensure any code paths that compute spread_pct handle None safely.
	•	Avoid introducing new schema changes; NULLs are acceptable.
	•	Keep defaults consistent with existing A3 CLI flags and config (max_spread_pct remains configurable but becomes conditional).