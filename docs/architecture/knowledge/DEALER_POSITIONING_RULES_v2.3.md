---
system: KapMan
doc_type: metric
version: 2.3
last_validated: 2026-04-04
market_regime: all
confidence: strong
tags:
  - dealer
  - gex
  - dgpi
  - gamma_flip
---

# DEALER_POSITIONING_RULES

## [KapMan] Objective
Capture all implemented dealer-positioning rules for Gamma Exposure (GEX), Dealer Gamma Pressure Index (DGPI), gamma flip, wall ranking, confidence, and quality status.

## [KapMan] Decision Table
| Filter Stage | Keep Contract When | Default Threshold |
|---|---|---|
| Expiration validity | `dte >= 0` | expired rejected |
| DTE horizon | `dte <= max_dte_days` | `max_dte_days = 90` |
| Gamma quality | `gamma` present | non-null required |
| Open interest quality | `open_interest >= min_open_interest` and `>0` | `min_open_interest = 100` |
| Volume quality | `volume >= min_volume` | `min_volume = 1` |

| Dealer Status | Required Conditions | Output |
|---|---|---|
| FULL | `eligible_options >= 25`, non-null/non-zero GEX, position not unknown, confidence high/medium | `FULL` |
| LIMITED | `eligible_options >= 1`, non-null/non-zero GEX, position in long/short/neutral, confidence medium/invalid | `LIMITED` |
| Otherwise | Any failure condition | `INVALID` + reason |

| Position | Net GEX Rule |
|---|---|
| neutral | `abs(net_gex) < 1,000,000` |
| long_gamma | `net_gex > 0` and not neutral |
| short_gamma | `net_gex < 0` and not neutral |

## [KapMan] Rule Catalog
### RULE DEALER_001
RULE_ID: DEALER_001  
SOURCE_FILE: core/metrics/dealer_metrics_job.py  
SOURCE_LINE: 360-381, 562-564  
CATEGORY: Dealer  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: Option contracts are filtered before any dealer calculations.
LOGIC:
- IF: `dte < 0`
- THEN: Reject as expired
- IF: `dte > max_dte_days`
- THEN: Reject
- IF: `gamma is None`
- THEN: Reject
- IF: `open_interest <= 0` or `< min_open_interest`
- THEN: Reject
- IF: `volume < min_volume`
- THEN: Reject
- THRESHOLD: `max_dte_days=90`, `min_open_interest=100`, `min_volume=1`
CONTEXT: Protects Dealer Gamma Pressure Index (DGPI) from low-quality chain artifacts.

### RULE DEALER_002
RULE_ID: DEALER_002  
SOURCE_FILE: docs/research_inputs/dealer_metrics.py  
SOURCE_LINE: 46-75  
CATEGORY: Dealer  
RULE_TYPE: Formula  
CONFIDENCE: STRICT  
DESCRIPTION: Per-contract Gamma Exposure (GEX) uses gamma, open interest, and spot scaling with call-side sign inversion.
LOGIC:
- IF: `gamma is None` or `open_interest <= 0`
- THEN: Contract GEX = `0.0`
- ELSE: `gex = gamma * open_interest * spot^2 * 0.01 * contract_multiplier`
- AND: IF contract type is call, invert sign (`gex = -gex`)
- THRESHOLD: `contract_multiplier = 100`
CONTEXT: Encodes dealer-short-option sign convention used across aggregate metrics.

### RULE DEALER_003
RULE_ID: DEALER_003  
SOURCE_FILE: docs/research_inputs/dealer_metrics.py  
SOURCE_LINE: 80-102  
CATEGORY: Dealer  
RULE_TYPE: Formula  
CONFIDENCE: STRONG  
DESCRIPTION: Strike-level GEX is additive across contracts at the same strike.
LOGIC:
- IF: Contract belongs to strike `K`
- THEN: Add contract GEX into `strike_gex[K]`
- THRESHOLD: None
CONTEXT: Produces canonical strike ladder used by gamma flip and slope calculations.

### RULE DEALER_004
RULE_ID: DEALER_004  
SOURCE_FILE: docs/research_inputs/dealer_metrics.py  
SOURCE_LINE: 105-143  
CATEGORY: Dealer  
RULE_TYPE: Formula  
CONFIDENCE: STRONG  
DESCRIPTION: Gamma flip is interpolated at the cumulative GEX zero-cross.
LOGIC:
- IF: Cumulative GEX changes sign between adjacent strikes
- THEN: Interpolate flip level between those strikes
- AND: Return rounded flip level
- THRESHOLD: Rounded to 2 decimals
CONTEXT: Identifies where dealer hedge behavior is likely to change regime.

### RULE DEALER_005
RULE_ID: DEALER_005  
SOURCE_FILE: docs/research_inputs/dealer_metrics.py  
SOURCE_LINE: 165-201  
CATEGORY: Dealer  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: Wall candidates require valid contract type, positive open interest, non-null gamma, and bounded moneyness.
LOGIC:
- IF: Contract type matches target wall side
- AND: `open_interest > 0`
- AND: `gamma is not None`
- AND: `abs(strike-spot)/spot <= max_moneyness`
- THEN: Include in wall aggregation
- THRESHOLD: `max_moneyness = 0.2` default
CONTEXT: Removes far-tail and low-quality contracts from wall scoring.

### RULE DEALER_006
RULE_ID: DEALER_006  
SOURCE_FILE: docs/research_inputs/dealer_metrics.py  
SOURCE_LINE: 146-163, 216-218  
CATEGORY: Dealer  
RULE_TYPE: Formula  
CONFIDENCE: STRONG  
DESCRIPTION: Wall ranking applies step-based moneyness weighting.
LOGIC:
- IF: `moneyness <= 0.05`
- THEN: Weight `1.0`
- IF: `0.05 < moneyness <= 0.10`
- THEN: Weight `0.7`
- IF: `0.10 < moneyness <= 0.15`
- THEN: Weight `0.4`
- IF: `0.15 < moneyness <= 0.20`
- THEN: Weight `0.2`
- THRESHOLD: Tiered weights above
CONTEXT: Prioritizes nearby strikes in wall significance ranking.

### RULE DEALER_007
RULE_ID: DEALER_007  
SOURCE_FILE: docs/research_inputs/dealer_metrics.py  
SOURCE_LINE: 219-232  
CATEGORY: Dealer  
RULE_TYPE: Classification  
CONFIDENCE: STRONG  
DESCRIPTION: Wall lists are ranked by descending weighted GEX and truncated to top N.
LOGIC:
- IF: Weighted wall list constructed
- THEN: Sort by `-weighted_gex`, tie-break by strike
- THEN: Return first `top_n`
- THRESHOLD: Default `top_n = 3`
CONTEXT: Produces stable, deterministic call/put wall outputs.

### RULE DEALER_008
RULE_ID: DEALER_008  
SOURCE_FILE: docs/research_inputs/dealer_metrics.py  
SOURCE_LINE: 235-266  
CATEGORY: Dealer  
RULE_TYPE: Formula  
CONFIDENCE: STRONG  
DESCRIPTION: Local GEX slope is computed over strike window around spot.
LOGIC:
- IF: Strike ladder and spot are valid
- THEN: Define bounds `[spot*(1-range_pct), spot*(1+range_pct)]`
- AND: `slope = (upper_gex - lower_gex) / price_range`
- THRESHOLD: Default `range_pct = 0.02`
CONTEXT: Approximates hedge-pressure gradient around current price.

### RULE DEALER_009
RULE_ID: DEALER_009  
SOURCE_FILE: docs/research_inputs/dealer_metrics.py  
SOURCE_LINE: 269-320  
CATEGORY: Dealer  
RULE_TYPE: Formula  
CONFIDENCE: STRONG  
DESCRIPTION: Dealer Gamma Pressure Index (DGPI) combines signed log-scaled net GEX, slope effect, and optional IV rank weighting.
LOGIC:
- IF: `net_gex` is null
- THEN: DGPI = null
- ELSE: `base = sign(net_gex) * log10(abs(net_gex)+1) * 10`
- AND: Apply slope multiplier `1 + clamp(gex_slope*0.01, -0.3, 0.3)` when slope exists
- AND: Apply IV multiplier `0.7 + iv_rank/333` when IV rank exists
- THEN: Clamp final DGPI to `[-100, 100]` and round to 2 decimals
- THRESHOLD: slope clamp `[-0.3,0.3]`, output clamp `[-100,100]`
CONTEXT: Produces bounded cross-ticker dealer-pressure signal.

### RULE DEALER_010
RULE_ID: DEALER_010  
SOURCE_FILE: docs/research_inputs/dealer_metrics.py  
SOURCE_LINE: 323-339  
CATEGORY: Dealer  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: Dealer position class uses net GEX magnitude threshold.
LOGIC:
- IF: `abs(net_gex) < threshold`
- THEN: `neutral`
- ELSE IF: `net_gex > 0`
- THEN: `long_gamma`
- ELSE: `short_gamma`
- THRESHOLD: `threshold = 1,000,000`
CONTEXT: Suppresses weak-signal sign flips near zero.

### RULE DEALER_011
RULE_ID: DEALER_011  
SOURCE_FILE: docs/research_inputs/dealer_metrics.py  
SOURCE_LINE: 342-367  
CATEGORY: Dealer  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: Confidence level is determined from contracts-with-gamma count and total open interest.
LOGIC:
- IF: No contracts or `contracts_with_gamma < 5`
- THEN: `invalid`
- IF: `contracts_with_gamma >= 10` and `total_oi >= 1000`
- THEN: `high`
- IF: `contracts_with_gamma >= 5`
- THEN: `medium`
- ELSE: `low`
- THRESHOLD: gamma-count cutoffs `5/10`, OI cutoff `1000`
CONTEXT: Encodes minimum data depth requirements before trusting dealer signals.

### RULE DEALER_012
RULE_ID: DEALER_012  
SOURCE_FILE: core/metrics/dealer_metrics_job.py  
SOURCE_LINE: 95-130  
CATEGORY: Dealer  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: Persisted dealer status (FULL/LIMITED/INVALID) is determined by eligible-option depth plus GEX/position/confidence validity.
LOGIC:
- IF: All FULL conditions pass
- THEN: `FULL`
- ELSE IF: All LIMITED conditions pass
- THEN: `LIMITED`
- ELSE: `INVALID` with first-matching reason
- THRESHOLD: FULL uses `eligible_options >= 25`; LIMITED uses `>=1`
CONTEXT: Controls downstream consumption quality for Dealer Gamma Pressure Index (DGPI) payloads.

### RULE DEALER_013
RULE_ID: DEALER_013  
SOURCE_FILE: core/metrics/dealer_metrics_job.py  
SOURCE_LINE: 525-547, 574  
CATEGORY: Dealer  
RULE_TYPE: Classification  
CONFIDENCE: STRONG  
DESCRIPTION: Metadata status applies secondary quality rules with lower eligible threshold.
LOGIC:
- IF: `eligible_options == 0` or `processing_status != SUCCESS` or all contracts filtered
- THEN: `INVALID`
- IF: `eligible_options >= min_eligible_threshold` and confidence high
- THEN: `FULL`
- IF: confidence medium OR `0 < eligible_options < min_eligible_threshold`
- THEN: `LIMITED`
- THRESHOLD: `min_eligible_threshold = 5`
CONTEXT: Separates payload-level quality annotation from primary status classifier.

### RULE DEALER_014
RULE_ID: DEALER_014  
SOURCE_FILE: core/metrics/dealer_metrics_job.py  
SOURCE_LINE: 565-567; core/metrics/dealer_metrics_calc.py 12-14  
CATEGORY: Dealer  
RULE_TYPE: Threshold  
CONFIDENCE: STRICT  
DESCRIPTION: Runtime defaults pin key dealer model sensitivities.
LOGIC:
- IF: No CLI override provided
- THEN: use defaults `walls_top_n=3`, `gex_slope_range_pct=0.02`, `max_moneyness=0.2`
- THRESHOLD: values above
CONTEXT: Keeps wall/slope model behavior stable across runs.

## [KapMan] Anti-Patterns
- NEVER compute Dealer Gamma Pressure Index (DGPI) from unfiltered contracts lacking gamma/open-interest quality.
- NEVER interpret wall ranks without moneyness weighting tiers.
- NEVER treat low-depth chains as FULL quality dealer signals.
- NEVER ignore the neutral net-GEX deadzone around `|net_gex| < 1,000,000`.

## [KapMan] Source Mapping
- `core/metrics/dealer_metrics_job.py`: 81-130, 360-381, 525-547, 562-567, 574
- `core/metrics/dealer_metrics_calc.py`: 12-14
- `docs/research_inputs/dealer_metrics.py`: 46-75, 80-143, 146-232, 235-339, 342-367

## [KapMan] Change Log
| Date | Version | Change |
|---|---|---|
| 2026-02-13 | 1.0 | Initial extraction of dealer positioning, quality, and formula rules. |
| 2026-04-04 | 2.3 | Standardized to v2.3 production baseline. No content changes. |
