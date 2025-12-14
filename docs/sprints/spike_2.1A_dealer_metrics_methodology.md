# Dealer Metrics Methodology (SPIKE 2.1.A)

## Purpose
This document defines the **Sprint 2.1 MVP methodology** for dealer and market-structure metrics used by KapMan.

These metrics are **descriptive inputs**, not trading signals. They are designed to be:
- Deterministic
- Explainable
- Daily (end-of-day) snapshots
- Independent of Wyckoff logic, scoring, or recommendations

Empirical validation and tuning are intentionally deferred to **Sprint 2.2**.

---

## Design Principles (MVP)
1. Daily snapshot only (no intraday inference)
2. Explainability over precision
3. Open Interest first, volume second
4. Near-dated expirations dominate
5. Missing or insufficient data degrades to NULL, not noise

---
## Dealer Metrics Configuration Contract

Dealer metrics require the following configuration input at runtime:

- `dealer_metrics.max_dte_days`

Sprint 2.1 defines metric behavior assuming a near-dated option universe.
Selection of the numeric DTE value is intentionally deferred to later sprints
to support strategy-specific and regime-specific tuning.

In Sprint 2.1 storage:
- Do NOT store a numeric DTE value (e.g., 45)
- Instead store a configuration reference identifier

This enables:
- Multiple dealer-metric configurations
- Historical reproducibility
- Re-computation and comparison across configurations

---

## Options Universe Definition

### Included Contracts
- Calls and puts
- Nearest two standard expirations (weekly or monthly)
- Maximum DTE provided via configuration (`dealer_metrics.max_dte_days`)

Sprint 2.1 assumes a near-dated option universe but does not prescribe
a fixed DTE value.

### Excluded Contracts
- Contracts with DTE greater than the configured maximum
- Contracts missing any of:
  - Gamma
  - Open interest
  - Strike
  - Option type
  - Spot price

---


### 1. Aggregate Gamma Exposure (GEX)

Aggregate gamma exposure represents the net gamma positioning across the defined options universe.

For each option contract:

contract_gex =
  gamma
* open_interest
* contract_multiplier
* (spot_price ^ 2)
* sign

Where:
- contract_multiplier = 100
- sign = +1 for calls, -1 for puts

Aggregate GEX is computed as:

aggregate_gex = sum(contract_gex across all included contracts)

Stored as a signed numeric value.

---

### 2. DGCPI (Dealer Gamma Composite Positioning Index)

DGCPI is a normalized, unitless representation of aggregate dealer gamma positioning.

dgcpi = aggregate_gex / notional_scale

Where:

notional_scale =
  spot_price^2
* total_open_interest
* contract_multiplier

DGCPI is descriptive only and contains no thresholds or regime classification.

---

### 3. Gamma Flip Price

The gamma flip price represents the strike level at which cumulative dealer gamma exposure changes sign.

Methodology:
1. Group contracts by strike
2. Compute cumulative GEX across strikes (ascending)
3. Identify the strike where:
   - cumulative GEX crosses zero, or
   - absolute cumulative GEX is minimized

That strike is stored as the gamma flip price.

If no such strike exists, gamma_flip = NULL.

---

### 4. Gamma Flip Distance (% of Spot)

Gamma flip distance measures the relative position of spot price to the gamma flip level.

gamma_flip_distance_pct =
  (spot_price - gamma_flip) / spot_price

If gamma_flip is NULL, this metric is also NULL.

---

### 5. Call Wall / Put Wall

Call and put walls represent dominant concentrations of dealer gamma at specific strike levels.

Strike Exposure:
strike_exposure =
  sum(abs(contract_gex)) at that strike

Call Wall:
- Strike with the highest strike_exposure from call contracts
- Strike must be above the current spot price

Put Wall:
- Strike with the highest strike_exposure from put contracts
- Strike must be below the current spot price

MVP stores one wall per side only.

Walls identify structural concentration points only; interpretation of wall interaction or breach is deferred to Sprint 2.2.

---

### 6. Call Open Interest / Put Open Interest

Raw open interest values are stored to preserve foundational positioning data.

Open Interest Aggregation:

call_open_interest =
  sum(open_interest) for call contracts

put_open_interest =
  sum(open_interest) for put contracts

Aggregation is performed across:
- All included strikes
- All included expirations (as defined by `dealer_metrics.max_dte_days`)
- Contracts passing data-quality filters

Call Open Interest:
- Sum of open interest from call contracts only

Put Open Interest:
- Sum of open interest from put contracts only

MVP Constraints:
- Open interest values are stored without normalization
- No ratios or sentiment interpretation are applied
- Put/Call ratio and positioning signals are explicitly deferred to Sprint 2.2

MVP stores one aggregated value per side only.


---

## Data Quality Rules

### Contract Filtering
A contract is excluded if any of the following are missing:
- Gamma
- Open interest
- Strike
- Option type
- Spot price

### Symbol-Level Validity
If fewer than **20 valid contracts** remain after filtering:
- All dealer metrics for that symbol/date are set to NULL

---

## Stored Fields (Preview)

Minimum required fields:

symbol  
date  
aggregate_gex  
dgcpi  
gamma_flip  
gamma_flip_distance_pct  
call_wall  
put_wall  
call_open_interest  
put_open_interest  
expiration_count  
contract_count  
source_version  
dealer_metrics_config_id

Counts are stored for **observability**, not signal generation.

---

## Explicit Non-Goals
The following are **explicitly out of scope** for Sprint 2.1:
- Intraday dealer metrics
- Dealer intent inference
- Charm, vanna, or higher-order Greeks
- Strategy or signal generation
- Normalization beyond DGCPI

---

**Status:** APPROVED FOR SPRINT 2.1
