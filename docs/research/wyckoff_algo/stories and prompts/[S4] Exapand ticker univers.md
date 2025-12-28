Below is a single, copy-paste-ready Windsurf prompt.
It is written to minimize changes, preserve your existing raw detector and benchmark, and add universe mode, batching, and coverage CSVs exactly as discussed.

Do not modify wording when pasting into Windsurf.

⸻

WINDSURF PROMPT — Phase 1 All-Symbol Coverage Run

You are working inside the existing KapMan MVP repository at:

docs/research/wyckoff_algo/

Your task is to extend the existing raw Wyckoff detection + benchmark pipeline to support a full-universe coverage run, without altering the detector logic or benchmark math.

This is Phase 1: detector health validation, not signal tuning.

⸻

GOALS (STRICT)
	1.	Add a universe mode that loads all eligible symbols from the dev Postgres DB.
	2.	Add batching so the run scales to thousands of symbols safely.
	3.	Generate coverage CSV reports from raw events.
	4.	Reuse the existing raw detector and benchmark code unchanged.
	5.	Preserve existing watchlist behavior.

⸻

NON-GOALS (DO NOT DO)
	•	Do NOT change event detection logic.
	•	Do NOT change benchmark calculations.
	•	Do NOT add sequence logic or experiments.
	•	Do NOT fork or duplicate detector code.
	•	Do NOT break existing watchlist runs.

⸻

REQUIRED FUNCTIONALITY

1️⃣ Universe Mode (DB-Driven)

Add support for running without a watchlist file.

If config.yaml contains:

universe: all

Then:
	•	Query the dev DB (DATABASE_URL) for all symbols with:
	•	≥ min_days rows (default: 252)
	•	valid OHLCV in the last 2 years
	•	Symbols must be sorted deterministically (symbol ASC)

If watchlist is present, preserve existing behavior.

⸻

2️⃣ Batching

Add batching so symbols are processed incrementally.

Config options:

batch_size: 250
min_days: 252

Behavior:
	•	Process symbols in batches of batch_size
	•	Load OHLCV only for the current batch
	•	Append detected events incrementally to the raw output
	•	Batching must be restart-safe and deterministic

⸻

3️⃣ Raw Output (unchanged semantics)

Raw output location (existing):

docs/research/wyckoff_algo/outputs/raw/

Continue to write:
	•	events.parquet
	•	events.csv

Schema must remain compatible with existing benchmark code.

⸻

4️⃣ Coverage CSV Reports (NEW)

After raw detection completes, generate the following CSVs in:

docs/research/wyckoff_algo/outputs/raw/coverage/

A) Event coverage summary
File: event_coverage_summary.csv

Columns:
	•	event
	•	total_count
	•	symbols_with_event
	•	avg_events_per_symbol
	•	density (events / symbol / year)

⸻

B) Symbol event density
File: symbol_event_density.csv

Columns:
	•	symbol
	•	total_events
	•	events_per_year

⸻

C) Event spacing diagnostics
File: event_spacing_stats.csv

For each event type:
	•	min_gap_days
	•	median_gap_days
	•	p95_gap_days

(Gap = days between consecutive events of same type per symbol)

⸻

5️⃣ Benchmark (unchanged)

After raw detection:
	•	Run the existing benchmark harness
	•	Output baseline benchmark results exactly as before
	•	No experiment IDs, no filters, no renaming

⸻

CONFIG FILE UPDATE

Extend outputs/raw/config.yaml (or equivalent) to support:

universe: all        # or omit to use watchlist
watchlist: ../../data/watchlist_105.txt
batch_size: 250
min_days: 252


⸻

DELIVERABLES
	1.	Updated loader logic supporting universe: all
	2.	Batching implementation
	3.	Coverage CSV generation code
	4.	Zero changes to:
	•	event detection rules
	•	benchmark math
	•	experiment code

⸻

ACCEPTANCE CRITERIA
	•	Running raw pipeline with universe: all processes >1000 symbols successfully
	•	Coverage CSVs are generated and populated
	•	Benchmark results are produced
	•	Existing watchlist runs still work unchanged

⸻

IMPORTANT

This is a diagnostic scaling step.
Accuracy and determinism matter more than speed.

Do not refactor beyond what is explicitly requested.

⸻

End of prompt.

