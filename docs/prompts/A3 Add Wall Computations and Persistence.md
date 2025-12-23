A3.1 Add Wall Computation & Persistence

You are working in the kapman-trader repository.

Objective

Extend A3 Dealer Metrics to compute, rank, and persist options “walls”:
- call_walls
- put_walls
- primary_call_wall
- primary_put_wall

These walls represent strike-level gamma exposure concentrations used for
market-structure analysis (pinning, support/resistance) and must comply with
A8 constraints (no bid/ask dependency).

This story adds wall computation only. It must not refactor unrelated logic.

⸻

Context (Must Respect)

Current State:
- A3 computes dealer metrics (GEX total, net GEX, gamma flip, position, confidence)
- Dealer metrics are persisted into daily_snapshots.dealer_metrics_json
- Bid/ask data is largely missing (Polygon backfill) and must not be used
- Options ingestion (A1.1) now guarantees deterministic snapshot_time per day
- A3 selects a single deterministic snapshot per day

We now need to add wall computation in a way that:
- Is deterministic
- Is structurally meaningful (near spot)
- Avoids false walls from deep OTM strikes
- Produces stable, explainable outputs

⸻

Hard Constraints

1. NO schema changes
2. NO bid / ask usage anywhere in wall logic
3. Walls must be computed from already-eligible options only
4. Deterministic output for identical inputs
5. Backward compatibility with existing A3 consumers
6. Walls must live inside dealer_metrics_json

⸻

Definitions

Wall:
A strike-level aggregation of gamma exposure (GEX) that represents a
concentration of dealer hedging pressure.

Primary Wall:
The highest-ranked wall on each side (call / put) after weighting and filtering.

⸻

Required Behavioral Changes

1️⃣ Wall Eligibility Filters (Pre-Aggregation)

Reuse existing A3 eligibility filters:
- max_dte_days
- min_open_interest
- min_volume
- gamma must be present

ADD new structural filter:

• Moneyness filter (distance from spot):
  abs(strike - spot_price) / spot_price <= max_moneyness

Default:
- max_moneyness = 0.20  (±20%)

This value MUST be configurable via CLI.

Rationale:
Deep OTM strikes do not materially affect near-term dealer hedging and
create false support/resistance signals.

⸻

2️⃣ Strike-Level Aggregation

For each ticker and snapshot:

Group eligible contracts by:
- strike
- option_type (CALL / PUT)

Aggregate per group:
- gex = SUM(contract_gex)
- open_interest = SUM(open_interest)
- contracts = COUNT(*)

This aggregation produces candidate wall strikes.

⸻

3️⃣ Proximity Weighting (Sorting Logic)

Walls MUST be ranked by proximity-weighted GEX, not raw absolute GEX.

Compute:

moneyness = abs(strike - spot_price) / spot_price

Apply step-based decay:

- moneyness ≤ 5%   → weight = 1.0
- moneyness ≤ 10%  → weight = 0.7
- moneyness ≤ 15%  → weight = 0.4
- moneyness ≤ 20%  → weight = 0.2

weighted_gex = abs(gex) * weight

Sorting:
- Sort walls by weighted_gex DESC
- Use raw gex only for reporting, not ranking

Rationale:
Dealer hedging impact decays rapidly with distance from spot.

⸻

4️⃣ Wall Selection

For each ticker:

- call_walls = top N CALL walls by weighted_gex
- put_walls  = top N PUT walls by weighted_gex

N is controlled by existing --walls-top-n flag.

Primary walls:
- primary_call_wall = first element of call_walls (or null)
- primary_put_wall  = first element of put_walls (or null)

⸻

5️⃣ JSON Persistence Contract

Persist walls inside dealer_metrics_json with full transparency.

Required fields:

{
  "call_walls": [
    {
      "strike": number,
      "gex": number,
      "weighted_gex": number,
      "moneyness": number,
      "open_interest": number,
      "contracts": number
    }
  ],
  "put_walls": [
    {
      "strike": number,
      "gex": number,
      "weighted_gex": number,
      "moneyness": number,
      "open_interest": number,
      "contracts": number
    }
  ],
  "primary_call_wall": {
    "strike": number,
    "gex": number,
    "distance_from_spot": number
  } | null,
  "primary_put_wall": {
    "strike": number,
    "gex": number,
    "distance_from_spot": number
  } | null,
  "spot_price": number,
  "wall_config": {
    "max_moneyness": number,
    "walls_top_n": number,
    "max_dte_days": number
  }
}

Notes:
- distance_from_spot = strike - spot_price (signed)
- Raw gex is preserved for auditability
- weighted_gex explains ranking

⸻

6️⃣ CLI Changes (Allowed)

Add CLI flag to A3:

--max-moneyness FLOAT
  Maximum allowed distance from spot (as fraction of spot) for wall eligibility.
  Default: 0.20

This flag:
- Affects wall computation only
- Does NOT affect other dealer metrics

⸻

7️⃣ Determinism Guarantees

- Stable sorting (tie-break by strike if needed)
- No randomness
- Same input snapshot → identical JSON output

⸻

Testing Requirements (Must Add)

Unit tests in tests/unit/dealer_metrics/:

1. Proximity dominance test
   - Near-ATM strike beats higher-GEX deep OTM strike

2. Empty result test
   - No eligible strikes → empty arrays + null primaries

3. Determinism test
   - Same input → byte-identical JSON output

4. Moneyness cutoff test
   - Strikes beyond max_moneyness are excluded

Optional (document-only if skipped):
- Mixed strike spacing behavior

⸻

Acceptance Criteria

✅ call_walls and put_walls are populated when eligible data exists  
✅ primary_call_wall and primary_put_wall are correct and deterministic  
✅ No bid/ask fields are read or referenced  
✅ Deep OTM strikes (> max_moneyness) never dominate walls  
✅ Weighted GEX, moneyness, and spot_price are persisted  
✅ CLI allows tuning max_moneyness  
✅ Dealer metrics dashboards show walls without schema changes  
✅ Re-running A3 on same snapshot produces identical output  

⸻

Out of Scope (Explicitly)

- Bid/ask reconstruction
- Time-decay weighting across expirations
- Strike-density normalization
- Schema migrations

These may be future stories.

⸻

Final Instruction

Implement exactly as specified.
Do not refactor unrelated code.
Favor clarity and determinism over cleverness.