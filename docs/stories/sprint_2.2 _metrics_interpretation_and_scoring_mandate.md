Sprint 2.2 – Metrics Interpretation & Scoring Mandate

1. Purpose

Sprint 2.2 converts raw, descriptive metrics produced in Sprint 2.1 into interpretive, decision-support intelligence.

Sprint 2.2 is where KapMan moves from:
	•	“What is happening in the market?”
to:
	•	“What does this imply for regime, setup quality, and action?”

This document locks the metric mandate for Sprint 2.2 and defines what is in scope, out of scope, and explicitly deferred.

⸻

2. Sprint 2.2 Core Responsibility (Canonical)

Sprint 2.2 derives, interprets, and scores signals from Sprint 2.1 metrics.

It does not ingest new market data.
It does not redefine metric calculations.

Sprint 2.2:
	•	Combines metrics
	•	Applies temporal context
	•	Computes directional and regime signals
	•	Produces scores and confidence measures

⸻

3. Inputs (Locked from Sprint 2.1)

Sprint 2.2 may only consume the following classes of inputs:

3.1 Technical Metrics
	•	RSI
	•	MACD
	•	ADX
	•	ATR
	•	Historical Volatility (HV)

3.2 Volatility & Options Metrics
	•	IV Rank
	•	IV Term Structure
	•	IV Skew
	•	Aggregate GEX
	•	DGCPI
	•	Gamma Flip
	•	Gamma Flip Distance %

3.3 Structural Context
	•	Wyckoff Phase (produced within Sprint 2.2)

No new raw metrics may be added without amending Sprint 2.1.

⸻

4. Derived Metrics (Sprint 2.2 Ownership)

The following metrics are explicitly Sprint 2.2 responsibilities.

4.1 Temporal Derivatives
	•	GEX Slope (3d / 5d / 10d)
	•	DGCPI Slope
	•	Volatility Regime Change (HV vs IV trends)

4.2 Regime Indicators
	•	Long-Gamma vs Short-Gamma Regime
	•	Trend vs Mean-Reversion Bias
	•	Volatility Expansion / Compression

⸻

5. Scoring & Weighting (Locked to Sprint 2.2)

Sprint 2.2 introduces composite scoring, using configurable weights such as:
	•	RSI
	•	ADX
	•	HV
	•	ATR
	•	IV Rank
	•	GEX / DGCPI
	•	IV Skew
	•	IV Term
	•	Gamma Flip Proximity

Weight values are:
	•	Externalized (config-driven)
	•	Versioned
	•	Not hard-coded into metric logic

⸻

6. Wyckoff Integration

Sprint 2.2 is the first sprint allowed to reference Wyckoff concepts.

In Scope
	•	Wyckoff Phase detection
	•	Phase confidence scoring
	•	Alignment of metrics to phase context

Out of Scope
	•	Trade execution
	•	Position sizing
	•	Portfolio constraints

⸻

7. Minimum Required vs Desirable Signals

Minimum Required (MVP-Blocking)
	•	RSI
	•	ADX
	•	MACD
	•	IV Rank
	•	Aggregate GEX
	•	Wyckoff Phase

Highly Desirable (Full Fidelity)
	•	HV
	•	ATR
	•	Gamma Flip
	•	DGCPI
	•	Trend Strength
	•	Phase Confidence
	•	Delta / OI context

Optional Enhancements (Post-MVP)
	•	Sector context
	•	Gamma Alignment Index
	•	POP (Probability of Profit)

⸻

8. Explicit Non-Goals

Sprint 2.2 does not:
	•	Recompute base metrics
	•	Introduce intraday logic
	•	Perform backtesting
	•	Generate executable trades
	•	Optimize strategy parameters

⸻

9. Sprint 2.2 Exit Criteria

Sprint 2.2 is complete when:
	•	Composite scores are produced deterministically
	•	Wyckoff phase and confidence are computed
	•	Derived metrics (e.g., GEX slope) are stable
	•	Scores are explainable and auditable
	•	No Sprint 2.1 logic is modified

⸻

Status: LOCKED