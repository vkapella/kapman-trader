## Dealer Metrics Status Semantics (Authoritative)

A3 assigns **two distinct status concepts** that must not be conflated:

1. **Top-level `status`** — *authoritative data-quality contract for downstream consumers*
2. **`metadata.status`** — *operational/debug heuristic*

Downstream logic (Wyckoff, scoring, ranking, recommendations) **MUST key off the top-level `status` only**.

---

### Top-Level `status` (Contractual)

The top-level `dealer_metrics_json.status` classifies whether dealer metrics are *usable*, *fragile*, or *invalid* for decision-making.

#### FULL

A dealer metrics payload is `FULL` if **all** of the following are true:

* `eligible_options_count >= 25`
* `gex_total` and `gex_net` are present
* `abs(gex_total) > 0`
* `position != "unknown"`
* `confidence ∈ {"high", "medium"}`

**Interpretation**
High-quality, statistically meaningful dealer signal. Safe to use for:

* Wyckoff overlays
* Scoring and ranking
* Regime context and alerts

---

#### LIMITED

A dealer metrics payload is `LIMITED` if **all** of the following are true:

* `eligible_options_count >= 1`
* `eligible_options_count < 25`
* `gex_total` and `gex_net` are present
* `abs(gex_total) > 0`
* `position ∈ {"long_gamma","short_gamma","neutral"}`
* `confidence ∈ {"medium","invalid"}`

**Interpretation**
Dealer math succeeded, but the sample size is thin.
Use only as **weak context**; do **not** allow to dominate Wyckoff or ranking decisions.

Typical causes:

* Small-cap / low-liquidity option chains
* Narrow expiration coverage
* Walls driven by very few contracts

---

#### INVALID

A dealer metrics payload is `INVALID` if **any** of the following apply:

* `eligible_options_count == 0`
* `eligible_options_count < 25` **and** confidence/threshold criteria not met
* Missing or zero-magnitude `gex_total` or `gex_net`
* Spot resolution failed
* Diagnostics include `all_contracts_filtered` or `no_options_available`
* Status thresholds not met (`status_reason = "criteria_not_met"`)

**Important nuance**
`INVALID` does **not** mean computation failed.

Dealer math may have executed successfully, walls and GEX may be present, and `processing_status` may be `SUCCESS` — but the result is **not statistically reliable**.

**Interpretation**
Do not use for:

* Wyckoff confirmation
* Ranking or scoring
* Trade recommendations

May still be inspected manually for exploratory analysis.

---

### `metadata.status` (Non-Authoritative)

`metadata.status` is derived from a **separate heuristic** (lower thresholds, different intent) and exists for:

* Debugging
* Operator inspection
* Pipeline observability

It may disagree with the top-level `status`.

**Rule:**
If `status != metadata.status`, **the top-level `status` always wins**.

---

## Why FULL Metadata Can Still Be INVALID (Critical Insight)

The AEVA example demonstrates a key design decision:

* Dealer math succeeded
* Spot was resolved
* GEX, walls, and gamma flip were computed
* Confidence is `high`

Yet:

* Only **18 eligible contracts**
* Below the `FULL` minimum threshold
* `status_reason = "criteria_not_met"`

Result:

* `metadata.status = FULL`
* **top-level `status = INVALID`**

This is intentional and correct.

The top-level status encodes **statistical sufficiency**, not mathematical success.

---

## Sample Dealer Metrics JSON (LIMITED / INVALID)

The following are **canonical, real-world examples** and should be used for documentation, fixtures, and validation.

---

### INVALID Example — AEVA (Thin Market, Criteria Not Met)

```json
{
  "status": "INVALID",
  "status_reason": "criteria_not_met",
  "eligible_options_count": 18,
  "total_options_count": 184,
  "confidence": "high",
  "position": "neutral",
  "gex_total": 194395.38,
  "gex_net": -162843.81,
  "gamma_flip": 13.16,
  "dgpi": -52.12,
  "spot_price": 14.29,
  "spot_price_source": "ohlcv",
  "processing_status": "SUCCESS",
  "metadata": {
    "symbol": "AEVA",
    "eligible_options": 18,
    "contracts_used": 18,
    "status": "FULL",
    "status_reason": "criteria_not_met"
  }
}
```

**Why INVALID**

* Dealer math succeeded
* Confidence is high
* But **eligible option count < FULL threshold**
* Signal is not statistically robust

---

### LIMITED Example — CXM (Low Liquidity, Thin but Usable)

```json
{
  "status": "LIMITED",
  "status_reason": "limited_thresholds_met",
  "eligible_options_count": 8,
  "total_options_count": 80,
  "confidence": "medium",
  "position": "neutral",
  "gex_total": 47576.0,
  "gex_net": -46164.16,
  "gamma_flip": 5.08,
  "dgpi": -46.64,
  "spot_price": 7.84,
  "spot_price_source": "ohlcv",
  "processing_status": "SUCCESS",
  "metadata": {
    "symbol": "CXM",
    "eligible_options": 8,
    "contracts_used": 8,
    "status": "LIMITED",
    "status_reason": "limited_thresholds_met"
  }
}
```

**Why LIMITED**

* Dealer math succeeded
* Non-zero GEX
* Confidence is medium
* Sample size is small but non-zero

Use only as **contextual signal**, never primary.

---

## Downstream Consumption Rules (Updated)

When integrating dealer metrics into Wyckoff (A8.*):

1. **Gate on top-level `status`**

   * `FULL` → normal weight
   * `LIMITED` → reduced weight
   * `INVALID` → ignore

2. Never infer usability from:

   * `processing_status`
   * `metadata.status`
   * Presence of walls or gamma flip alone

3. Treat `eligible_options_count` as a **first-class reliability indicator**

---

## Documentation Invariant (Recommended)

Add this invariant to prevent future drift:

> Any change to:
>
> * dealer thresholds
> * status rules
> * filter defaults
> * wall construction
>
> MUST update `dealer_metrics.md` in the same PR.

---

If you want, next we can:

* Add a **truth table** mapping `eligible_options × confidence → status`
* Add **SQL assertions** that detect status/metadata disagreement
* Generate a **pytest fixture** directly from AEVA and CXM for regression tests
