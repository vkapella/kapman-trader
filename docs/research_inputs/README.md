
IMPORTANT:
No production code under core/, api/, or runtime services may import from docs/research_inputs/.
This directory exists solely to inform roadmap intent, story acceptance criteria, and design decisions.

Promotion from research_inputs/ to production occurs only via:
explicit roadmap items, and
re-implementation against validated acceptance criteria (never direct reuse).



File-by-File Alignment Review

0. 00_MVP-output-12-30-25.md
This is your behavioral truth for wyckoff stories: the validated algorithmic behavior that has already demonstrated signal quality and constraints. It is not production code; it is a reference contract.

1. chatgpt_wyckoff_gpt_explanation_of_dealer_metrics.md
Status: 🟡 Later-phase conceptual reference
Alignment: Good, but not MVP-critical
Why
Explains why dealer metrics matter
Helps inform Layer-2 / Layer-3 decisions (timing, expression)
Does not conflict with current Wyckoff framing
Action
Keep in docs/research_inputs/
Do not reference in Wyckoff stories
This belongs to Options / Dealer Layer stories later
2. claude-kapman-trader-architecture-prompt-v1.0.md
Status: 🟡 Later-phase architectural reference
Why
Broad system-level thinking
Useful when you formalize:
Backstage integration
Service boundaries
Over-scoped for MVP
Action
Keep
Mark mentally as architecture inspiration, not spec
3. KapMan_Deterministic_Schematic_Rules_v2.2.md
Status: ❌ Superseded (important to archive explicitly)
Why
Encodes deterministic decision logic
Collapses structure → action directly
Conflicts with your new layered, probabilistic framing
This is the old KapMan brain.
Action (strongly recommended)
Move to:
docs/archive/research_legacy/
Add header note:
Superseded by layered, probabilistic decision architecture (Dec 2025)
This removes conceptual gravity.
4. KapMan_Options_Analyzer_v2.18_Core_Spec.md
Status: 🟡 Valuable, but post-Wyckoff MVP
Why
This is expression logic
Assumes an upstream context provider (which Wyckoff now is)
Still very relevant — just not yet
Correct placement in the roadmap
This becomes a consumer of Wyckoff output
It should never back-propagate requirements into Wyckoff
Action
Keep
Explicitly defer to a later epic (Options Strategy Engine)
5. metric_weights.json
Status: 🟡 Later-phase tuning artifact
Why
Encodes preferences, not structure
Weights imply optimization and scoring
MVP Wyckoff must remain weight-free
Action
Keep as reference only
Do not port into MVP code
Will matter once you build scoring layers
6. structural_phases_v1.json
Status: ✅ MVP-aligned as a taxonomy seed
Why
Defines labels, not decisions
Helps ensure semantic consistency
Does not enforce behavior
Important constraint
Treat this as naming input, not logic
MVP code should still compute states, not lookup them
Action
Reference only for naming consistency when drafting schemas and enums
Do not import directly into production yet
7. wyckoff_config.json
Status: 🟡 Partial MVP relevance
Why
Some thresholds may still be relevant
But this file blends:
Research assumptions
Tunable parameters
Implicit policy
Action
Treat as a parameter sketch
MVP stories should define which parameters exist, not their values
8. Python Files
(structural.py, phase.py, scoring.py, models.py, dealer_metrics.py, volatility_metrics.py, checklist.py)
Status: ⚠️ Dangerous if misused (research prototypes)
Why
These look production-ready but are not:
No contracts
No versioning
No benchmark traceability
They encode implicit decisions
Correct mental model
These are thinking tools, not building blocks.
Action
Leave in research_inputs/
Add a README guardrail (if not already done)
Re-implement concepts cleanly later, never import
Alignment with Current MVP (Bottom Line)
What the MVP Wyckoff slice should consume from this archive:
Taxonomy ideas (phases, regimes)
Conceptual framing (structure vs expression)
Benchmark results (your fast bench output)
What it must NOT consume:
Deterministic rules
Weights
Scoring engines
Option logic
Dealer logic