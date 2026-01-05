CONTEXT CLAIM
-------------
Wyckoff regime: {{WYCKOFF_REGIME}}
Provided confidence: {{WYCKOFF_CONFIDENCE}}

DATA
----
{{FULL_SNAPSHOT_PAYLOAD_JSON}}

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

If evidence is weak or contradictory:
- Recommendations must reflect uncertainty or defensive positioning.

Return only valid JSON conforming exactly to the provided schema.