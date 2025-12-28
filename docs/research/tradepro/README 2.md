# Wyckoff + VPA Integrated Pipeline

## Overview
This module provides a structured pipeline that merges **Wyckoff methodology** and **Volume Price Analysis (VPA)** for market phase detection and trade context classification.

---

## Pipeline Flow
1. **Raw Data Input:**  
   OHLCV (open, high, low, close, volume) data, ideally daily candles.

2. **VPA Computation:**  
   Calculates the relationship between price *effort* (volume) and *result* (price spread).  
   ```python
   spread = high - low
   effort_result = (close.diff()) / volume
   ```

3. **Wyckoff Classification:**  
   Classifies each candle into one of five Wyckoff phases:
   - **Accumulation:** Quiet basing, low volume.
   - **Markup:** Expanding spread + rising volume.
   - **Distribution:** Rising price with declining volume.
   - **Markdown:** Decline with volume expansion.
   - **Reaccumulation/Redistribution:** Pause in trend continuation.

4. **Confluence Scoring:**  
   Assigns confidence levels to each bar based on the Wyckoff phase.

---

## Key Concepts

### 🧱 Volume Price Analysis (VPA)
The study of **effort (volume)** vs **result (price movement)** to interpret supply/demand dynamics.

| Volume Behavior | Price Behavior | Interpretation |
|------------------|----------------|----------------|
| Rising | Rising | Demand > Supply (bullish) |
| Rising | Falling | Supply > Demand (bearish) |
| Falling | Rising | Weak demand, likely exhaustion |
| Falling | Falling | No interest phase |

---

### 📈 Wyckoff Market Phases
| Phase | Description | Institutional Behavior |
|--------|--------------|------------------------|
| Accumulation | Smart money buying | Absorption |
| Markup | Broad participation | Trend begins |
| Distribution | Smart money selling | Supply appears |
| Markdown | Public panic | Trend ends |
| Reaccumulation | Pause before continuation | Re-entry |

---

## Usage Example
```python
import pandas as pd
from wyckoff_vpa_pipeline import WyckoffVPAPipeline

# Assume df is a DataFrame with OHLCV columns
pipeline = WyckoffVPAPipeline(df)
results = pipeline.run()
print(results[['close', 'wyckoff_phase', 'confluence_score']].tail())
```

---

## Output Columns
| Column | Description |
|--------|-------------|
| `spread` | Price range per candle |
| `effort_result` | Volume-adjusted price move |
| `wyckoff_phase` | Classified market phase |
| `confluence_score` | Confidence weighting (0–1) |

---

### ⚠️ Disclaimer
This code is for **educational and research purposes**.  
Trading involves risk — use with discretion and verify all signals.
