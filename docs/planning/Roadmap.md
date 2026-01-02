## KapMan MVP Roadmap

Status Note (as of Jan 2026):
This roadmap reflects the original MVP execution plan. Several sections (notably Section 2 and Slice A of Section 4) are now substantially complete in implementation, even where individual FR coverage statuses have not yet been updated. This document is maintained to track remaining work, not to re-litigate completed scope.

Status Note (as of Jan 1 2026):
Slice B is now complete. Beginning Slice 3

## Purpose

This document defines the **delivery roadmap for the KapMan MVP**, grounded in
`KAPMAN_ARCHITECTURE.md`.

It exists to:
- Prove **full coverage of architectural Functional Requirements (FRs)**
- Resolve **metric scope drift introduced by spikes**
- Identify the **minimum remaining work** to achieve a runnable MVP
- Organize work into **clean, dependency-aware execution slices**

This document is **not architectural authority** and may evolve independently.

---

## 1. Requirements Traceability Matrix (RTM)

### 1.1 Functional Requirements Coverage

**Status Note:** January 2026: FR coverage statuses reflect the MVP reboot baseline. Several FRs are now fully implemented in code but not yet re-audited in this table.

| FR ID | Requirement | Coverage Status | Notes |
|------|-------------|----------------|------|
| FR-001 | Daily OHLCV load (full universe) | ⚠️ Partial | initial hydrationloader + daily + backfill utilitie|
| FR-002 | Options chains for watchlist | ❌ Missing | Schema exists; ingestion not implemented |
| FR-003 | Technical indicators computed daily | ❌ Missing | MCP dropped; local TA computation required |
| FR-004 | Dealer metrics stored | ⚠️ Partial | Schema/config only; no computation |
| FR-005 | Volatility metrics stored | ⚠️ Partial | Schema/config only; no computation |
| FR-006 | Price metrics stored | ❌ Missing | RVOL/VSI/HV not implemented |
| FR-007 | Wyckoff phase A–E stored | ⚠️ Partial | Research only; no prod persistence |
| FR-008 | 8 Wyckoff events stored | ⚠️ Partial | Benchmark code not wired to pipeline |
| FR-009 | Recommendations persisted | ⚠️ Partial | Claude provider exists; no persistence |
| FR-010 | Real strikes only | ❌ Missing | Requires options ingestion + validation |
| FR-011 | Portfolio CRUD | ⚠️ Partial | Schema only |
| FR-012 | Dashboard displays recommendations | ❌ Missing | UI stub only |
| FR-013 | Directional accuracy (Brier) | ❌ Missing | Outcome schema only |
| FR-014 | Alert on BC ≥ 24 | ❌ Missing | No rule engine |
| FR-015 | Alert on SPRING + SOS | ❌ Missing | No rule engine |
| FR-016 | ≥80% test coverage | ⚠️ Policy only | No enforcement |
| FR-017 | dev/test/prod environments | ⚠️ Partial | Single compose stack only |

---

## 2. Metric Scope & Schema Policy (Resolved)

**Status Note:** January 2026 Metric scope and schema commitments in this section are complete and in force, with the sole remaining implementation work being Wyckoff metrics (Section 4, Slice B).

### 2.1 MVP Metric Commitment (Authoritative)

For MVP, the system **must compute and persist** the following metrics:

**Technical (Core)**
- RSI
- MACD (line/signal/histogram)
- SMA / EMA (key periods)

**Price**
- RVOL
- VSI
- Historical Volatility (HV)

**Dealer**
- Total GEX
- Net GEX
- Gamma flip level
- Primary call wall
- Primary put wall

**Volatility**
- Average IV
- IV Rank
- Put/Call ratio (OI-based)

**Wyckoff**

Wyckoff Role in kapman-trader MVP
Wyckoff analytics in KapMan provide structural market context, not trade signals. The Wyckoff pipeline is responsible for detecting and persisting market regime, event structure, and confidence metadata derived from price–volume behavior. These outputs are consumed by downstream layers (options selection, sizing, alerts, evaluation) but do not encode entry, exit, or expression logic.

- Phase (A–E) + confidence
- 8 critical events
- BC / Spring scores

These metrics are **first-class** and must exist as columns and/or JSON fields
in `daily_snapshots`.

---

### 2.2 Extended Metric Context (Explicitly Allowed)

Although the **schema is locked**, the system explicitly allows:

- Computing **additional technical indicators** beyond MVP
- Storing them in:
  - `technical_indicators_json`
  - `price_metrics_json`
  - `dealer_metrics_json`
  - `volatility_metrics_json`

These extended metrics:
- Are **non-contractual**
- Are **not required for MVP completion**
- May will passed to Claude as **contextual input** for interpretation

This preserves:
- MVP discipline
- Schema stability
- Future analytical richness

No schema changes are required to support this.

---

## 3. Canonical Gap Stories (Original Plan: see status notes)

**Status Note:** 

January 2026: Many stories listed below have been fully or partially implemented since this roadmap was drafted. Stories without an explicit “COMPLETE” annotation should be treated as remaining gaps; completed stories are retained for traceability.

This is the **minimum set of stories** required to close all FR gaps.
Every roadmap story MUST reference one or more GitHub issue IDs in its title or description.

### Data & Metrics

**Status Note:** 

January 2026: COMPLETE (superseded by implemented ingestion + metric pipelines)

- **S-INF-00** - Deterministic database rebuild and baseline validation → *Issue ID: A5*
- **S-INF-01** - Wipe DB and establish MVP schema baseline → *Issue ID: A6*
- **S-DS-01** — OHLCV backfill (universe) → *Closes FR-001* → *Issue ID: A0*
- **S-WL-01** — Persist MVP Watchlist → *Issue ID: A7*
- **S-OPT-02** — Options ingestion (watchlist → `options_chains`) → *Closes FR-002* → *Issue ID: A1*
- **S-MET-01** — Dealer metric computation/persistence → *Closes FR-004* → *Issue ID: A3
- **S-MET-02** — Volatility metric computation/persistence → *Closes FR-005* → *Issue ID: A4*
- **S-MET-03** — Local TA + price metric computation (RSI/MACD/SMA/EMA + RVOL/VSI/HV) → *Closes FR-003, FR-006* → *Issue ID: A2*

### Wyckoff

**Status Note:**  
January 2026: ACTIVE (current focus)

- **S-WYC-01** — Persist Daily Wyckoff Regime State
For each symbol and trading day, compute and persist a single Wyckoff regime classification (e.g., Accumulation, Markup, Distribution, Markdown, Unknown) along with confidence metadata. Regime assignment must be deterministic, path-dependent, and stable in the absence of regime-setting events.     → *Closes FR-007* → *Issue ID: B1*

- **S-WYC-02** — Persist Canonical Wyckoff Events
Detect and persist canonical Wyckoff structural events (SC, BC, AR, AR_TOP, SPRING, UT, SOS, SOW) with event date, type, and validation metadata. Events are sparse, path-dependent, and may only occur once per symbol per structural phase. Event detection logic must conform to the research-validated benchmark behavior.   → *Closes FR-008* → *Issue ID: B2*

### Recommendations
- **S-AI-01** - Deterministic AIinterface & contract → *Closes FR-09* → *Issue ID: C1*
- **S-REC-02** — Strike/expiration validator (real strikes only) → *Closes FR-010* → *Issue ID: C3*
- **S-REC-01** — Recommendation persistence (AI output) → *Closes FR-009* → *Issue ID: C2*

### Feedback Loop
- **S-FB-01** — Outcome evaluation (+5/+10/+20 days) → *Closes FR-013* → *Issue ID: D1*
- **S-FB-02** — Weekly statistical score computation → *Closes FR-013* → *Issue ID: D2*

### Product Surface
- **S-PORT-01** — Portfolio CRUD API → *Closes FR-011* → *Issue ID: E1*
- **S-UI-01** — Minimal dashboard (recs + BC/Spring alerts) → *Closes FR-012, FR-014, FR-015* → *Issue ID: E2*

### Quality & Ops
- **S-QA-01** — Coverage gate enforcement → *Closes FR-016* → *Issue ID: E3*
- **S-ENV-01** — dev/test/prod promotion workflow → *Closes FR-017* → *Issue ID: E4*

---

## 4. Dependency-Aware Execution Slices

Execution is organized by **blocking reality**, not subsystem purity.

#### Slice A — Data Ingress & Core Analytics

Execution is organized by blocking reality, not subsystem purity.

- S-INF-01
- S-INF-00
- S-DS-01
- **S-WL-01**  ← NEW
- S-OPT-02
- S-MET-01
- S-MET-02
- S-MET-03

Outcome: `daily_snapshots` fully populated with real metrics.

**Status Note:** 

January 2026: COMPLETE (additional stories added opportunistically and tracked outside this roadmap in github issues)
---

### Slice B — Wyckoff Structural Context (ACTIVE)

**Status Note:** January 2026: Research complete; production implementation in progress

- S-WYC-01
- S-WYC-02

**Outcome:** Research-grade Wyckoff logic operating in daily pipeline.
**Out of Scope for This Slice**
- Explicit event sequence labeling (e.g., SC→AR→SPRING→SOS)
- Regime transition scoring or prediction
- Trade entry, exit, or sizing logic
These capabilities are research-validated but intentionally deferred to later slices to preserve separation between structural context and decision logic.

---

### Slice C — Recommendation Integrity
- S-AI-01 
- S-REC-02
- S-REC-01

**Outcome:** Trustworthy, persisted recommendations.

---

### Slice D — Feedback & Scoring
- S-FB-01
- S-FB-02

**Outcome:** Measurable signal quality.

---

### Slice E — Product, Quality, Ops
- S-PORT-01
- S-UI-01
- S-QA-01
- S-ENV-01

**Outcome:** Usable, testable MVP.

---

## 5. MVP Definition of Done

The MVP is complete when:

- All FR-001 → FR-017 are closed
- Daily pipeline runs end-to-end locally
- Recommendations are persisted and scored
- Alerts surface correctly
- Dashboard renders core outputs
- Test coverage ≥80% is enforced
- No schema changes are required to add new metrics for Claude context

At that point, KapMan is a **true decision-support system**, not a demo.

---
## 6.Ownership Invariants

- A6 owns schema truth.
- A0 owns canonical ingestion logic.
- No story other than A0 may modify ingestion behavior.
- Later stories may invoke ingestion entrypoints only.