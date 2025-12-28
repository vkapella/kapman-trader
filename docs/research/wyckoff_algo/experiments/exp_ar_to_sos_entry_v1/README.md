# Experiment: AR → SOS Entry (exp_ar_to_sos_entry_v1)

- Wyckoff rationale: SOS strength often follows an Automatic Rally; this sequence tests whether confirming demand improves entry quality.
- Sequence-conditioned: SOS is emitted only when an AR occurred within the configured bar window; no SOS-only signals.
- Comparison targets: SOS baseline (event-only) and AR baseline to gauge incremental value of the AR → SOS sequence.
- BC invalidation: optional guard to drop SOS if a Buying Climax appears between AR and SOS.
- Candidate long entry: direction/role remain UP/ENTRY; detection math is unchanged.
- Uses raw detector output; benchmark math, loaders, and horizons are unchanged.
