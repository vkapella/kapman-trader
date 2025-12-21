Windsurf Prompt — A2 Pattern Flag + Runtime Instrumentation + Run Header

Context
You are modifying the KapMan MVP A2 Local TA + price metric batch job.

This task is observability + execution control only.

The authoritative indicator contract is defined in:

docs/reference/ta_indicator_surface.py

Do not change schemas, JSON shapes, indicator math, persistence semantics, or introduce parallelism.

⸻

Objectives

Add three tightly-scoped capabilities to the A2 batch job:
	1.	A runtime flag to explicitly enable pattern-recognition (CDL) indicators*
	2.	Lightweight runtime timing instrumentation to measure performance impact
	3.	A single startup header block that documents the execution plan and flags

These changes are required to:
	•	Measure runtime impact of pattern indicators
	•	Eliminate ambiguity when reviewing logs
	•	Prepare for future chunking / parallel hydration work

⸻

1. New CLI Flag — Pattern Indicators

Add to scripts/run_a2_local_ta.py

Add a new flag:

--enable-pattern-indicators

Required behavior

Default (flag NOT provided):
	•	Pattern indicators are disabled
	•	No TA-Lib imports or CDL computations attempted
	•	Pattern indicator JSON keys are still emitted
	•	All pattern indicator values are NULL

When flag IS provided:
	•	Pattern indicators are attempted
	•	If TA-Lib backend is unavailable:
	•	Do not fail
	•	Emit NULL values
	•	Log once that backend is unavailable

Execution semantics (important)

The flag must gate execution only, not schema or JSON shape.

if enable_pattern_indicators and pattern_backend_available:
    compute_pattern_indicators()
else:
    emit_null_pattern_indicators()

technical_indicators_json["pattern_recognition"] must always exist.

⸻

2. Runtime Timing Instrumentation

Add lightweight timing (no profilers) to capture:
	•	Time spent computing technical indicators
	•	Time spent computing pattern indicators

Add the following to the A2 SUMMARY block:

technical_indicator_time_sec: <float>
pattern_indicator_time_sec: <float>

Rules:
	•	If pattern indicators are disabled → pattern_indicator_time_sec = 0.0
	•	Timing must exclude DB writes
	•	Use simple wall-clock timers

⸻

3. Startup Header / Run Manifest Block

At the very start of the run, before any computation or progress logging, emit exactly one structured header block at INFO level.

Prefix every line with:

[A2] RUN CONFIG


⸻

3.1 Snapshot scope

After CLI parsing, log the resolved scope:

[A2] RUN CONFIG snapshot_mode=single_date
[A2] RUN CONFIG date=YYYY-MM-DD
[A2] RUN CONFIG fill_missing=true|false

or for ranges:

[A2] RUN CONFIG snapshot_mode=date_range
[A2] RUN CONFIG start_date=YYYY-MM-DD
[A2] RUN CONFIG end_date=YYYY-MM-DD
[A2] RUN CONFIG fill_missing=true|false


⸻

3.2 Indicator execution plan

Technical indicators

[A2] RUN CONFIG technical_indicators=enabled
[A2] RUN CONFIG technical_indicator_categories=[momentum, trend, volatility, volume, others]
[A2] RUN CONFIG technical_indicator_count=<int>

The count must come from the authoritative indicator surface.

⸻

Price metrics

[A2] RUN CONFIG price_metrics=enabled
[A2] RUN CONFIG price_metrics_list=[rvol, vsi, hv]


⸻

Pattern recognition indicators
Log enablement, backend availability, and reason:

[A2] RUN CONFIG pattern_indicators_enabled=true|false
[A2] RUN CONFIG pattern_backend_available=true|false
[A2] RUN CONFIG pattern_indicator_count=<int>
[A2] RUN CONFIG pattern_indicators_reason=enabled|disabled_by_flag|backend_unavailable


⸻

3.3 Flags and execution options

Log all relevant flags, even if defaulted:

[A2] RUN CONFIG flags:
[A2] RUN CONFIG   enable_pattern_indicators=false
[A2] RUN CONFIG   verbose=false
[A2] RUN CONFIG   log_heartbeat_interval=50

Include any option that materially affects behavior or output.

⸻

3.4 Determinism and versioning

Always log:

[A2] RUN CONFIG model_version=<model_version_string>
[A2] RUN CONFIG deterministic=true


⸻

4. Summary Enhancements (end of run)

Extend the existing A2 SUMMARY block with:

pattern_indicators_enabled: true|false
pattern_backend_available: true|false
pattern_indicators_attempted: <int>
pattern_indicators_present: <int>
technical_indicator_time_sec: <float>
pattern_indicator_time_sec: <float>

Definitions:
	•	attempted = number of CDL indicators evaluated
	•	present = number of non-NULL pattern outputs

⸻

Constraints (Do NOT violate)
	•	❌ No schema changes
	•	❌ No JSON shape changes
	•	❌ No indicator math changes
	•	❌ No new dependencies
	•	❌ No parallelism
	•	❌ No refactors outside A2

This must be a surgical, additive change.

⸻

Acceptance Criteria
	•	Running A2 without the flag:
	•	Pattern indicators skipped
	•	Clear header explains why
	•	Runtime decreases measurably
	•	Running A2 with the flag:
	•	Pattern indicators attempted
	•	Graceful NULLs if TA-Lib missing
	•	Header block appears once per run, before progress logs
	•	Summary clearly reports timing and indicator status
	•	CI and all existing tests pass unchanged

⸻

End of Prompt

⸻

What this gives you immediately

After landing this:
	1.	You can run two comparable benchmarks (patterns off vs on)
	2.	You get clean per-component timing
	3.	You get an explicit execution manifest for every run
	4.	You’ll have the exact data needed to design:
	•	chunk sizes
	•	worker counts
	•	parent-writer vs worker-writer strategies

Once you run the next 12/5/25 job with this in place, paste the new SUMMARY + header and we can quantitatively design A2.1 parallel hydration instead of guessing.