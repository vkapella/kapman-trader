## KapMan MVP Roadmap

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

## 3. Canonical Gap Stories (MVP Completion Set)

This is the **minimum set of stories** required to close all FR gaps.
Every roadmap story MUST reference one or more GitHub issue IDs in its title or description.

### Data & Metrics
- **S-INF-00** - Deterministic database rebuild and baseline validation → *Issue ID: A5*
- **S-INF-01** - Wipe DB and establish MVP schema baseline → *Issue ID: A6*
- **S-DS-01** — OHLCV backfill (universe) → *Closes FR-001* → *Issue ID: A0*
- **S-OPT-02** — Options ingestion (watchlist → `options_chains`) → *Closes FR-002* → *Issue ID: A1*
- **S-MET-01** — Dealer metric computation/persistence → *Closes FR-004* → *Issue ID: A3
- **S-MET-02** — Volatility metric computation/persistence → *Closes FR-005* → *Issue ID: A4*
- **S-MET-03** — Local TA + price metric computation (RSI/MACD/SMA/EMA + RVOL/VSI/HV) → *Closes FR-003, FR-006* → *Issue ID: A2*

### Wyckoff
- **S-WYC-01** — Persist daily Wyckoff phase + confidence → *Closes FR-007* → *Issue ID: B1*
- **S-WYC-02** — Persist 8 Wyckoff events with benchmark assertion → *Closes FR-008* → *Issue ID: B2*

### Recommendations
- **S-AI-01** - Deterministic Claude interface & contract → *Closes FR-09* → *Issue ID: C3*
- **S-REC-02** — Strike/expiration validator (real strikes only) → *Closes FR-010* → *Issue ID: C1*
- **S-REC-01** — Recommendation persistence (Claude output) → *Closes FR-009* → *Issue ID: C2*

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

### Slice A — Data Ingress & Core Analytics

- S-INF-01
- S-INF-00
- S-DS-01
- S-OPT-02
- S-MET-01
- S-MET-02
- S-MET-03

**Outcome:** `daily_snapshots` fully populated with real metrics.

---

### Slice B — Wyckoff in Production
- S-WYC-01
- S-WYC-02

**Outcome:** Research-grade Wyckoff logic operating in daily pipeline.

---

### Slice C — Recommendation Integrity
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
