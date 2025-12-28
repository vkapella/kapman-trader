You are working inside the KapMan repository.

GOAL
-----
Create a new Wyckoff experiment named:

    exp_spring_test_to_sos_entry_v1

This experiment tests whether SOS entries are higher quality when they occur after:
    SPRING → TEST → SOS
within the same Wyckoff base. This is intended to increase sample size vs SPRING→SOS,
while preserving structural integrity.

This is a RESEARCH experiment. Do NOT modify raw detectors, benchmark math, runner/loaders,
or baseline experiment code outside the new experiment directory.

DIRECTORY
---------
Create:

docs/research/wyckoff_algo/experiments/exp_spring_test_to_sos_entry_v1/

FILES TO CREATE (ONLY THESE)
----------------------------
1) config.yaml
2) filter.py
3) run.py
4) README.md

Reuse patterns from:
- docs/research/wyckoff_algo/experiments/exp_ar_to_sos_entry_v1
- docs/research/wyckoff_algo/experiments/exp_spring_to_sos_entry_v1
- docs/research/wyckoff_algo/experiments/baseline/run.py (for stable run structure)

Do NOT modify any other files.

--------------------------------------------------
1) config.yaml
--------------------------------------------------
Create config.yaml with:

experiment_id: exp_spring_test_to_sos_entry_v1

# Source raw detected events
source_events: ../../outputs/raw/events.parquet

# Sequencing rules (bar-based; fallback to event_date if bar_index missing)
spring_to_test_max_bars: 30
test_to_sos_max_bars: 30
spring_to_sos_max_bars: 80

# Event selection behavior
test_event_names: ["TEST"]          # Future-proof list
require_test: true
use_bc_invalidator: true

# Dedup behavior: for each SOS, match the nearest valid TEST and nearest valid SPRING before that TEST
match_strategy: "nearest_prior"     # documented behavior

--------------------------------------------------
2) filter.py
--------------------------------------------------
Implement:

apply_experiment(events_df: pd.DataFrame, ohlcv_by_symbol: dict, cfg: dict) -> pd.DataFrame

HARD REQUIREMENTS
-----------------
A) Preserve schema:
   - Do NOT rename identity column
   - Do NOT drop columns from accepted SOS rows
   - Return accepted SOS rows as copies of the original SOS rows

B) Dynamic identity column:
   - events_df may have 'symbol' OR 'ticker'
   - Determine id_col as:
        if "symbol" in columns -> "symbol"
        elif "ticker" in columns -> "ticker"
        else raise

C) Sequence logic:
   For each symbol/ticker group, sort by bar_index if present, else by event_date.

   For each SOS candidate:
     1) Find TEST events where:
        - event in test_event_names
        - TEST occurs before SOS
        - (SOS.bar_index - TEST.bar_index) <= test_to_sos_max_bars
     2) For the selected TEST (use nearest prior TEST to SOS):
        find SPRING events where:
        - event == "SPRING"
        - SPRING occurs before TEST
        - (TEST.bar_index - SPRING.bar_index) <= spring_to_test_max_bars
        - also enforce total window: (SOS.bar_index - SPRING.bar_index) <= spring_to_sos_max_bars
        - choose nearest prior SPRING to TEST

     3) If use_bc_invalidator is true:
        reject if any BC occurs strictly between SPRING and SOS inclusive of interior:
          SPRING.bar_index < BC.bar_index <= SOS.bar_index
        (BC after SPRING invalidates the base)

   If all constraints pass:
     - emit the SOS row (copy)
     - add ONLY these metadata columns:
         matched_spring_bar_index
         matched_spring_date
         matched_test_bar_index
         matched_test_date
         bars_since_spring
         bars_since_test

D) Output:
   Return DataFrame of accepted SOS rows.
   If zero rows, return an empty DataFrame with no special casing in filter (runner handles empty).

--------------------------------------------------
3) run.py
--------------------------------------------------
Create run.py by copying the proven “schema-safe” runner pattern used in your working experiment.

STRICT REQUIREMENTS
-------------------
- Must call load_ohlcv() with NO arguments
- Must load config.yaml and read experiment_id
- Must resolve source_events path relative to experiment directory
- Must dynamically resolve identity column for sorting CSV:
    id_col = "symbol" if present else "ticker"
- Must write outputs to:
    docs/research/wyckoff_algo/outputs/exp_spring_test_to_sos_entry_v1/
  using experiment_id in filenames:
    events_<experiment_id>.parquet
    events_<experiment_id>.csv
    benchmark_results_<experiment_id>.parquet
    benchmark_results_<experiment_id>.csv

- Must run benchmark:
    run_bench(events_path=events_out_parquet, output_path=bench_parquet)
  and then convert parquet -> csv

- If filtered is empty:
    log WARNING "No events produced for <experiment_id>. Exiting."
    return cleanly (exit 0)

Do NOT hard-code "symbol".
Do NOT change benchmark math.
Do NOT change raw detector outputs.

--------------------------------------------------
4) README.md
--------------------------------------------------
Create a short README.md describing:
- Purpose: SPRING → TEST → SOS
- Intuition: absorb, test, then show strength
- Config knobs and what they do (bar windows, BC invalidator)
- How to run:
    python docs/research/wyckoff_algo/experiments/exp_spring_test_to_sos_entry_v1/run.py
- What to look for:
    - signal_count > SPRING→SOS
    - 20-bar mean_return stays strong
    - MAE improves vs SPRING-only (or at least doesn’t worsen materially)

--------------------------------------------------
ACCEPTANCE CRITERIA
-------------------
1) New experiment directory exists with the four files.
2) Running the command produces experiment-named parquet + csv outputs (or exits cleanly with a warning).
3) No changes outside the experiment directory.
4) Output schema preserves the raw SOS row fields, plus only the approved metadata columns.

Proceed step-by-step and output complete file contents for all files.