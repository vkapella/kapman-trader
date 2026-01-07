CONTEXT CLAIM
-------------
Wyckoff regime: {{WYCKOFF_REGIME}}
Provided confidence: {{WYCKOFF_CONFIDENCE}}

INJECTED INPUT (CANONICAL JSON)
------------------------------
{{INJECTED_CONTEXT_JSON}}

TASK
----
Evaluate whether the claimed Wyckoff context is supported by the data.

Requirements:
- Use only the provided metrics and Wyckoff-derived data.
- Do not infer or synthesize missing data; treat nulls as neutral.
- Absence of sequences is neutral, not negative.
- Identify duplicative or low-signal metrics.

Return only valid JSON conforming exactly to the provided schema.
