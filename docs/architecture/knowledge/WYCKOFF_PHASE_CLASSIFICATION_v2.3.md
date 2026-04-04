---
system: KapMan
doc_type: strategy
version: 2.3
last_validated: 2026-04-04
market_regime: all
confidence: strong
tags:
  - wyckoff
  - phase_classification
  - regime
  - transitions
---

# WYCKOFF_PHASE_CLASSIFICATION

## [KapMan] Objective
Document all implemented rules that classify Accumulation Phase, Markup, Distribution, Markdown, and daily Wyckoff regime state transitions.

## [KapMan] Decision Table
| Input Event | Regime Output | Priority Rank (same day) |
|---|---|---|
| SC | ACCUMULATION | 1 |
| SPRING | ACCUMULATION | 2 |
| SOS | MARKUP | 3 |
| BC | DISTRIBUTION | 4 |
| UT | DISTRIBUTION | 5 |
| SOW | MARKDOWN | 6 |

| Transition Pair | Allowed | Minimum Prior Duration |
|---|---|---|
| ACCUMULATION -> MARKUP | Yes | 5 bars |
| MARKUP -> DISTRIBUTION | Yes | 5 bars |
| DISTRIBUTION -> MARKDOWN | Yes | 5 bars |
| MARKDOWN -> ACCUMULATION | Yes | 5 bars |
| Any other pair | No | N/A |

## [KapMan] Rule Catalog
### RULE WYCKOFF_PHASE_001
RULE_ID: WYCKOFF_PHASE_001  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 311-319, 58  
CATEGORY: Wyckoff  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: A structural phase is rejected when its span is shorter than minimum phase length.
LOGIC:
- IF: `end_idx - start_idx + 1 < min_phase_bars`
- THEN: Return empty phase object
- THRESHOLD: `min_phase_bars = 2`
CONTEXT: Prevents single-bar phase noise.

### RULE WYCKOFF_PHASE_002
RULE_ID: WYCKOFF_PHASE_002  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 321-327  
CATEGORY: Wyckoff  
RULE_TYPE: Classification  
CONFIDENCE: STRONG  
DESCRIPTION: Accumulation Phase starts at Selling Climax (SC) and ends at Sign of Strength (SOS) if present, else Automatic Rally (AR), else SC itself.
LOGIC:
- IF: Selling Climax (SC) exists
- THEN: `acc_end = SOS else AR else SC`
- THEN: Create Accumulation Phase from `SC -> acc_end`
- THRESHOLD: None
CONTEXT: Encodes foundational Accumulation Phase structure in the structural model.

### RULE WYCKOFF_PHASE_003
RULE_ID: WYCKOFF_PHASE_003  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 328-333  
CATEGORY: Wyckoff  
RULE_TYPE: Classification  
CONFIDENCE: STRONG  
DESCRIPTION: Markup begins at end of Accumulation Phase and terminates at Buying Climax (BC).
LOGIC:
- IF: Accumulation Phase exists
- AND: Buying Climax (BC) exists
- THEN: Create Markup from `Accumulation.end -> BC`
- THRESHOLD: None
CONTEXT: Uses phase handoff boundary instead of separate detector.

### RULE WYCKOFF_PHASE_004
RULE_ID: WYCKOFF_PHASE_004  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 335-345  
CATEGORY: Wyckoff  
RULE_TYPE: Classification  
CONFIDENCE: STRONG  
DESCRIPTION: Distribution starts at Buying Climax (BC) and ends at Sign of Weakness (SOW), else AR_TOP, else BC.
LOGIC:
- IF: Buying Climax (BC) exists
- THEN: `dist_end = SOW else AR_TOP else BC`
- THEN: Create Distribution from `BC -> dist_end`
- THRESHOLD: None
CONTEXT: Captures Distribution with weakening confirmation precedence.

### RULE WYCKOFF_PHASE_005
RULE_ID: WYCKOFF_PHASE_005  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 347-356  
CATEGORY: Wyckoff  
RULE_TYPE: Classification  
CONFIDENCE: STRONG  
DESCRIPTION: Markdown starts at Sign of Weakness (SOW) and extends to next Selling Climax (SC) or final bar.
LOGIC:
- IF: Sign of Weakness (SOW) exists
- AND: A later Selling Climax (SC) exists
- THEN: Markdown end = first later Selling Climax (SC)
- ELSE: Markdown end = last available bar
- THRESHOLD: None
CONTEXT: Implements cyclical transition back to potential Accumulation Phase.

### RULE WYCKOFF_PHASE_006
RULE_ID: WYCKOFF_PHASE_006  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 357-362, 55  
CATEGORY: Wyckoff  
RULE_TYPE: Conditional  
CONFIDENCE: STRICT  
DESCRIPTION: Soft Markdown fallback is disabled by default and only activates when explicitly enabled.
LOGIC:
- IF: No Sign of Weakness (SOW)
- AND: `allow_soft_markdown_without_sow == True`
- AND: Buying Climax (BC) exists
- THEN: Create Markdown from Distribution end (or BC) to final bar
- THRESHOLD: `allow_soft_markdown_without_sow = False` default
CONTEXT: Prevents Markdown inference without explicit weakness signal under default settings.

### RULE WYCKOFF_PHASE_007
RULE_ID: WYCKOFF_PHASE_007  
SOURCE_FILE: core/metrics/structural.py  
SOURCE_LINE: 365-374, 56-57  
CATEGORY: Wyckoff  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: First and last detected structural phases can be extended to chart edges.
LOGIC:
- IF: `extend_first_phase_to_start == True`
- THEN: Set earliest phase start index to 0
- IF: `extend_last_phase_to_end == True`
- THEN: Set latest phase end index to `n-1`
- THRESHOLD: Both defaults `True`
CONTEXT: Produces continuous phase coverage for chart shading.

### RULE WYCKOFF_PHASE_008
RULE_ID: WYCKOFF_PHASE_008  
SOURCE_FILE: core/metrics/b1_wyckoff_regime_job.py  
SOURCE_LINE: 27-37, 270-286  
CATEGORY: Wyckoff  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: Daily regime is set from event codes using fixed event-to-regime mapping and fixed priority order.
LOGIC:
- IF: Day contains one or more regime-setting events
- THEN: Select first event in priority list `[SC, SPRING, SOS, BC, UT, SOW]`
- THEN: Map selected event to regime `{SC/SPRING->ACCUMULATION, SOS->MARKUP, BC/UT->DISTRIBUTION, SOW->MARKDOWN}`
- THRESHOLD: Priority rank is deterministic and static
CONTEXT: Ensures same-day deterministic regime assignment.

### RULE WYCKOFF_PHASE_009
RULE_ID: WYCKOFF_PHASE_009  
SOURCE_FILE: core/metrics/b1_wyckoff_regime_job.py  
SOURCE_LINE: 281-292, 410  
CATEGORY: Wyckoff  
RULE_TYPE: Conditional  
CONFIDENCE: STRICT  
DESCRIPTION: Daily regime confidence is set to 1.0 when a setting event occurs; otherwise prior regime/confidence is carried forward.
LOGIC:
- IF: A regime-setting event is selected
- THEN: `confidence = 1.0`, `set_by_event = selected_event`
- ELSE: Carry prior `regime` and prior `confidence`, set `set_by_event = None`
- THRESHOLD: Hard confidence setpoint `1.0`
CONTEXT: Distinguishes event-triggered state changes from persistence days.

### RULE WYCKOFF_PHASE_010
RULE_ID: WYCKOFF_PHASE_010  
SOURCE_FILE: core/metrics/b1_wyckoff_regime_job.py  
SOURCE_LINE: 410  
CATEGORY: Wyckoff  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: Initial prior state defaults to UNKNOWN regime with null confidence.
LOGIC:
- IF: No prior regime state exists
- THEN: Initialize `regime=UNKNOWN`, `confidence=None`, `set_by_event=None`
- THRESHOLD: N/A
CONTEXT: Avoids backfilling inferred certainty into first observed date.

### RULE WYCKOFF_PHASE_011
RULE_ID: WYCKOFF_PHASE_011  
SOURCE_FILE: core/metrics/b4_wyckoff_derived_job.py  
SOURCE_LINE: 25-30, 285-290  
CATEGORY: Wyckoff  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: Regime transitions are persisted only for approved cycle transitions and only when prior regime duration is at least 5 bars.
LOGIC:
- IF: `prior_regime` and `new_regime` are non-unknown
- AND: Pair is in allowed transitions set
- AND: `prior_duration >= 5`
- THEN: Emit transition row
- THRESHOLD: `prior_duration >= 5`
CONTEXT: Filters transient regime flips.

### RULE WYCKOFF_PHASE_012
RULE_ID: WYCKOFF_PHASE_012  
SOURCE_FILE: core/metrics/b4_1_wyckoff_sequences_job.py  
SOURCE_LINE: 36-44, 408-410, 419-426  
CATEGORY: Wyckoff  
RULE_TYPE: Classification  
CONFIDENCE: STRONG  
DESCRIPTION: Terminal-event sequence eligibility and invalidation are regime-gated.
LOGIC:
- IF: Terminal event is SOS
- AND: Prior regime in `{ACCUMULATION, MARKDOWN}`
- THEN: Sequence eligible; invalidate if transition enters `{DISTRIBUTION, MARKUP}` between start and terminal date
- IF: Terminal event is SOW
- AND: Prior regime in `{DISTRIBUTION, MARKUP}`
- THEN: Sequence eligible; invalidate if transition enters `{ACCUMULATION, MARKDOWN}`
- THRESHOLD: Regime sets are static
CONTEXT: Prevents contradictory sequence labeling against live regime path.

### RULE WYCKOFF_PHASE_013
RULE_ID: WYCKOFF_PHASE_013  
SOURCE_FILE: core/metrics/b4_1_wyckoff_sequences_job.py  
SOURCE_LINE: 345-349  
CATEGORY: Wyckoff  
RULE_TYPE: Formula  
CONFIDENCE: STRONG  
DESCRIPTION: Sequence confidence scales linearly with supporting-event count and saturates at 1.0.
LOGIC:
- IF: Supporting-event count is `n`
- THEN: `confidence = min(1.0, round(0.6 + 0.1 * max(0, n), 4))`
- THRESHOLD: Base `0.6`, step `0.1`, cap `1.0`
CONTEXT: Provides deterministic confidence weighting for canonical sequence completeness.

## [KapMan] Anti-Patterns
- NEVER assign daily regime from an event not in the explicit priority set.
- NEVER infer Markup or Markdown transitions from sub-5-bar prior regime durations in derived transitions.
- NEVER treat invalidated canonical sequences as equivalent to valid confirmations.
- NEVER assume soft Markdown behavior is active without explicit config override.

## [KapMan] Source Mapping
- `core/metrics/structural.py`: 311-374
- `core/metrics/b1_wyckoff_regime_job.py`: 27-37, 270-292, 410
- `core/metrics/b4_wyckoff_derived_job.py`: 25-30, 262-303
- `core/metrics/b4_1_wyckoff_sequences_job.py`: 36-44, 345-349, 408-426

## [KapMan] Change Log
| Date | Version | Change |
|---|---|---|
| 2026-02-13 | 1.0 | Initial extraction of phase, regime, and transition classification logic. |
| 2026-04-04 | 2.3 | Standardized to v2.3 production baseline. No content changes. |
