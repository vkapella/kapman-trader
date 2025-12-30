# Wyckoff Algorithmic Decision Specification (Research-Validated)

## 1. Purpose & Scope

This algorithm consumes **daily OHLCV** for a single instrument and emits a deterministic set of **Wyckoff-style structural labels**:

- **Primary structural events**: `SC`, `BC`, `AR`, `AR_TOP`, `SPRING`, `UT`, `SOS`, `SOW`
- **Daily regime labels** derived from a subset of those events: `UNKNOWN`, `ACCUMULATION`, `MARKUP`, `DISTRIBUTION`, `MARKDOWN`
- **Higher-order, research-only labels** derived from the event/regime stream: regime transition markers, sequence-completion markers, and event-with-prior-regime context tags

It explicitly does **not**:

- Produce trade entries/exits, sizing, portfolio actions, or forecasts
- Use intraday data, indicators requiring higher frequency, or any data beyond daily OHLCV
- Detect a full “textbook” Wyckoff catalog (only the eight event codes above are in scope)
- Perform cross-asset or cross-symbol reasoning (each symbol is independent)

## 2. Inputs

**Required inputs (per symbol):**

- A time-ordered series of daily bars with: `date`, `open`, `high`, `low`, `close`, `volume`

**Preconditions and assumptions:**

- Bars are processed in strictly increasing `date` order (ties are undefined and must not occur).
- OHLC values are numeric and internally consistent (e.g., `low ≤ min(open, close) ≤ max(open, close) ≤ high`).
- `high > low` is required for any rule that depends on “close position within the bar”; if `high == low`, that bar cannot qualify for such events.
- Rolling standardization requires sufficient history; until required lookback windows are populated, standardized measures are undefined and event candidates that rely on them cannot trigger.
- The benchmarked research runs operate on a bounded recent-history window per symbol (a fixed lookback measured in calendar days). The event logic itself is defined on “the provided window”.

## 3. High-Level Algorithm Phases

1. **Normalize the daily bar stream** to ensure chronological processing and consistent field semantics.
2. **Compute relative-intensity measures** for price range expansion and volume expansion compared to recent history.
3. **Detect major climax candidates** (potential exhaustion points) and select/accept them under trend context.
4. **Anchor a structural range** using the first strong reaction after a climax, yielding a support or resistance reference.
5. **Detect range interactions** (springs / upthrusts) and range boundary resolutions (signs of strength / weakness).
6. **Convert event occurrences into a daily regime label** that persists until a new regime-setting event appears.
7. **Derive higher-order research labels** from the daily regime stream (transitions), from the event stream (sequences), and by attaching prior regime context to selected events.

## 4. Event Candidate Detection (Conceptual)

### Common derived measures (used across events)

- **Daily range**: absolute `high − low`
- **Close position within the bar**: `(close − low) / (high − low)` (undefined when `high == low`)
- **Standardized range expansion**: rolling z-score of daily range over a 40-bar trailing window
- **Standardized volume expansion**: rolling z-score of daily volume over a 40-bar trailing window
- **Trend context proxy**: slope of a 20-bar simple moving average of `close` (positive slope = rising, negative slope = falling)

Rolling z-scores use the trailing-window mean and standard deviation; if the trailing standard deviation is zero/undefined, the z-score is undefined for that bar.

### `SC` (Selling Climax)

- **Behavior targeted**: unusually wide-range, high-volume selling pressure that nevertheless closes off the low (capitulation-like bar).
- **Preconditions**:
  - Rolling range and volume standardizations are defined.
  - Trend context is defined (moving-average slope available).
- **Candidate rule**:
  - Standardized range expansion ≥ `2.0`
  - Standardized volume expansion ≥ `2.0`
  - Close position ≥ `0.5` (close in the upper half of the bar)
  - Trend context indicates a declining trend (moving-average slope < `0`)

### `BC` (Buying Climax)

- **Behavior targeted**: unusually wide-range, high-volume buying pressure that closes near the high (blow-off-like bar).
- **Preconditions**: same as `SC`.
- **Candidate rule**:
  - Standardized range expansion ≥ `2.0`
  - Standardized volume expansion ≥ `2.0`
  - Close position ≥ `0.6` (close in the upper portion of the bar)
  - Trend context indicates a rising trend (moving-average slope > `0`)

### `AR` (Automatic Reaction after `SC`)

- **Behavior targeted**: the first strong reflexive rebound following a selling climax.
- **Preconditions**:
  - An `SC` has already been accepted.
  - Standardized range expansion is defined.
- **Candidate rule** (searched in the first 19 bars after `SC`):
  - `close` > prior day `close` (an up day)
  - Standardized range expansion > `0.5`

### `AR_TOP` (Automatic Reaction after `BC`)

- **Behavior targeted**: the first strong reaction downward following a buying climax.
- **Preconditions**:
  - A `BC` has already been accepted.
  - Standardized range expansion is defined.
- **Candidate rule** (searched in the first 19 bars after `BC`):
  - `close` < prior day `close` (a down day)
  - Standardized range expansion > `0.5`

### Support and resistance references (range anchors)

- **Support reference** is defined only after `SC` followed by `AR`: the minimum `low` observed from `SC` through `AR` (inclusive).
- **Resistance reference** is defined only after `BC` followed by `AR_TOP`: the maximum `high` observed from `BC` through `AR_TOP` (inclusive).

### `SPRING`

- **Behavior targeted**: a downside “shakeout” below structural support that quickly re-enters the range and closes strong, with at least moderate volume expansion.
- **Preconditions**:
  - A support reference exists (requires `SC` then `AR`).
  - Standardized volume expansion is defined.
- **Candidate rule** (first accepted occurrence):
  - The bar’s `low` is at least `1%` below the support reference.
  - The bar’s close position ≥ `0.6`.
  - Standardized volume expansion ≥ `0.8`.
  - A re-entry confirmation exists: within `0–2` bars from the break bar (inclusive), there is a bar whose `close` is ≥ the support reference.
  - The event is **dated to the break bar** (the first bar whose `low` breaks support), even if the confirming re-entry close occurs on a subsequent bar.

### `UT` (Upthrust)

- **Behavior targeted**: an upside “shakeout” above structural resistance that quickly falls back into the range and closes weak.
- **Preconditions**:
  - A resistance reference exists (requires `BC` then `AR_TOP`).
  - Standardized range expansion is defined.
- **Candidate rule** (first accepted occurrence):
  - The bar’s `high` is at least `1%` above the resistance reference.
  - The bar’s close position ≤ `0.4`.
  - A re-entry confirmation exists: within `0–2` bars from the break bar (inclusive), there is a bar whose `close` is ≤ the resistance reference.
  - The event is **dated to the break bar**, even if the confirming re-entry close occurs on a subsequent bar.

### `SOS` (Sign of Strength)

- **Behavior targeted**: a decisive close above structural resistance accompanied by range expansion.
- **Preconditions**:
  - A resistance reference exists.
  - Standardized range expansion is defined.
- **Candidate rule** (first accepted occurrence):
  - `close` > resistance reference
  - Standardized range expansion ≥ `1.5`

### `SOW` (Sign of Weakness)

- **Behavior targeted**: a decisive close below structural support accompanied by range expansion.
- **Preconditions**:
  - A support reference exists.
  - Standardized range expansion is defined.
- **Candidate rule** (first accepted occurrence):
  - `close` < support reference
  - Standardized range expansion ≥ `1.5`

## 5. Path-Dependent Event Acceptance Rules

This research system benchmarks two acceptance behaviors that share the same candidate definitions but differ in **when** qualifying events are selected and how strictly chronology is enforced.

### 5.1 Shared structural dependencies (always true)

- `AR` can only occur if an `SC` has occurred.
- `AR_TOP` can only occur if a `BC` has occurred.
- `SPRING` and `SOW` can only occur after a support reference exists (requires `SC → AR`).
- `UT` and `SOS` can only occur after a resistance reference exists (requires `BC → AR_TOP`).
- Each of the eight event codes is emitted at most once per symbol within the analyzed history window.
- Event “scores” are standardized intensity measures:
  - `SC`, `BC`, `SPRING`: score = standardized **volume** expansion on the event bar
  - `AR`, `AR_TOP`, `SOS`, `SOW`, `UT`: score = standardized **range** expansion on the event bar

### 5.2 Scan-mode selection (non-path-dependent reference behavior)

This mode performs global selection within the provided history window:

- `SC` is chosen as the **most recent** bar in the window that satisfies the `SC` candidate rule.
- `BC` is chosen as the **most recent** bar in the window that satisfies the `BC` candidate rule.
- `AR` and `AR_TOP` are then chosen as the **first** qualifying reactions in the 19-bar post-climax search windows.
- Once a support/resistance reference is defined, `SPRING` / `UT` / `SOS` / `SOW` are searched and accepted using their candidate rules (first accepted occurrence under each definition).

Important consequence of global selection:

- Because support/resistance references are defined from events chosen using the full window, downstream events are not explicitly constrained to occur **after** the bars that defined those references. The resulting label stream is deterministic but not strictly causal.

### 5.3 Path-dependent selection (incremental, chronology-enforcing behavior)

This mode processes bars strictly forward in time and enforces a single-pass acceptance contract:

- Bars are evaluated sequentially; once an event is emitted it is never revised, re-scored, or re-timed.
- At most **one event** may be emitted per bar, using the following priority order:
  1. `SC`
  2. `BC`
  3. `AR`
  4. `AR_TOP`
  5. `SPRING`
  6. `UT`
  7. `SOS`
  8. `SOW`
- `AR` is only eligible during the 19-bar window immediately following `SC`. If it is not found by the end of that window, `AR` is permanently suppressed (and therefore support is never defined, suppressing `SPRING` and `SOW` as well).
- `AR_TOP` is only eligible during the 19-bar window immediately following `BC`. If it is not found by the end of that window, `AR_TOP` is permanently suppressed (and therefore resistance is never defined, suppressing `UT` and `SOS` as well).
- Once `AR` occurs, the support reference is fixed and never updated.
- Once `AR_TOP` occurs, the resistance reference is fixed and never updated.
- After the range anchor is established, range-dependent events are only eligible within a fixed horizon:
  - `SPRING` and `SOW` eligibility expires `1000` bars after `AR`.
  - `UT` and `SOS` eligibility expires `1000` bars after `AR_TOP`.
  - In the benchmarked bounded-history runs, this horizon is typically non-binding, but it remains part of the acceptance contract.
- `SPRING` and `UT` use a two-step acceptance:
  - The first bar that satisfies the break-bar conditions becomes a **pending** candidate.
  - The candidate is accepted only if a confirming re-entry close occurs within the next `0–2` bars (inclusive).
  - If no confirmation arrives within that horizon, the pending candidate is discarded and later break bars may be considered.
  - When accepted, the event is dated to the original break bar (not the confirming bar).

## 6. Regime Classification Logic

### Static regimes (daily labels)

Each day is assigned exactly one regime label, per symbol:

- Start in `UNKNOWN` at the beginning of the analyzed window.
- On any day with no regime-setting event, the prior day’s regime label persists.
- Only the following events are regime-setting:
  - `SC` or `SPRING` → `ACCUMULATION`
  - `SOS` → `MARKUP`
  - `BC` or `UT` → `DISTRIBUTION`
  - `SOW` → `MARKDOWN`
- If multiple regime-setting events occur on the same date, precedence is applied in this order (later items override earlier ones):
  1. `SC`
  2. `SPRING`
  3. `SOS`
  4. `BC`
  5. `UT`
  6. `SOW`

### Regime transitions (sparse change markers)

A “transition” is a separate, sparse label emitted only when:

- The regime changes from one day to the next, and
- The change is one of these allowed transitions:
  - `ACCUMULATION → MARKUP`
  - `MARKUP → DISTRIBUTION`
  - `DISTRIBUTION → MARKDOWN`
  - `MARKDOWN → ACCUMULATION`
and
- Both prior and new regimes are not `UNKNOWN`, and
- The prior regime lasted for at least `5` consecutive bars immediately before the change.

Transition markers are dated on the **first bar of the new regime**.

## 7. Context Qualification

Selected event types are enriched with immediate prior-regime context:

- Eligible events (default set): `SOS`, `SOW`, `BC`, `SPRING`
- For an eligible event on date `D`, compute `prior_regime` as the regime label from the immediately preceding bar in the daily regime stream (a 1-bar lookback).
- Context-qualified events are retained only when `prior_regime` is one of:
  - `ACCUMULATION`, `MARKUP`, `DISTRIBUTION`, `MARKDOWN`
  (`UNKNOWN` is excluded)

The resulting context-qualified label is represented as:

- Base event code (`event`), plus `prior_regime`, and/or
- A derived composite label of the form: `EVENT_after_PRIOR_REGIME`

This context materially alters interpretation because identical structural events are empirically observed (in benchmarked research summaries) to have meaningfully different forward-return distributions depending on the immediately preceding regime.

## 8. Sequence Resolution

Sequences are sparse “completion” labels emitted when ordered event patterns occur within a bounded time window.

**Input stream**:

- The per-symbol event stream (ordered chronologically by event date; ties broken deterministically by original event ordering on that date).

**Time constraint**:

- A sequence must complete within `30` calendar days of its first event (unless overridden per sequence).

**Defined sequence patterns (default set):**

- `SEQ_ACCUM_BREAKOUT`: `SC → AR → SPRING → SOS`
- `SEQ_DISTRIBUTION_TOP`: `BC → AR_TOP`
- `SEQ_MARKDOWN_START`: `BC → AR_TOP → SOW`
- `SEQ_RECOVERY`: `SOW → SC`
- `SEQ_FAILED_ACCUM` (special rule): `SC → AR → SPRING`, **with no** `SOS` occurring within the same time window after the `SC`

**Completion dating:**

- For standard patterns, the sequence completion is dated on the bar of the **final event** in the pattern.
- For `SEQ_FAILED_ACCUM`, completion is dated on the `SPRING` bar (the “attempt” completes when the spring occurs without a subsequent `SOS` in-window).

**Overlap rules:**

- Within a given sequence pattern, once a completion is recorded, the next search begins after the final matched event for that pattern (preventing overlapping completions of the same pattern).
- Different sequence patterns are detected independently and may overlap in time.

## 9. Outputs (Production Contract)

All outputs are per symbol and per day within the analyzed window, derived only from that symbol’s daily OHLCV.

### Primary outputs

1. **Structural event records (sparse)**
   - Each record contains:
     - `date` (the labeled bar date)
     - `event` (one of: `SC`, `BC`, `AR`, `AR_TOP`, `SPRING`, `UT`, `SOS`, `SOW`)
     - `score` (standardized intensity as defined in Section 5.1)
   - In path-dependent mode: at most one record per bar (priority-ordered).
   - Across the analyzed window: at most one record per event code.

2. **Daily regime label (dense)**
   - Each bar has exactly one `regime` label (Section 6).

### Derived/contextual labels (research-validated additions)

3. **Regime transition records (sparse)**
   - Each record contains:
     - `date` (first bar of new regime)
     - `transition` (e.g., `MARKDOWN->ACCUMULATION`)
     - `prior_regime`, `new_regime`

4. **Sequence completion records (sparse)**
   - Each record contains:
     - `date` (completion date per Section 8)
     - `sequence_id` (one of the defined sequence identifiers)

5. **Context-qualified event records (sparse subset)**
   - Each record contains:
     - `date`
     - `event`
     - `prior_regime`
   - A derived composite label `EVENT_after_PRIOR_REGIME` may be formed for downstream consumption.

## 10. Invariants & Guarantees

- **Deterministic content**: given identical daily OHLCV inputs, identical history windowing, and identical constants, the emitted labels and dates are deterministic.
- **Single-instance events**: within an analyzed window, each of the eight event codes is emitted at most once per symbol.
- **Hard prerequisites**: events that depend on a support/resistance reference can never occur without the prerequisite climax+reaction pair that defines that reference.
- **Bounded confirmation lookahead for `SPRING`/`UT`**: acceptance requires re-entry confirmation within 2 bars; the event is dated to the break bar but cannot be confirmed until the confirmation bar exists.
- **Regime persistence**: absent a regime-setting event, the regime label persists unchanged day-to-day.
- **Transition strictness**: transition markers only occur for the allowed cyclic transitions and only after a minimum prior-regime duration (5 bars).
- **No additional data**: all labels depend only on daily OHLCV for the same symbol (no fundamentals, no cross-asset inputs).

## 11. Explicit Non-Goals

- Detecting additional Wyckoff events beyond the implemented set (e.g., preliminary support/supply, secondary tests, last points of support/supply, UTAD, multi-phase schematics).
- Producing trade directives, position sizing, or risk management actions.
- Incorporating intraday structure, order flow, or volume-at-price.
- “Cycle completion” logic that reliably segments multiple full Wyckoff cycles within a long history window (the event set is single-instance per window by design).
