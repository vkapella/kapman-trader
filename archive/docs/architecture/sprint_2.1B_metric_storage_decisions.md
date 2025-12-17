# File: docs/architecture/sprint_2.1B_metric_storage_decisions.md

# SPIKE 2.1.B — Metric Schema & Storage Design Decisions (Locked)

## Purpose
This document is the authoritative record of the design decisions (the “wizard”) that govern Sprint 2.1.B database schemas and storage contracts for KapMan Trading System. It is intentionally free of scoring, ranking, regime, or strategy logic.

If a future change requires violating any decision below, it MUST be treated as a schema version bump (new migrations + updated tests + updated config contracts).

---

## Inputs (Authoritative References)
- Sprint 2.1 planning document: scope, invariants, execution constraints
- Dealer Metrics Methodology: authoritative dealer/option metric contracts

---

## Non-Goals (Explicit Exclusions)
The Sprint 2.1.B storage layer MUST NOT:
- Introduce new metrics beyond those implied by the authoritative documents
- Hard-code numeric parameters (e.g., DTE values, windows, thresholds) in tables, columns, views, or code defaults
- Encode scoring, ranking, signal generation, regime detection, or interpretation logic
- Collapse “missing” into “0” (NULL must remain first-class)
- Require synchronous full backfills to operate (must support async backfill)

---

## Global Storage Invariants (All Metric Families)
All metric-family schemas and writes MUST satisfy:
1. Deterministic & reproducible outputs
   - Derived metrics must bind to explicit algorithm identity and configuration identity.
2. Orthogonality across metric families
   - No metric-family table should embed another family’s interpretation or decision logic.
3. Explicit NULLs and versioning
   - NULL is first-class and must not be coerced to 0 or inferred.
4. Support event-driven hydration + batch updates + async backfill
   - Storage contracts must support each mode without destructive overwrites that lose provenance.
5. Idempotent recomputation
   - Primary keys define idempotency; re-runs overwrite by PK only (not append new versions unless input identities differ).

---

## Locked Wizard Decisions

### Decision 1 — OHLCV Canonicality
**Selected: Option B — Multi-source / versioned OHLCV**

Meaning:
- OHLCV is treated as a versioned dataset (input artifact), not a single mutable “truth.”
- Multiple OHLCV rows may coexist for the same (symbol, trading_date) distinguished by source identity.
- Canonicalization (if needed for ergonomics) is performed via explicit views or downstream selection, not by overwriting stored facts.

Implications:
- `source_version` participates in the OHLCV primary key.
- Backfills are additive for OHLCV (new `source_version`), not destructive overwrites of prior provenance.

---

### Decision 2 — Volatility Family Boundary
**Selected: Option B — Split realized vs implied**

Meaning:
- Realized volatility outputs (derived from OHLCV) and implied volatility outputs (derived from options surfaces) are stored in separate tables.
- This enforces orthogonality and provenance separation.

---

### Decision 3 — Dealer Metric Granularity
**Selected: Option B — Dealer metrics + options chain snapshot metadata**

Meaning:
- Store daily dealer metrics in a fact table.
- Additionally store lightweight options chain snapshot metadata (counts, timestamps, completeness indicators) to preserve reproducibility without storing full raw chains in Sprint 2.1.

---

### Decision 4 — Config Versioning Strictness
**Selected: Option A — Explicit config_id always**

Meaning:
- Every derived metric row MUST reference a frozen config row (`config_id`).
- No implicit defaults. No hard-coded numeric parameters in schema or code that bypass config binding.

---

### Decision 5 — Algorithm Version Semantics
**Selected: Option C — Semantic tag + Git SHA**

Meaning:
- Derived metric rows MUST store algorithm identity in a way that is both human-readable and forensically precise:
  - semantic version tag (e.g., `dealer-metrics@2.1.0`)
  - git commit SHA (e.g., `a1b2c3d...`)
- These may be stored as separate fields or a composite structured field, but both must be persisted.

---

### Decision 6 — NULL Semantics
**Selected: Option A — NULL is first-class**

Meaning:
- NULL explicitly indicates “not present / not computable under this config + source identity.”
- Zero is a real value and must only be written when mathematically/contractually correct.

---

### Decision 7 — Backfill Authority
**Selected: Option A — PK defines idempotency**

Meaning:
- For derived metrics: async backfills may overwrite existing rows with the same PK (idempotent upsert).
- New rows are created only when input identities differ (e.g., new `config_id`, new algorithm version, or new source identity).

---

## Determinism and Provenance Model (Summary)
For derived metric tables, the reproducibility identity is:
- symbol identity
- trading_date
- config identity (`config_id`)
- algorithm identity (semantic tag + git SHA)
- (and indirectly) upstream source identities captured via run metadata / snapshot metadata

---

## Operational Commitments (Engineering)
Before enabling automated hydration, batch updates, or async backfills, the repository MUST include:
- Schema-level PK and NOT NULL constraints that enforce the decisions above
- Tests that validate:
  - OHLCV versioning behavior (no destructive overwrite)
  - Config binding requirements (config_id required)
  - NULL preservation
  - Idempotency behavior (upsert by PK)
  - Provenance requirements for downstream computations

---

## Change Control
Any change to a Locked Wizard Decision requires:
1. Update to this document
2. A new SQL migration version
3. Updated config contracts (if applicable)
4. Updated tests demonstrating compliance with the revised rule-set

End of document.