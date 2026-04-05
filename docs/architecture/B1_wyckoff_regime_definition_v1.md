Wyckoff Regime Definition v1 (B1)

Purpose
- Persist deterministic, path-dependent daily Wyckoff regime state onto existing `public.daily_snapshots` rows.
- Convert sparse B2 structural events into a continuous daily regime series for downstream consumers.

Current module inputs
- `public.daily_snapshots.events_detected`
- Existing `public.daily_snapshots` rows for the target symbol/date range
- OHLCV date coverage from `public.ohlcv`

Regime states
- `UNKNOWN`
- `ACCUMULATION`
- `MARKUP`
- `DISTRIBUTION`
- `MARKDOWN`

Regime-setting events and precedence
- `SC` -> `ACCUMULATION`
- `SPRING` -> `ACCUMULATION`
- `SOS` -> `MARKUP`
- `BC` -> `DISTRIBUTION`
- `UT` -> `DISTRIBUTION`
- `SOW` -> `MARKDOWN`
- Same-day precedence is fixed: `SC`, `SPRING`, `SOS`, `BC`, `UT`, `SOW`

Persistence model
- B1 updates existing `public.daily_snapshots` rows only.
- It writes:
  - `wyckoff_regime`
  - `wyckoff_regime_confidence`
  - `wyckoff_regime_set_by_event`
- It does not create new tables.

Behavior
- The reducer is a single forward pass per symbol.
- On days with no regime-setting event, the prior regime is carried forward unchanged.
- Confidence is currently `1.0` on regime-setting days and otherwise carried forward with the prior state.

Operational assumptions
- B1 assumes upstream `daily_snapshots` rows already exist for the target symbol/date range.
- Duplicate rows for the same ticker/date may exist because persistence keys on `(time, ticker_id)`, not `(date, ticker_id)`.
- Downstream jobs that reason per-date should normalize or deduplicate same-date snapshot rows explicitly.
