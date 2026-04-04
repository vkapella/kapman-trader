---
system: KapMan
doc_type: strategy
version: 2.3
last_validated: 2026-04-04
market_regime: all
confidence: strong
tags:
  - wyckoff
  - events
  - thresholds
  - structural
---

# WYCKOFF_EVENT_DETECTION_RULES

## [KapMan] Objective
Capture all implemented event-detection logic for Selling Climax (SC), Automatic Rally (AR), SPRING, Sign of Strength (SOS), Buying Climax (BC), Upthrust (UT), Sign of Weakness (SOW), and related guards.

## [KapMan] Decision Table
| Event | IF Core Trigger | AND Filters | THEN | Thresholds |
|---|---|---|---|---|
| Selling Climax (SC) | `tr_z` and `vol_z` spike | Close not at bar low; optional prior downtrend | Emit SC | `tr_z >= 2.0`, `vol_z >= 2.0`, `close_pos >= 0.5`, `sma_slope < 0` when enabled |
| Buying Climax (BC) | `tr_z` and `vol_z` spike | Close near bar high; optional prior uptrend | Emit BC | `tr_z >= 2.0`, `vol_z >= 2.0`, `close_pos >= 0.6`, `sma_slope > 0` when enabled |
| Automatic Rally (AR) | First up-close after SC | Elevated range expansion | Emit AR | In `SC+1 .. SC+min_bars_in_range`, `tr_z > 0.5` |
| AR_TOP | First down-close after BC | Elevated range expansion | Emit AR_TOP | In `BC+1 .. BC+min_bars_in_range`, `tr_z > 0.5` |
| SPRING | Low breaks support | Re-entry into range, strong close, enough volume | Emit SPRING | Break `>1%`, re-entry `<=2` bars, `close_pos >= 0.6`, `vol_z >= 0.8` |
| Upthrust (UT) | High breaks resistance | Re-entry below resistance, weak close | Emit UT | Break `>1%`, re-entry `<=2` bars, `close_pos <= 0.4` |
| Sign of Strength (SOS) | Close above resistance | Strong range expansion | Emit SOS | `tr_z >= 1.5` |
| Sign of Weakness (SOW) | Close below support | Strong range expansion | Emit SOW | `tr_z >= 1.5` |

## [KapMan] Rule Catalog
### RULE WYCKOFF_EVENT_001
RULE_ID: WYCKOFF_EVENT_001  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 134-135  
CATEGORY: Wyckoff  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: Event detection is disabled when there are not enough bars for range logic.
LOGIC:
- IF: `len(df) < min_bars_in_range`
- THEN: Return no events and no phases
- THRESHOLD: `min_bars_in_range = 20`
CONTEXT: Prevents false structure labeling on insufficient history.

### RULE WYCKOFF_EVENT_002
RULE_ID: WYCKOFF_EVENT_002  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 167-170, 184  
CATEGORY: Wyckoff  
RULE_TYPE: Threshold  
CONFIDENCE: STRONG  
DESCRIPTION: Selling Climax (SC) requires concurrent range and volume shock plus close recovery off the low.
LOGIC:
- IF: `tr_z >= sc_tr_z`
- AND: `vol_z >= sc_vol_z`
- AND: `close_pos >= 0.5`
- THEN: Emit Selling Climax (SC)
- THRESHOLD: `sc_tr_z=2.0`, `sc_vol_z=2.0`, `close_pos>=0.5`
CONTEXT: Forces SC to represent capitulation-like expansion with intrabar buyer response.

### RULE WYCKOFF_EVENT_003
RULE_ID: WYCKOFF_EVENT_003  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 174-182, 54  
CATEGORY: Wyckoff  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: SC candidate selection enforces prior downtrend when trend gating is enabled.
LOGIC:
- IF: `require_prior_trend_for_sc_bc == True`
- AND: `sma_slope < 0` at candidate bar
- THEN: Candidate is eligible for SC selection
- THRESHOLD: Boolean gate default `True`
CONTEXT: Avoids labeling isolated volatility spikes as Selling Climax (SC) without prior decline.

### RULE WYCKOFF_EVENT_004
RULE_ID: WYCKOFF_EVENT_004  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 188-191, 203  
CATEGORY: Wyckoff  
RULE_TYPE: Threshold  
CONFIDENCE: STRONG  
DESCRIPTION: Buying Climax (BC) requires concurrent range and volume shock and strong close near bar high.
LOGIC:
- IF: `tr_z >= bc_tr_z`
- AND: `vol_z >= bc_vol_z`
- AND: `close_pos >= 0.6`
- THEN: Emit Buying Climax (BC)
- THRESHOLD: `bc_tr_z=2.0`, `bc_vol_z=2.0`, `close_pos>=0.6`
CONTEXT: Encodes late-stage demand exhaustion behavior.

### RULE WYCKOFF_EVENT_005
RULE_ID: WYCKOFF_EVENT_005  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 195-201, 54  
CATEGORY: Wyckoff  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: BC candidate selection enforces prior uptrend when trend gating is enabled.
LOGIC:
- IF: `require_prior_trend_for_sc_bc == True`
- AND: `sma_slope > 0` at candidate bar
- THEN: Candidate is eligible for BC selection
- THRESHOLD: Boolean gate default `True`
CONTEXT: Reduces false Buying Climax (BC) labels in sideways regimes.

### RULE WYCKOFF_EVENT_006
RULE_ID: WYCKOFF_EVENT_006  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 210-218  
CATEGORY: Wyckoff  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: Automatic Rally (AR) is the first qualifying upward reaction after Selling Climax (SC).
LOGIC:
- IF: Bar is in window `SC+1 .. SC+min_bars_in_range`
- AND: `close[i] > close[i-1]`
- AND: `tr_z > 0.5`
- THEN: Emit Automatic Rally (AR) at first match
- THRESHOLD: Reaction threshold `tr_z > 0.5`
CONTEXT: Captures immediate post-climax recovery impulse.

### RULE WYCKOFF_EVENT_007
RULE_ID: WYCKOFF_EVENT_007  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 221-229  
CATEGORY: Wyckoff  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: AR_TOP is the first qualifying downward reaction after Buying Climax (BC).
LOGIC:
- IF: Bar is in window `BC+1 .. BC+min_bars_in_range`
- AND: `close[i] < close[i-1]`
- AND: `tr_z > 0.5`
- THEN: Emit AR_TOP at first match
- THRESHOLD: Reaction threshold `tr_z > 0.5`
CONTEXT: Captures early loss of upside control after climax.

### RULE WYCKOFF_EVENT_008
RULE_ID: WYCKOFF_EVENT_008  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 241-262, 42-44, 35  
CATEGORY: Wyckoff  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: SPRING requires support break, re-entry, strong close location, and sufficient volume surprise.
LOGIC:
- IF: `low < support_level * (1 - spring_break_pct)`
- AND: Any close in `[i, i+spring_reentry_bars]` is `>= support_level`
- AND: `close_pos >= spring_close_pos`
- AND: `vol_z >= spring_vol_z`
- THEN: Emit first SPRING and stop scanning
- THRESHOLD: `spring_break_pct=0.01`, `spring_reentry_bars=2`, `spring_close_pos=0.6`, `spring_vol_z=0.8`
CONTEXT: Implements false-breakdown reversal behavior expected in Accumulation Phase.

### RULE WYCKOFF_EVENT_009
RULE_ID: WYCKOFF_EVENT_009  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 265-281, 45-47  
CATEGORY: Wyckoff  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: Upthrust (UT) requires resistance break, re-entry below resistance, and weak close location.
LOGIC:
- IF: `high > resistance_level * (1 + ut_break_pct)`
- AND: Any close in `[i, i+ut_reentry_bars]` is `<= resistance_level`
- AND: `close_pos <= ut_close_pos`
- THEN: Emit first UT and stop scanning
- THRESHOLD: `ut_break_pct=0.01`, `ut_reentry_bars=2`, `ut_close_pos=0.4`
CONTEXT: Encodes failed breakout behavior in Distribution Phase.

### RULE WYCKOFF_EVENT_010
RULE_ID: WYCKOFF_EVENT_010  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 287-293, 34  
CATEGORY: Wyckoff  
RULE_TYPE: Threshold  
CONFIDENCE: STRONG  
DESCRIPTION: Sign of Strength (SOS) proxy is first close above resistance with strong range expansion.
LOGIC:
- IF: `close > resistance_level`
- AND: `tr_z >= sos_tr_z`
- THEN: Emit first SOS
- THRESHOLD: `sos_tr_z=1.5`
CONTEXT: Uses breakout plus expansion proxy for strength confirmation.

### RULE WYCKOFF_EVENT_011
RULE_ID: WYCKOFF_EVENT_011  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 295-301, 33  
CATEGORY: Wyckoff  
RULE_TYPE: Threshold  
CONFIDENCE: STRONG  
DESCRIPTION: Sign of Weakness (SOW) proxy is first close below support with strong range expansion.
LOGIC:
- IF: `close < support_level`
- AND: `tr_z >= sow_tr_z`
- THEN: Emit first SOW
- THRESHOLD: `sow_tr_z=1.5`
CONTEXT: Uses breakdown plus expansion proxy for weakness confirmation.

### RULE WYCKOFF_EVENT_012
RULE_ID: WYCKOFF_EVENT_012  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 49-51, 149-160, 184, 203, 218, 229, 261, 280, 293, 301  
CATEGORY: Wyckoff  
RULE_TYPE: Formula  
CONFIDENCE: STRONG  
DESCRIPTION: Event score payload is directly derived from selected z-score channel per event type.
LOGIC:
- IF: Event is SC or BC or SPRING
- THEN: Store `score = vol_z`
- IF: Event is AR or AR_TOP or UT or SOS or SOW
- THEN: Store `score = tr_z`
- THRESHOLD: None beyond event detector thresholds
CONTEXT: Preserves a scalar severity signal for downstream primary-event selection.

### RULE WYCKOFF_EVENT_013
RULE_ID: WYCKOFF_EVENT_013  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 49-51  
CATEGORY: Wyckoff  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: Secondary Test (ST) parameters exist in config but no Secondary Test (ST) detection logic is implemented.
LOGIC:
- IF: Looking for Secondary Test (ST) detector
- THEN: No runtime detector branch exists
- THRESHOLD: `max_st_deviation_pct=0.01`, `test_low_vol_factor=0.7` (defined but unused)
CONTEXT: Prevents assuming Secondary Test (ST) support in production when only placeholders exist.

## [KapMan] Anti-Patterns
- NEVER assume Secondary Test (ST) detection is active; it is not implemented.
- NEVER treat any bar with high range as Selling Climax (SC) or Buying Climax (BC) without volume and close-position filters.
- NEVER assume multiple SPRING or Upthrust (UT) events are emitted in one pass; logic stops after first match.
- NEVER infer Sign of Strength (SOS) or Sign of Weakness (SOW) without support/resistance construction from prior climax/reaction context.

## [KapMan] Source Mapping
- `core/metrics/structural.py`: 14-58, 134-135, 149-301

## [KapMan] Change Log
| Date | Version | Change |
|---|---|---|
| 2026-02-13 | 1.0 | Initial extraction from runtime structural event logic. |
| 2026-04-04 | 2.3 | Standardized to v2.3 production baseline. No content changes. |
