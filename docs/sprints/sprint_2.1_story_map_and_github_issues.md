Sprint 2.1 – Story Map & GitHub Issues

This document translates Sprint 2.1 – Metrics & Market Structure Foundations into an executable story map and a copy/paste–ready GitHub issue set.

It is the only execution artifact for Sprint 2.1. Architecture, invariants, and scope are defined in the Sprint 2.1 planning document and are not restated here.

⸻

1. Sprint 2.1 Story Order (Canonical)

Execution order is intentional and must not be reordered without amending the Sprint 2.1 planning artifact.
	1.	SPIKE 2.1.A – Dealer Metrics Methodology
	2.	SPIKE 2.1.B – Metric Schemas & Versioning
	3.	STORY 2.1.1 – Metric Engine Scaffold
	4.	STORY 2.1.2 – OHLCV Technical Metrics (Event-Driven)
	5.	STORY 2.1.3 – OHLCV Technical Metrics (Batch)
	6.	STORY 2.1.4 – Volatility Metrics (Event + Batch)
	7.	STORY 2.1.5 – Dealer / Positioning Metrics (MVP)
	8.	STORY 2.1.6 – Async Historical Backfill Worker

⸻

2. GitHub-Flavored Sprint Checklist

- [ ] SPIKE 2.1.A – Dealer Metrics Methodology
- [ ] SPIKE 2.1.B – Metric Schemas & Versioning
- [ ] STORY 2.1.1 – Metric Engine Scaffold
- [ ] STORY 2.1.2 – OHLCV Technical Metrics (Event-Driven)
- [ ] STORY 2.1.3 – OHLCV Technical Metrics (Batch)
- [ ] STORY 2.1.4 – Volatility Metrics (Event + Batch)
- [ ] STORY 2.1.5 – Dealer / Positioning Metrics (MVP)
- [ ] STORY 2.1.6 – Async Historical Backfill Worker


⸻

3. Copy/Paste–Ready GitHub Issues

Each section below is intended to be copied directly into a GitHub issue.

Each issue now includes:
	•	Suggested labels for GitHub
	•	Estimated complexity (S / M / L)
	•	Explicit dependencies to prevent mis-ordering

⸻

SPIKE 2.1.A – Dealer Metrics Methodology

Suggested Labels: spike, options, market-structure, sprint-2.1
Estimated Complexity: M
Dependencies: None

Objective
Define conservative, explicit, and explainable methodologies for dealer positioning metrics used in Sprint 2.1.

Scope
	•	Define GEX calculation (inputs, aggregation, expirations)
	•	Define gamma flip level methodology
	•	Define call wall / put wall identification
	•	Document assumptions and limitations

Out of Scope
	•	Intraday dealer metrics
	•	Strategy-specific interpretations

Acceptance Criteria
	•	Written methodology committed to /docs/research/
	•	All formulas and assumptions explicit
	•	No production code written

⸻

SPIKE 2.1.B – Metric Schemas & Versioning

Suggested Labels: spike, schema, metrics, sprint-2.1
Estimated Complexity: S
Dependencies: None

Objective
Finalize schemas for Sprint 2.1 metric storage to prevent rework and coupling.

Scope
	•	Define schemas for:
	•	ohlcv_technical_metrics
	•	volatility_metrics
	•	dealer_positioning_metrics
	•	Define primary keys and nullability
	•	Define metric versioning approach

Acceptance Criteria
	•	Schemas reviewed and approved
	•	Versioning approach documented
	•	No downstream dependencies assumed

⸻

STORY 2.1.1 – Metric Engine Scaffold

Suggested Labels: infra, metrics, event-driven, batch, sprint-2.1
Estimated Complexity: M
Dependencies: SPIKE 2.1.B

Objective
Create a shared execution framework supporting event-driven and batch metric computation.

Scope
	•	Event listener for symbol addition
	•	Batch execution interface
	•	Shared utilities for:
	•	Lookback windows
	•	Idempotent upserts
	•	Logging

Acceptance Criteria
	•	Same code path supports event and batch execution
	•	Dry-run metric computation succeeds

⸻

STORY 2.1.2 – OHLCV Technical Metrics (Event-Driven)

Suggested Labels: metrics, ohlcv, event-driven, technical-indicators, sprint-2.1
Estimated Complexity: M
Dependencies: STORY 2.1.1

Objective
Provide immediate, decisionable technical metrics when a symbol is added.

Scope
	•	Fetch last ~252 trading days of OHLCV
	•	Compute RSI, MACD, ADX, OBV, ATR
	•	Persist to ohlcv_technical_metrics

Acceptance Criteria
	•	Metrics available within minutes of symbol addition
	•	Values validated against known references (e.g., SPY)
	•	Missing data explicit

⸻

STORY 2.1.3 – OHLCV Technical Metrics (Batch)

Suggested Labels: metrics, ohlcv, batch, technical-indicators, sprint-2.1
Estimated Complexity: S
Dependencies: STORY 2.1.2

Objective
Ensure stable, idempotent daily updates of technical metrics.

Scope
	•	Nightly batch job
	•	Compute metrics for latest trading day only
	•	Upsert without duplication

Acceptance Criteria
	•	Re-running batch produces identical results
	•	Event-driven and batch outputs match

⸻

STORY 2.1.4 – Volatility Metrics (Event + Batch)

Suggested Labels: metrics, volatility, options, event-driven, batch, sprint-2.1
Estimated Complexity: M
Dependencies: STORY 2.1.2

Objective
Introduce volatility awareness for regime detection and risk context.

Scope
	•	Historical volatility from OHLCV
	•	ATM IV from options data
	•	IV/HV ratios and basic term structure

Acceptance Criteria
	•	Metrics populate where options exist
	•	Explicit NULLs where unavailable
	•	No dependency on dealer logic

⸻

STORY 2.1.5 – Dealer / Positioning Metrics (MVP)

Suggested Labels: metrics, options, dealer, market-structure, sprint-2.1
Estimated Complexity: L
Dependencies: SPIKE 2.1.A, STORY 2.1.1

Objective
Expose conservative market structure signals from options positioning.

Scope
	•	Aggregate GEX
	•	Gamma flip price
	•	Call and put walls (top N)

Acceptance Criteria
	•	Methodology matches SPIKE 2.1.A definitions
	•	No intraday assumptions
	•	Metrics persisted independently

⸻

STORY 2.1.6 – Async Historical Backfill Worker

Suggested Labels: infra, backfill, async, metrics, sprint-2.1
Estimated Complexity: M
Dependencies: STORY 2.1.1

Objective
Enable full historical completeness without blocking MVP workflows.

Scope
	•	Background backfill worker
	•	Chunked processing
	•	Per-metric-family isolation

Acceptance Criteria
	•	Backfill resumable and non-blocking
	•	Failures isolated to affected metric family

⸻

4. Sprint Completion Checklist

Sprint 2.1 is complete when:
	•	All stories above are complete
	•	Metrics are available within minutes for new symbols
	•	Daily batch updates run without manual intervention
	•	Downstream systems consume metrics without special cases

⸻

Status: ACTIVE