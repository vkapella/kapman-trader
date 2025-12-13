# KapMan Deterministic Schematic Rules (v2.2 – Context-Aware + Taxonomy Edition)

## 🧩 Purpose
Version 2.2 extends v2.1 by:
- Adding a **taxonomy** that distinguishes between classical Wyckoff phases and modern quantitative overlays.
- Introducing **visual legends and flags** to clarify counter-intuitive or hybrid contexts.
- Embedding a chart legend for automatic labeling of both structural and quantitative states.

---

## ⚙️ Overview
- Uses 200-bar Polygon OHLCV data.
- Detects local pivot highs/lows.
- Computes RSI(14), ADX(14), HV(20) for context.
- Classifies phase by deterministic rule-set.
- Adds extended context flags (B↑, C✕, D▭, E↓, HV-Divergent, Dealer Compression, Time-Compressed).
- Produces labeled schematic with visual legend.

---

## 🧮 Context-Aware Phase Detection Rules

```json
{
  "PhaseA": { "criteria": { "rsi_rsi": "<35", "hv_sigma": ">1.2", "adx_ADX_14": "<20" }, "description": "Stopping Action" },
  "PhaseB": { "criteria": { "rsi_rsi": "35–55", "adx_ADX_14": "<25", "hv_sigma": "<1.0" }, "description": "Range / Accumulation" },
  "PhaseC": { "criteria": { "rsi_delta": ">10", "adx_ADX_14": "20–30", "hv_sigma": ">1.0" }, "description": "Spring / Test" },
  "PhaseD": { "criteria": { "rsi_rsi": ">60", "adx_ADX_14": ">30", "hv_sigma": "0.8–1.3" }, "description": "Expansion / Trend" },
  "PhaseE": { "criteria": { "rsi_divergence": true, "hv_sigma": ">1.5", "adx_ADX_14": "<25" }, "description": "Distribution / Exhaustion" }
}
```

---

## 🧩 Extended Context Flags

| Flag | Trigger Condition | Meaning | Classification |
|------|--------------------|----------|----------------|
| **B↑ – Range Drift** | ADX < 25 and RSI 50–60 | Upward drift within Phase B | Classical-Compatible |
| **C✕ – Failed Spring** | HV > 1.2 and RSI < 45 after breakout | Unconfirmed test | Classical-Compatible |
| **D▭ – Trend Pause** | ADX > 25 and RSI > 60 but flat price | Reaccumulation pause | Classical-Compatible |
| **E↓ – Reactive Bounce** | RSI > 55 in Phase E, ADX < 20 | Counter-trend rally in distribution | Classical-Compatible |
| **HV-Divergent** | HV > 1.5 and range < 5% of ATR | Volatility expansion without price | Quantitative Extension |
| **Dealer Compression** | Price within ±1% Gamma Flip | Hedging pressure zone | Quantitative Extension |
| **Time-Compressed** | Sum of 3 phases < 15% of 200-bar window | Cycle duration compressed | Quantitative Extension |

---

## 🧭 Taxonomy Summary

| Category | Includes | Origin | Display Type |
|-----------|-----------|---------|---------------|
| **Structural (Classical Wyckoff)** | A–E | Canonical | Bold labels, primary color shading |
| **Extended Structural** | B↑, C✕, D▭, E↓ | Modern, classical-compatible | Dashed shading + arrow annotations |
| **Quantitative Overlays** | HV-Divergent, Dealer Compression, Time-Compressed | Modern (non-Wyckoff) | Grey/magenta overlay bands |

---

## 🧾 Visual Legend for Charts

| Symbol / Color | Meaning |
|----------------|----------|
| **Red** | Phase A – Stopping Action |
| **Orange** | Phase B – Accumulation |
| **Blue** | Phase C – Spring/Test |
| **Green** | Phase D – Expansion |
| **Purple** | Phase E – Distribution |
| **↑ Arrow (Orange)** | B↑ – Range Drift |
| **✕ (Blue)** | C✕ – Failed Spring |
| **▭ (Green)** | D▭ – Trend Pause |
| **↓ Arrow (Purple)** | E↓ – Reactive Bounce |
| **Grey Stripe** | HV-Divergent (volatility mirage) |
| **Magenta Dotted Band** | Dealer Compression Zone |
| **⚠ Tag** | Time-Compressed Phase Sequence |

---

## 📊 Rendering Logic (Legend Integration)

1. Draw structural phases (A–E) using standard shading colors.
2. Overlay extended flags where criteria met.
3. Add grey or magenta overlays for quantitative zones.
4. Place legend box at upper-right corner of chart with matching color keys and flag symbols.
5. Include ⚠ Time-Compressed banner if phase duration < threshold.

---

## 📦 Metadata

```json
{
  "module": "kapman_deterministic_schematic_rules",
  "version": "2.2",
  "codename": "Context-Aware + Taxonomy",
  "compatibility": ["KapMan v2.17+", "Snapshot Readiness v2.0"],
  "description": "Adds taxonomy for classical vs. quantitative contexts, contextual flags, and full legend integration for schematic rendering."
}
```
