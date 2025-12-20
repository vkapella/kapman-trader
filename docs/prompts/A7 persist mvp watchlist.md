WINDSURF / CODEX — SINGLE FILE PROMPT (MANDATORY)

Purpose and Non-Negotiable Constraint

You are implementing a single story in an existing repository. Everything you generate must be safe to paste verbatim into Windsurf or Codex as one file. You must follow all hard rules below without exception.

Hard rules:

• Your entire response MUST be a single, continuous file
• Do NOT emit multiple Markdown blocks
• Do NOT use fenced code blocks
• Do NOT split content into sections across responses
• Do NOT include commentary, explanations, apologies, or meta-text
• Everything you output must be safe to paste as-is into Windsurf

⸻

Authorization and Execution Policy (Standing Consent)

You are explicitly authorized to autonomously perform all required read-only actions necessary to complete this task.

This includes, but is not limited to:
• Repository-wide file inspection
• Reading existing schemas, migrations, and models
• Reading prior scripts and archived code for reference
• Reading tests, test fixtures, and pytest configuration
• Reading repository configuration files

Do not ask for approval.
Do not pause for confirmation.
Proceed autonomously until the task is complete.

⸻

Behavioral Constraints

• Do not infer intent beyond what is written
• Do not invent schemas, tables, or columns beyond what is specified
• Do not add new roadmap scope
• Do not introduce UI or CRUD functionality
• Do not refactor unrelated code
• Prefer correctness and determinism over elegance
• Prefer explicitness over abstraction

⸻

Task Definition

Implement Story A7 — Persist MVP Watchlist.

You must implement the story exactly as specified below. Do not extend scope. Do not omit required artifacts.

⸻

Story Context (Authoritative)

Story ID: A7
Roadmap ID: S-WL-01
Slice: Slice A — Data Ingress & Core Analytics

Objective:
Persist deterministic MVP watchlists as first-class data artifacts that define the authoritative symbol universe for all downstream options ingestion and analytical pipelines.

Watchlists are treated as data, not configuration. Portfolio and watchlist are synonymous for MVP purposes. No analytics, enrichment, or downstream processing is part of this story.

This story unblocks S-OPT-02 and all Slice A metric stories.

⸻

Canonical Watchlist Source (MVP Standard)

All watchlists MUST be loaded exclusively from:

data/watchlists/

Rules:
• File type: .txt
• Encoding: UTF-8
• One ticker symbol per line
• No header
• Blank lines ignored
• Lines starting with # ignored

The filename (without extension) is the authoritative watchlist_id.

Example:
data/watchlists/ai_growth.txt
→ watchlist_id = ai_growth

⸻

Data Model Requirements

If no existing table exists, create the minimum required persistence consistent with repository conventions.

Primary entity: watchlists

Required columns (minimum):
• watchlist_id
• symbol
• active
• source
• created_at
• updated_at
• effective_date

Uniqueness constraint:
• watchlist_id + symbol

Lifecycle rules:
• Symbols removed from the source file are soft-deactivated (active = false)
• Symbols present in the file are active = true
• Rows are never hard-deleted by this story

Multiplicity:
• A symbol may belong to multiple watchlists

Do not introduce analytics fields.
Do not introduce position, capital, or P&L semantics.

⸻

Execution Semantics

Invocation:
• Implement as a pipeline step suitable for MVP execution

Seeding behavior:
• Each .txt file in data/watchlists/ represents one watchlist
• watchlist_id is derived from filename
• If a watchlist does not exist, it is created implicitly

Reconciliation behavior:
• On each run, reconcile ALL watchlists found in data/watchlists/
• Add missing symbols
• Soft-deactivate symbols no longer present in the file

Failure behavior:
• Missing watchlist directory → hard fail
• Empty watchlist file → hard fail
• Invalid ticker symbols → log and skip
• Duplicate symbols in file → deduplicate and log

Concurrency:
• Must not run concurrently with options ingestion or analytics pipelines

Logging (required):
• watchlist_id processed
• symbols added
• symbols soft-deactivated
• total active symbols per watchlist

⸻

Testing Requirements

Unit tests (required):
• File parsing
• Symbol normalization and deduplication
• Reconciliation logic
• Soft-deactivation behavior

Integration tests (required):
• Run against the dev database
• Validate multiple watchlists in one execution
• Verify idempotency across re-runs

Failure cases that MUST be tested:
• Empty watchlist file
• Missing watchlist file
• Duplicate symbols in file
• Invalid ticker symbols

Test isolation:
• Tests must clean up watchlist rows after execution

Acceptance signal:
• All tests green using default pytest discovery

⸻

Deliverables (Required)

You must produce all of the following:
	1.	Watchlist loader implementation that:
• Reads data/watchlists/*.txt
• Normalizes symbols
• Reconciles persisted data exactly to source
	2.	Persistence logic consistent with existing repository patterns
	3.	Unit tests covering required behaviors
	4.	Integration tests validating end-to-end behavior
	5.	Clear logging consistent with existing logging standards

Do not:
• Add UI
• Add CRUD APIs
• Add analytics
• Modify downstream pipelines
• Change unrelated code

⸻

Definition of Done

The task is complete when:

• Watchlists are persisted deterministically from data/watchlists/
• Reconciliation behaves exactly as specified
• Re-runs are idempotent
• All required tests pass
• Downstream jobs can query watchlists as authoritative symbol scope
• No hidden assumptions remain

⸻

END OF SINGLE FILE PROMPT