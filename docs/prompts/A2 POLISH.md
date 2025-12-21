IMPLEMENTATION PROMPT — A2 POLISH

Warning Suppression, Heartbeat, Verbosity, and Batch Summary

You are modifying the existing A2 Local TA batch job to improve operational usability and signal quality.
You are not changing metric logic, schemas, or outputs.

⸻

GOALS (NON-NEGOTIABLE)
	1.	Suppress expected numerical warnings from pandas / numpy / ta
	2.	Preserve true exceptions (do not blanket-silence errors)
	3.	Add heartbeat / progress logging
	4.	Emit batch summary statistics on completion
	5.	Add CLI verbosity flags
	6.	Ensure --help prints all supported flags

⸻

WHAT YOU MUST NOT CHANGE
	•	Indicator surface
	•	Metric formulas
	•	NULL semantics
	•	Database schema
	•	Idempotent behavior
	•	Tests that validate metric correctness

⸻

PART 1 — WARNING SUPPRESSION (REQUIRED)

Problem

Indicators such as ADX / DI+/DI− emit unavoidable warnings like:

RuntimeWarning: invalid value encountered in scalar divide

These are expected and already handled via NULL outputs.

Fix (do exactly this)

Wrap all indicator computation in both:
	•	warnings.catch_warnings
	•	numpy.errstate

Implementation pattern
In core/metrics/a2_local_ta_job.py, at the point where indicators are computed:

import warnings
import numpy as np

Wrap calls to compute_indicator_latest(...) like this:

with warnings.catch_warnings():
    warnings.simplefilter("ignore", RuntimeWarning)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = surface.compute_indicator_latest(ohlcv, category, name)

Rules:
	•	Suppress only RuntimeWarning
	•	Do not catch Exception
	•	Any real exception must still bubble or be handled explicitly

⸻

PART 2 — HEARTBEAT / PROGRESS LOGGING

Objective

Allow the operator to know the job is alive during long runs.

Required behavior

Emit a heartbeat log every N tickers, configurable via flag.

Default:
	•	Every 50 tickers

Example log (INFO level):

[A2] progress snapshot_date=2025-12-05 processed=150/1234 elapsed=00:02:31

Implementation

Track:
	•	Total tickers
	•	Tickers processed
	•	Start time

Use time.monotonic() for elapsed time.

⸻

PART 3 — BATCH SUMMARY STATISTICS (MANDATORY)

At the end of each run (per invocation), emit a single summary block.

Required stats

At minimum:
	•	snapshot_date(s) processed
	•	tickers_processed
	•	snapshots_written
	•	indicators_computed_total
	•	indicators_null_total
	•	pattern_indicators_present (count)
	•	duration_seconds

Example output

[A2] SUMMARY
  dates: 2025-12-05
  tickers: 1234
  snapshots_written: 1234
  indicators_computed: 98720
  indicators_null: 14312
  pattern_indicators_present: 0
  duration_sec: 183.4


⸻

PART 4 — VERBOSITY FLAGS (CLI)

Extend scripts/run_a2_local_ta.py using argparse.

Required flags

Flag	Behavior
--verbose	INFO-level per-ticker logging
--debug	DEBUG-level indicator-level logging
--heartbeat N	Emit progress every N tickers
--quiet	Only warnings + final summary

Rules:
	•	--debug implies --verbose
	•	--quiet overrides others
	•	Default = normal INFO + heartbeat

⸻

PART 5 — HELP MODE (REQUIRED)

Your script must support:

python scripts/run_a2_local_ta.py --help

Output must list all flags, including:
	•	date / start-date / end-date
	•	fill-missing
	•	verbose / debug / quiet
	•	heartbeat

Do not custom-print help; rely on argparse.

⸻

PART 6 — LOGGING RULES
	•	Use the existing logging framework
	•	Do not print directly to stdout
	•	Heartbeats = INFO
	•	Summary = INFO
	•	Indicator failures (unexpected) = WARN
	•	Debug flag enables per-indicator detail

⸻

PART 7 — TESTING REQUIREMENTS

You must:
	•	Add or adjust unit tests to ensure:
	•	Warning suppression does not alter outputs
	•	Summary stats are emitted
	•	Do not assert on exact log text
	•	Assert presence / counts only

No integration tests required for logging.

⸻

SUCCESS CRITERIA

After implementation:

PYTHONPATH=. python scripts/run_a2_local_ta.py --date 2025-12-05

	•	No warning spam
	•	Periodic progress logs
	•	Final summary printed
	•	Identical database output as before

⸻

FINAL INSTRUCTION

Implement only the above changes.
Do not refactor unrelated code.

When finished:
	•	Run pytest
	•	Commit with message:

A2: suppress expected TA warnings, add heartbeat, verbosity, and batch summary



Begin implementation now.