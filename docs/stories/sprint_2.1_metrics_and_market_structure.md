# Sprint 2.1 – Metrics & Market Structure Foundations

## 1. Purpose of This Document

This document is the **authoritative planning and execution artifact** for Sprint 2.1 of the KapMan Trading System.

Its goals are to:

* Lock **scope, invariants, and architectural decisions** for Sprint 2.1
* Provide durable context for future planning sessions
* Prevent re‑litigation of foundational choices
* Serve as a living reference that can be amended as the sprint progresses

This document is **not** a task tracker or backlog export. It exists above Jira/GitHub issues.

---

## 2. Sprint Objective (Canonical)

**Sprint 2.1 establishes the metrics foundation required for decisionable intelligence.**

The sprint computes, normalizes, and persists market metrics derived from:

* Daily OHLCV data
* Options chain data

These metrics are produced as **independent, reusable inputs** for downstream systems, including:

* Wyckoff event detection
* Regime classification
* Scoring and recommendations

Sprint 2.1 explicitly does **not** perform scoring, strategy selection, or trade recommendation.

Numeric configuration values for dealer metrics (e.g., DTE window size) are intentionally deferred to Sprint 2.2+, where strategy-specific and regime-specific tuning is introduced.
---

## 2.1 Executive Summary (One-Page View)

Sprint 2.1 creates the **first decision-ready layer** of the KapMan system by transforming raw market data into normalized, queryable metrics.

By the end of this sprint:

* Any newly added symbol produces usable intelligence within minutes
* Metrics are reliable, reproducible, and independently recomputable
* Downstream logic (Wyckoff, scoring, recommendations) can operate without special-case handling

This sprint deliberately favors **speed to insight** over exhaustive historical completeness while preserving a clean path to full backfill and future expansion.

---

## 3. Non‑Goals (Explicitly Out of Scope)

The following are **out of scope** for Sprint 2.1:

* Wyckoff phase/event detection logic
* Composite scoring or ranking
* Trade recommendations
* Portfolio construction
* Position sizing

These will be introduced in later sprints once metric integrity is proven.

---

## 4. Sprint Invariants (Non‑Negotiable)

### 4.1 Metric Independence

* Metrics are computed directly from raw OHLCV or options data
* Metrics are stored separately from OHLCV tables
* No metric depends on Wyckoff labels, scores, or recommendations

### 4.2 Determinism & Reproducibility

* Given identical inputs, metrics must produce identical outputs
* Lookback windows are explicit and fixed
* No look‑ahead bias is permitted

### 4.3 Temporal Correctness

* All metrics are anchored to an as‑of trading date
* Partial bars or incomplete sessions are excluded

### 4.4 Orthogonality

* Metric families are isolated and independently recomputable
* Changes to one metric family must not force recomputation of others

### 4.5 MVP Minimalism

* Only metrics with clear downstream decision value are included
* Experimental or speculative indicators are deferred

### 4.6 Event Responsiveness

* Adding a symbol must trigger metric computation immediately
* Users must not wait for nightly batches to obtain intelligence
* Only metrics with clear downstream decision value are included
* Experimental or speculative indicators are deferred

---

## 5. Metric Families (Sprint 2.1 Scope)

Sprint 2.1 is responsible for computing and persisting **foundational market-structure metrics** derived directly from raw market data. These metrics are produced as **independent, reusable inputs** for downstream systems and contain **no embedded interpretation or strategy logic**.

### 5.1 OHLCV-Derived Metrics

Metrics derived exclusively from daily OHLCV data, capturing momentum, trend strength, range, and volume-based characteristics of price behavior.

These metrics provide time-series context for downstream pattern detection and regime analysis but do not encode trading signals.

---

### 5.2 Dealer Positioning & Gamma Structure Metrics (Options-Derived)

Metrics derived from options chain data that describe dealer positioning and near-term market structure, including gamma concentration and structural price interaction levels.

These metrics characterize the options-driven forces influencing price behavior without inferring dealer intent or market direction.

---

### 5.3 Volatility Structure Metrics

Metrics describing the shape and state of implied and realized volatility across time and option moneyness.

These metrics provide volatility context for downstream regime classification and risk assessment without performing comparative scoring or normalization.

---

---

## 6. Storage Strategy (Locked)

### 6.1 Storage Model

Sprint 2.1 uses **per‑metric‑family tables**:

* `ohlcv_technical_metrics`
* `dealer_positioning_metrics`
* `volatility_metrics`

Each table:

* Uses `(symbol, date)` as a primary key
* Allows explicit NULLs
* Includes a metric version or source identifier

### 6.2 Rationale

* Preserves orthogonality
* Enables safe backfills
* Avoids schema churn
* Supports rapid iteration

---

## 7. Backfill Strategy (Hybrid)

### 7.1 Decisionable Window

When a symbol is added to a watchlist:

* Metrics are immediately computed for the **last ~252 trading days**
* This window is sufficient for Wyckoff, regime, and recommendation logic

### 7.2 Full Historical Backfill

* Full history metrics are computed asynchronously
* This process is non‑blocking
* Backfill progress does not affect MVP decisionability

---

## 8. Execution Model (Event‑Driven + Batch)

### 8.1 Event‑Driven Path

Triggered when a symbol is added:

* Compute decisionable‑window metrics immediately
* Persist results
* Emit readiness for downstream consumers

### 8.2 Batch Path

Triggered nightly:

* Compute metrics for the latest trading day
* Idempotent and resumable

### 8.3 Async Backfill Worker

* Handles historical backfills
* Operates per metric family

---

## 9. Required Spikes

### Mandatory

* Dealer metrics methodology definition
* Metric schema finalization

### Optional

* Indicator library evaluation
* Performance profiling
* Storage growth projections

---

## 9.1 Dependencies & Assumptions

### Dependencies

* Reliable daily OHLCV ingestion (Sprint 2.0.x)
* Options chain data availability via Polygon or equivalent provider
* Stable symbol/watchlist management

### Assumptions

* Daily metrics are sufficient for MVP (no intraday requirements)
* Options data gaps are acceptable and must be explicit
* Downstream systems will tolerate partial historical coverage outside the Decisionable Window

---

## 9.2 Risks & Mitigations

| Risk                 | Impact                          | Mitigation                               |
| -------------------- | ------------------------------- | ---------------------------------------- |
| Options data gaps    | Incomplete dealer metrics       | Explicit NULLs and conservative defaults |
| Schema churn         | Rework and instability          | Per-metric-family isolation              |
| Backfill performance | Delayed historical completeness | Async, chunked backfill workers          |
| Indicator ambiguity  | Inconsistent signals            | Locked formulas and versioning           |

---


## 10. Sprint Exit Criteria

Sprint 2.1 is complete when:

* Adding a symbol yields usable metrics within minutes
* Metrics update daily without manual intervention
* Downstream systems can consume metrics without special‑case logic
* Missing data is explicit and observable

---

## 11. Amendment Log

| Date | Change | Rationale |
| ---- | ------ | --------- |
|      |        |           |

---

## 12. Cross-References

* KapMan Architecture Guide (v3.1)
* KapMan Research Architecture
* Windsurf Guide

---

**Status:** ACTIVE
