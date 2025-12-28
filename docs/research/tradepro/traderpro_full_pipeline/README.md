# TraderPro GPTZ — Full Technical Pipeline

## Overview
This pipeline combines **Volume Price Analysis (VPA)**, **Wyckoff logic**, **candlestick recognition**, and **pattern detection** to produce ranked trade setups.

---

## Modules

### 1️⃣ vpa_computation.py
Calculates *effort vs result* using volume and price spread to detect accumulation, markup, distribution, and markdown phases.

### 2️⃣ candlestick_recognition.py
Identifies common candle patterns such as:
- Bullish/Bearish Engulfing
- Marubozu
- Doji

### 3️⃣ pattern_detection.py
Recognizes structural chart patterns:
- Flag Breakout
- Breakdown
- Consolidation

### 4️⃣ confluence_scoring.py
Aggregates multiple signals to generate a **confidence score** (0–1) based on overlapping bullish/bearish confirmations.

### 5️⃣ top_trade_setup.py
Sorts the dataset by confluence score and extracts the **top N trade opportunities**.

---

## Usage Example
```python
import pandas as pd
from vpa_computation import VPAComputation
from candlestick_recognition import CandlestickRecognition
from pattern_detection import PatternDetection
from confluence_scoring import ConfluenceScoring
from top_trade_setup import TopTradeSetup

df = pd.read_csv('ohlcv_data.csv')
df = VPAComputation(df).compute()
df = CandlestickRecognition(df).detect_patterns()
df = PatternDetection(df).detect()
df = ConfluenceScoring(df).score()
top_trades = TopTradeSetup(df).extract_top(5)

print(top_trades)
```

---

## Concept Map
1. **Volume precedes price** — VPA validates the underlying effort.
2. **Candlesticks time reversals** — key for entry precision.
3. **Patterns confirm continuation/reversal**.
4. **Confluence scoring ranks the probability edge.**
