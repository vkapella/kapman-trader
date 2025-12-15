# STORY 2.1.1 — Metric Engine Scaffold

**Sprint:** 2.1  
**Type:** Infrastructure / Control Plane  
**Status:** Ready  
**Dependencies:** SPIKE 2.1.B (Design Authority)  
**Related Stories:** 2.1.2, 2.1.3

---

## 1. Objective

Establish a **shared, deterministic execution scaffold** for metric computation that supports both **event-driven** and **batch** invocation paths through a **single unified execution interface**.

This story defines **how metrics are executed**, not **what metrics do**.

---

## 2. Non-Goals (Hard Exclusions)

This story explicitly **does NOT**:

- Implement metric logic, formulas, or indicators
- Register or discover metrics
- Reference metric names, IDs, or types
- Change or extend schemas
- Introduce new invariants or constraints
- Perform persistence logic beyond delegating to existing mechanisms
- Implement scheduling, retries, backfills, or parallelism
- Perform performance optimizations
- Inspect or transform computed metric outputs

Any code violating the above is **out of scope** and invalid for 2.1.1.

---

## 3. Scope

### In Scope
- Unified execution entry point
- Event-driven invocation adapter
- Batch invocation adapter
- Execution context construction and validation
- Deterministic execution flow
- Dry-run execution support
- Logging and trace hooks
- Idempotent write enforcement via existing mechanisms

### Out of Scope
- Metric registration (2.1.2)
- Metric execution logic (2.1.3)
- Metric dependency resolution
- Persistence semantics
- Error recovery strategies

---

## 4. Execution Model

### 4.1 Unified Execution Entry Point

All metric computation—regardless of trigger—must flow through a **single execution interface**.

Conceptually:

```
MetricExecutionEngine.execute(execution_context)
```

No alternate execution paths are permitted.

---

### 4.2 Invocation Sources

#### Event-Driven Invocation
- Triggered by existing domain events.
- Responsibilities:
  - Validate event payload
  - Translate into execution context
  - Invoke unified execution entry point

No computation or business logic is permitted.

#### Batch Invocation
- Triggered manually or by orchestration.
- Produces the same execution context shape.
- Invokes the same unified execution entry point.

---

## 5. Execution Flow

1. Invocation received (event or batch)
2. Execution context constructed (existing schemas only)
3. Pre-execution validation
4. Dispatch to unified execution engine
5. Idempotent write enforcement (delegated)
6. Logging and trace emission
7. Completion or error propagation (no retries)

---

## 6. Dry-Run Semantics

Dry-run mode must:

- Execute the full control flow
- Construct complete execution context
- Invoke execution pipeline
- Prohibit persistence
- Emit logs indicating dry-run

Dry-run is not partial execution.

---

## 7. Interfaces (Contract Level)

- **Execution Engine**
  - `execute(context)`

- **Event Adapter**
  - `handle_event(event) → execution_context`

- **Batch Adapter**
  - `run_batch(params) → execution_context`

- **Shared Utilities**
  - Logging
  - Lookback window reference handling
  - Idempotent write guard (delegation only)

No interface may expose metric internals.

---

## 8. Story Boundaries

### 8.1 Boundary with STORY 2.1.2 (Metric Registration)

2.1.1 must NOT:
- Register or discover metrics
- Reference metric names or IDs
- Contain metric lists or registries

---

### 8.2 Boundary with STORY 2.1.3 (Metric Execution)

2.1.1 must NOT:
- Perform metric computation
- Loop over metrics
- Inspect metric outputs
- Know result shapes or target tables

---

## 9. Acceptance Criteria

- **AC-1:** Event and batch paths invoke the same execution method
- **AC-2:** Invalid execution context fails fast
- **AC-3:** Dry-run produces no database writes
- **AC-4:** Re-execution is idempotent
- **AC-5:** No metric logic or references exist
- **AC-6:** Deterministic start/end logging with mode, scope, dry-run flag

---

## 10. Definition of Done

- Unified scaffold implemented
- Event and batch adapters wired
- Dry-run validated end-to-end
- No metric logic present
- All acceptance criteria passing
- No changes required when 2.1.2 / 2.1.3 are implemented

---

## 11. Forward Compatibility

This scaffold is intentionally neutral and will host future metric registration and execution without modification.
