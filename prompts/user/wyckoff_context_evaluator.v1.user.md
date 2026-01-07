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

Then:
- Identify which metrics support the context and which contradict it.
- Assign relative weights to each metric.
- Score the overall strength of evidence.
- Conditionally propose:
  • One primary option strategy
  • Two alternative strategies

Requirements:
- Recommendations must use only contracts from option_chain_snapshot.
- Each strategy must include entry_reference, stop_loss, profit_target, confidence_score, and time_horizon.
- Include meta.option_chain_hash exactly as provided in the injected input.

If evidence is weak or contradictory:
- Recommendations must reflect uncertainty or defensive positioning.

Return only valid JSON conforming exactly to the provided schema.
