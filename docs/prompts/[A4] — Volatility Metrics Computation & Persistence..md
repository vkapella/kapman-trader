WINDSURF / CODEX — SINGLE FILE PROMPT (MANDATORY)

Purpose and Non-Negotiable Constraint

You are generating content that will be copied verbatim into Windsurf or Codex as a single file.

Hard rules:
	•	Your entire response MUST be a single, continuous file
	•	Do NOT emit multiple Markdown blocks
	•	Do NOT use fenced code blocks
	•	Do NOT split content into sections across responses
	•	Do NOT include commentary, explanations, apologies, or meta-text
	•	Everything you output must be safe to paste as-is into Windsurf

⸻

Authorization and Execution Policy (Standing Consent)

You are explicitly authorized to autonomously perform all required read-only actions necessary to complete any task defined in this prompt.

This authorization includes, but is not limited to:
	•	Repository-wide file inspection
	•	Repository-wide issue enumeration
	•	Pagination across GitHub API results
	•	Retrieval of issue bodies, metadata, labels, milestones, and assignees
	•	Reading commit history, pull requests, and repository configuration files

No additional user confirmation is required for these actions.
Do not pause to request approval.
Do not ask follow-up questions about authorization.
Proceed autonomously until the task is fully complete.

This authorization applies for the full duration of the task.

⸻

Output Format Rules (Absolute)
	1.	Produce exactly one file
	2.	Use plain Markdown only
	3.	Do NOT use triple backticks or fenced code blocks
	4.	Do NOT split content into multiple logical outputs
	5.	Do NOT label any section as “code” or “markdown”
	6.	Do NOT prepend or append explanations outside the file content

⸻

Behavioral Constraints
	•	Do not infer intent beyond explicit instructions
	•	Do not invent data
	•	Do not summarize unless explicitly asked
	•	Do not omit required artifacts
	•	Preserve original formatting when extracting text
	•	Prefer completeness over brevity

⸻

Model Guidance

Target model: GPT-5.1-mini
Reasoning level: medium
Primary optimization goals: correctness, determinism, architectural consistency with existing KapMan modules (A2, A3), and minimal CLI surface area.
Do not introduce abstractions, flags, or patterns that are not already established in the repository unless explicitly instructed.

⸻

Task Definition

You are implementing KapMan Story [A4] — Volatility Metrics Computation & Persistence.

You must implement this story exactly as planned in the Story Planning Wizard, with no scope expansion and no deviation from established KapMan conventions.

Your responsibilities include all of the following:
	1.	Repository Context Assimilation
	•	Inspect the repository to understand existing patterns used by:
	•	scripts/run_a2_local_ta.py
	•	scripts/run_a3_dealer_metrics.py
	•	kapman.metrics.volatility_metrics.py
	•	kapman DB helpers used for daily_snapshots upserts
	•	Treat existing A2/A3 behavior as authoritative precedent.
	2.	Script Entrypoint Creation
	•	Create scripts/run_a4_volatility_metrics.py.
	•	CLI flags must be strictly limited to:
	•	–db-url
	•	–date
	•	–start-date
	•	–end-date
	•	–fill-missing
	•	–verbose
	•	–debug
	•	–quiet
	•	–heartbeat
	•	No analytical, tuning, or metric-selection flags are permitted.
	•	Date resolution, watchlist resolution, logging, and heartbeat behavior must match A2/A3.
	3.	Metric Computation
	•	Use kapman.metrics.volatility_metrics.py as the single source of truth.
	•	Do not reimplement or duplicate metric logic.
	•	Compute and persist all metrics produced by that module, including:
	•	avg_iv
	•	avg_call_iv
	•	avg_put_iv
	•	iv_stddev
	•	iv_skew_call_put
	•	put_call_oi_ratio
	•	put_call_volume_ratio
	•	iv_percentile
	•	iv_rank
	•	front_month_iv
	•	back_month_iv
	•	iv_term_structure_slope
	•	Pass required inputs (eligible options data and historical avg_iv series) explicitly.
	4.	Persistence Contract
	•	Persist results into daily_snapshots.volatility_metrics_json.
	•	Do not modify any other daily_snapshots columns.
	•	Upserts must be idempotent.
	•	Respect –fill-missing semantics exactly as A2/A3.
	5.	Metadata, Status, and Versioning
	•	Populate metadata with ticker_id, symbol, snapshot_date, effective_options_time, counts, and processing_status.
	•	Populate diagnostics array on non-success paths.
	•	Compute deterministic confidence (high/medium/low) based on contract coverage and data quality.
	•	Set model_version deterministically using the format:
a4-volatility-metrics@<git_sha_or_version>
	6.	Orchestration Compatibility
	•	Ensure A4 runs cleanly as part of the A5 deterministic rebuild without special casing.
	•	Do not introduce new orchestration entrypoints.
	7.	Tests
	•	Add unit tests under tests/unit/metrics/test_volatility_metrics.py covering each metric family and edge cases.
	•	Add integration tests under tests/integration/test_a4_volatility_metrics.py validating persistence, idempotency, and failure handling.
	•	Follow existing A3 testing conventions.
	8.	Constraints
	•	Do not add new CLI flags.
	•	Do not add new metrics.
	•	Do not change volatility metric definitions.
	•	Do not introduce forecasting, signaling, or UI concerns.
	•	Do not refactor unrelated code.

Produce all required files and modifications necessary to fully implement and close Story A4.

Proceed autonomously until the task is complete.

⸻

END OF SINGLE FILE PROMPT