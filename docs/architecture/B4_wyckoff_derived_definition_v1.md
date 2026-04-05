Wyckoff Derived Objects Definition v1 (B4)

Purpose
- Persist higher-order derived Wyckoff objects from daily regime state and context events.
- Materialize regime transitions, legacy sequence completions, context-qualified events, and optional per-date evidence payloads.

Current module inputs
- `public.daily_snapshots.wyckoff_regime`
- `public.wyckoff_context_events`

Derived outputs
1) `public.wyckoff_regime_transitions`
   - Allowed regime changes only:
     - `ACCUMULATION -> MARKUP`
     - `MARKUP -> DISTRIBUTION`
     - `DISTRIBUTION -> MARKDOWN`
     - `MARKDOWN -> ACCUMULATION`
   - Prior regime must persist for at least 5 bars before transition persistence

2) Legacy sequence rows in `public.wyckoff_sequences`
   - `SEQ_ACCUM_BREAKOUT`
   - `SEQ_DISTRIBUTION_TOP`
   - `SEQ_MARKDOWN_START`
   - `SEQ_RECOVERY`
   - `SEQ_FAILED_ACCUM`

3) Derived context rows in `public.wyckoff_context_events`
   - Current module emits context labels only for:
     - `SOS`
     - `SOW`
     - `BC`
     - `SPRING`

4) Optional `public.wyckoff_snapshot_evidence`
   - Per-date JSON payload containing transitions, sequences, and context events when `include_evidence=True`

Behavior
- B4 reads context-event history and derives ordered legacy sequence completions using bounded pattern windows.
- B4 writes into the same `public.wyckoff_sequences` table later used by B4.1, but with a different `SEQ_*` vocabulary.
- Evidence writing is optional and controlled by the runner flag.

Operational assumptions
- B4 expects regime state from B1 and context events from B2 to already be present.
- Because B4 and B4.1 share `public.wyckoff_sequences`, downstream consumers must distinguish legacy `SEQ_*` rows from canonical B4.1 rows explicitly.
