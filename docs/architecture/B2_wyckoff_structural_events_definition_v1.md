Wyckoff Structural Events Definition v1 (B2)

Purpose
- Detect benchmark-aligned Wyckoff structural events from OHLCV history.
- Persist those events onto the existing daily snapshot surface and into a lightweight context-events table for downstream derivations.

Current module inputs
- `public.ohlcv`
- Existing `public.daily_snapshots` rows and their New York trading dates
- `core.metrics.structural.detect_structural_wyckoff`

Canonical event set
- `SC`
- `BC`
- `AR`
- `AR_TOP`
- `SPRING`
- `UT`
- `SOS`
- `SOW`

Persistence model
- B2 writes event outputs onto `public.daily_snapshots`:
  - `events_detected`
  - `primary_event`
  - `events_json`
- B2 also writes context rows to `public.wyckoff_context_events`:
  - `ticker_id`
  - `event_date`
  - `event_type`
  - `prior_regime`
  - `context_label`

Behavior
- B2 is driven by authoritative `daily_snapshots` date availability, not by prior B2 output.
- It refuses to run if any requested symbol/date snapshot coverage is incomplete.
- It validates OHLCV contiguity and skips symbols with empty, duplicate, non-monotonic, or excessively gapped histories.
- `primary_event` is the highest-score event for that day; `events_detected` retains the full sparse event set.

Operational assumptions
- B2 does not create synthetic snapshot dates.
- B2 persistence is deterministic and idempotent for identical upstream OHLCV and snapshot inputs.
- Downstream consumers should treat `daily_snapshots.events_detected` as the broadest event stream and `wyckoff_context_events` as a derived context surface, not a lossless replacement.
