# Experiment: SPRING → TEST → SOS (exp_spring_test_to_sos_entry_v1)

- Purpose: evaluate SOS entries only when a SPRING is followed by a TEST before the SOS within a bounded window.
- Intuition: price springs, tests supply (TEST), then shows strength (SOS); sequence aims to improve reliability and sample size versus SPRING→SOS alone.
- Config knobs: `spring_to_test_max_bars`, `test_to_sos_max_bars`, `spring_to_sos_max_bars`, optional `use_bc_invalidator` to drop bases with BC between SPRING and SOS.
- Test events are configurable via `test_event_names` (default ["TEST"]); nearest-prior matching strategy.
- How to run: `python docs/research/wyckoff_algo/experiments/exp_spring_test_to_sos_entry_v1/run.py`
- What to look for: higher signal_count than SPRING→SOS, strong 20-bar mean_return, and MAE that does not materially worsen versus SPRING-only or SPRING→SOS.
