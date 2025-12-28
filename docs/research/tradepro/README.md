# TraderPro GPTZ — Pipeline Modules Overview

## 1️⃣ VPA Computation
Performs Volume Price Analysis (VPA) by evaluating effort (volume) versus result (price spread).

## 2️⃣ Candlestick Recognition
Detects common candlestick patterns such as:
- Bullish/Bearish Engulfing
- Marubozu
- Doji

## 3️⃣ Pattern Detection
Identifies structural chart patterns:
- Flag Breakout
- Breakdown
- Consolidation

## 4️⃣ Confluence Scoring
Aggregates multiple signals to generate a confidence score (0–1) based on overlapping bullish/bearish confirmations.

## 5️⃣ Top Trade Setup
Sorts setups by confidence to display the top trade opportunities.

---

### Example Pipeline Usage
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
