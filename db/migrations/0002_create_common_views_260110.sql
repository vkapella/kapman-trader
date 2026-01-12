
  -- Create Wyckoff_Context_Events View 
create or replace view public.v_wyckoff_context_events as
select
  -- composite PK columns (these uniquely identify the row)
  e.ticker_id,
  t.symbol,
  e.event_date,
  e.event_type,
  e.prior_regime,

  -- payload
  e.context_label,

  -- optional: a single “key” field for BI convenience
  concat_ws('::',
    t.symbol,
    e.event_date::text,
    e.event_type,
    e.prior_regime
  ) as event_key
from public.wyckoff_context_events e
join public.tickers t
  on t.id = e.ticker_id;

  -- Create Wyckoff_Context_Regime_Transitions View 
create or replace view public.v_wyckoff_regime_transitions as
select
  r.ticker_id,
  t.symbol,
  r.date,
  r.prior_regime,
  r.new_regime,
  r.duration_bars,

  -- optional: convenience label for charts/tables
  (coalesce(r.prior_regime,'UNKNOWN') || ' → ' || r.new_regime) as transition_label
from public.wyckoff_regime_transitions r
join public.tickers t
  on t.id = r.ticker_id;

  -- Create Wyckoff_Context_Sequence_Events View 
create or replace view public.v_wyckoff_sequence_events as
select
  t.symbol,
  e.*
from public.wyckoff_sequence_events e
join public.tickers t
  on t.id = e.ticker_id;

  -- Create Wyckoff_Context_Sequences View 
create or replace view public.v_wyckoff_sequences as
select
  t.symbol,
  s.*
from public.wyckoff_sequences s
join public.tickers t
  on t.id = s.ticker_id;

  -- Create Wyckoff_Context_Snapshot_Evidence View 
create or replace view public.v_wyckoff_snapshot_evidence as
select
  t.symbol,
  se.*
from public.wyckoff_snapshot_evidence se
join public.tickers t
  on t.id = se.ticker_id;