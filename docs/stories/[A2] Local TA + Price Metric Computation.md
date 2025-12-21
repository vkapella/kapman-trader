[A2] Local TA + Price Metric Computation

Roadmap: S-MET-03
Closes: FR-003, FR-006
Issue ID: A2
Scope Type: Batch-only, deterministic, re-runnable
Persistence: Postgres/TimescaleDB (daily_snapshots)

⸻

PHASE 1 — Story Framing & Intent Validation

Why this issue exists

KapMan MVP requires a local, deterministic computation layer that derives a comprehensive technical indicator surface and core price-derived metrics directly from persisted OHLCV. These outputs are the analytical substrate for downstream Wyckoff interpretation and recommendation generation.

What this issue explicitly delivers
	•	Local computation (pandas + ta + TA-Lib candlestick functions) from KapMan DB ohlcv
	•	Full technical indicator surface (as defined by the authoritative registry sample) plus explicit SMA variants (14/20/50/200)
	•	Pattern recognition (candlestick) indicators in a new category
	•	Price metrics RVOL/VSI/HV
	•	Persistence into daily_snapshots JSONB blobs with deterministic keys and nullability
	•	Deterministic, idempotent reruns keyed by (time, ticker_id)

What this issue explicitly does NOT do
	•	No Wyckoff phase detection, event detection, or scoring
	•	No dealer/options/volatility-term-structure metrics
	•	No API/UI exposure
	•	No schema changes (unless later required by implementation defects)
	•	No event-driven execution, no background schedulers, no incremental rollups

⸻

PHASE 2 — Inputs, Outputs, and Invariants

Tables read
	•	tickers
	•	id, is_active
	•	ohlcv (hypertable)
	•	ticker_id, date, open, high, low, close, volume

Tables written
	•	daily_snapshots
	•	Primary key: (time, ticker_id)
	•	Columns set/overwritten by A2:
	•	technical_indicators_json
	•	price_metrics_json
	•	model_version
	•	created_at

External libraries
	•	pandas
	•	ta (technical analysis library)
	•	TA-Lib candlestick pattern functions (for pattern recognition category)

Invariants
	1.	Determinism: Same OHLCV slice ⇒ identical metric outputs.
	2.	Idempotency: Upsert on (time, ticker_id); no duplicates; safe reruns.
	3.	Isolation: All metrics derived only from persisted ohlcv. No S3/MCP/API reads.
	4.	Completeness: All keys in the locked contract exist; missing/insufficient data ⇒ NULL not omission.
	5.	Snapshot time: daily_snapshots.time is derived from ohlcv.date normalized to midnight (date-based snapshot, not runtime timestamp).
	6.	Watchlist scope: Only tickers.is_active = TRUE.

⸻

PHASE 2A — Metric Surface Lock

Classification rules (locked)
	•	Any metric computed via ta / TA-Lib indicator functions ⇒ technical_indicators_json
	•	Pure price/volume math (local) ⇒ price_metrics_json
	•	All keys must exist; values numeric/int or NULL

Technical indicator surface (technical_indicators_json)

Top-level categories:
	•	momentum
	•	trend
	•	volatility
	•	volume
	•	others
	•	pattern_recognition

SMA variants (explicit, required)
SMA is represented as explicit variants computed from close:
	•	technical_indicators_json["trend"]["sma"]["sma_14"]
	•	technical_indicators_json["trend"]["sma"]["sma_20"]
	•	technical_indicators_json["trend"]["sma"]["sma_50"]
	•	technical_indicators_json["trend"]["sma"]["sma_200"]

All four keys must exist; values numeric or NULL.

Full ta surface (authoritative from provided sample)
The story implements the full indicator set described in the authoritative sample registry (momentum, volatility, trend, volume, others) using their required inputs and default params, emitting the outputs listed per indicator. Missing prerequisites or failures result in NULL values for that indicator’s outputs.

Pattern recognition (pattern_recognition) — TA-Lib candlestick patterns (integer outputs)
New category stored under technical_indicators_json["pattern_recognition"], with integer outputs:
	•	cdl2crows
	•	cdl3blackcrows
	•	cdl3inside
	•	cdl3linestrike
	•	cdl3outside
	•	cdl3starsinsouth
	•	cdl3whitesoldiers
	•	cdlabandonedbaby
	•	cdladvanceblock
	•	cdlbelthold
	•	cdlbreakaway
	•	cdlclosingmarubozu
	•	cdlconcealbabyswall
	•	cdlcounterattack
	•	cdldarkcloudcover
	•	cdldoji
	•	cdldojistar
	•	cdldragonflydoji
	•	cdlengulfing
	•	cdleveningdojistar
	•	cdleveningstar
	•	cdlgapsidesidewhite
	•	cdlgravestonedoji
	•	cdlhammer
	•	cdlhangingman
	•	cdlharami
	•	cdlharamicross
	•	cdlhighwave
	•	cdlhikkake
	•	cdlhikkakemod
	•	cdlhomingpigeon
	•	cdlidentical3crows
	•	cdlinneck
	•	cdlinvertedhammer
	•	cdlkicking
	•	cdlkickingbylength
	•	cdlladderbottom
	•	cdllongleggeddoji
	•	cdllongline
	•	cdlmarubozu
	•	cdlmatchinglow
	•	cdlmathold
	•	cdlmorningdojistar
	•	cdlmorningstar
	•	cdlonneck
	•	cdlpiercing
	•	cdlrickshawman
	•	cdlrisefall3methods
	•	cdlseparatinglines
	•	cdlshootingstar
	•	cdlshortline
	•	cdlspinningtop
	•	cdlstalledpattern
	•	cdlsticksandwich
	•	cdltakuri
	•	cdltasumikgap
	•	cdlthrusting
	•	cdltristar
	•	cdlunique3river
	•	cdlupsidegap2crows
	•	cdlxsidegap3methods

Semantics:
	•	Integer values per TA-Lib convention (>0, <0, 0), or NULL if not computable.
	•	No interpretation or filtering in A2.

Price metric surface (price_metrics_json)
	•	rvol
	•	vsi
	•	hv

All keys must exist; values numeric or NULL. Window definitions must be deterministic and versioned via model_version.

⸻

PHASE 3 — Data Flow & Control Flow

Execution model
	•	Batch job, invoked explicitly (CLI-style entrypoint)
	•	Runs for:
	•	a single snapshot date, or
	•	a date range, or
	•	all missing snapshot dates

Step-by-step flow
	1.	Establish run context
	•	Determine model_version (static string for A2)
	•	Determine run_timestamp (for created_at only)
	2.	Resolve snapshot dates
	•	Use provided date/date-range or “fill missing” logic
	•	Normalize:
	•	snapshot_time = snapshot_date at 00:00:00 (timezone-consistent)
	3.	Resolve eligible tickers
	•	Query tickers where is_active = TRUE
	•	Produce stable list of ticker_ids
	4.	For each (snapshot_date, ticker_id)
	•	Query full OHLCV history:
	•	ohlcv where ticker_id = ? AND date <= snapshot_date
	•	order by date ASC
	•	Load into DataFrame with required columns
	5.	Compute technical indicator surface
	•	Compute full ta registry indicators (per PHASE 2A)
	•	Compute SMA variants explicitly: 14/20/50/200
	•	Compute TA-Lib candlestick patterns into pattern_recognition
	•	For each indicator output:
	•	extract latest value only
	•	coerce to Python scalar
	•	if not computable ⇒ NULL
	6.	Compute price metrics
	•	Compute RVOL, VSI, HV from OHLCV history deterministically
	•	extract latest value only
	•	coerce to Python scalar or NULL
	7.	Assemble snapshot payload
	•	time = snapshot_time
	•	ticker_id
	•	technical_indicators_json
	•	price_metrics_json
	•	model_version
	•	created_at = run_timestamp
	8.	Persist with idempotent upsert
	•	INSERT ... ON CONFLICT (time, ticker_id) DO UPDATE
	•	Overwrite JSON blobs + model_version + created_at
	•	No deletes

Control/batch boundaries
	•	Outer loop: snapshot dates
	•	Inner loop: active tickers
	•	Failure isolation: indicator-level errors do not abort ticker/date; DB errors abort run

⸻

PHASE 4 — Failure Modes & Idempotency

Failure modes and handling
	•	No OHLCV history for ticker/date
	•	Skip row; log WARN
	•	Insufficient history for windows (e.g., SMA200)
	•	Persist row with NULL values for affected keys
	•	Per-indicator compute errors
	•	Catch; set outputs to NULL; log WARN; continue
	•	Non-finite outputs (NaN/inf)
	•	Coerce to NULL
	•	DB read/write errors
	•	Abort run (fatal)
	•	JSON serialization errors
	•	Must be prevented by coercion; if still occurs, abort run (fatal)

Idempotency contract
	•	Key: (time, ticker_id)
	•	time derived from OHLCV trading date at midnight
	•	Safe reruns and backfills; re-running overwrites deterministically

⸻

PHASE 5 — Testing Strategy

All tests live under tests/ and run via default pytest.

Unit tests (tests/unit/metrics/)
	•	Validate JSON shape and required keys exist (not full numeric correctness)
	•	Validate SMA variant keys exist and are numeric/NULL
	•	Validate pattern_recognition keys exist and are int/NULL
	•	Validate insufficient history yields NULL for long windows without exceptions

Integration tests (tests/integration/)
	•	Seed DB with:
	•	1 active ticker
	•	≥ 260 OHLCV rows for SMA200 coverage
	•	Run A2 for the last OHLCV date
	•	Assert:
	•	daily_snapshots row exists
	•	JSON columns non-null
	•	required top-level categories exist
	•	SMA keys exist
	•	price metric keys exist
	•	Rerun same date:
	•	row count remains 1
	•	metrics JSON unchanged (created_at may change)

(If indicator-failure patching is brittle for integration tests, drop it and rely on unit tests for exception handling.)

⸻

PHASE 6 — Operational Considerations

Reruns/backfills
	•	Supports single date, date range, and “fill missing”
	•	Backfills may be slow; correctness prioritized

Logging
	•	INFO: start/end, dates, ticker counts
	•	WARN: missing data, per-indicator failures
	•	ERROR: DB failures, fatal serialization failures

Performance assumptions
	•	Watchlist scale is acceptable with per-ticker full-history DataFrame loads
	•	Optimization (parallelism/incremental state) explicitly deferred

⸻

PHASE 7 — Final Story Artifact Notes

Acceptance Criteria (from issue)
	•	TA metrics computed locally from OHLCV (full surface + SMA variants)
	•	Price metrics RVOL/VSI/HV computed locally
	•	Results persisted to daily_snapshots
	•	Deterministic and re-runnable execution

Appendix A — Technical Indicator Implementation Reference (Authoritative)

The full technical-indicator surface for A2 is defined by the module:

docs/reference/ta_indicator_surface.py

This file:
	•	Enumerates all supported indicators
	•	Defines required inputs, outputs, and default parameters
	•	Is the authoritative implementation reference for A2

The A2 job must compute all indicators defined in this file and persist their latest values into technical_indicators_json, preserving category and key names exactly.

Changes to the indicator surface require updating this file and bumping model_version.
⸻
