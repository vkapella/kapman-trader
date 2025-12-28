Polygon / Finnhub OHLCV
        ↓
VPA Computation (Effort vs Result)
        ↓
Wyckoff Phase Classification  ←—— (This Step)
        ↓
Candlestick Recognition (Nison)
        ↓
Pattern Detection (Bulkowski)
        ↓
Confluence Scoring
        ↓
Top Trade Setup Output



def wyckoff_phase(df):
    vol_mean = df['volume'].rolling(20).mean()
    spread = df['high'] - df['low']
    price_change = df['close'].pct_change()

    if (df['volume'].iloc[-1] < vol_mean.iloc[-1]*0.8) and (abs(price_change.iloc[-1]) < 0.01):
        return "Accumulation"

    elif (price_change.iloc[-1] > 0.02) and (df['volume'].iloc[-1] > vol_mean.iloc[-1]*1.5):
        return "Markup"

    elif (price_change.iloc[-1] < 0) and (df['volume'].iloc[-1] > vol_mean.iloc[-1]*1.3):
        return "Markdown"

    elif (price_change.iloc[-1] > 0) and (df['volume'].iloc[-1] < vol_mean.iloc[-1]):
        return "Distribution"

    else:
        return "Reaccumulation/Redistribution"


 Here’s a clear view of how TraderPro GPTZ’s data flow works—from the moment you make a request, through provider APIs, down to the Python modules and classifiers used for analysis—based on the configuration from your uploaded PDF ￼:

⸻

⚙️ 1. Data Flow Overview

🧭 User Request → Data Provider → Python Modules → Classifiers

User Input (e.g., “Scan bullish setups under $5”)
        │
        ▼
TraderPro GPTZ Routing Logic
        │
        ├──> Finnhub.io API (Primary)
        │      ├─ getQuote()
        │      ├─ getEarnings(), getInsiderTransactions()
        │      └─ getCryptoCandles(), etc.
        │
        ├──> Polygon.io API (Fallback / Screener)
        │      ├─ screenTickers() ← for large universe scans
        │      ├─ getAllStockSnapshots() ← for real-time data
        │      ├─ getAggregateBars() ← for OHLCV candles
        │      ├─ getPreviousClose() ← for yesterday’s data
        │      └─ getTickerDetails(), getTickerNews()
        │
        ├──> SEC.gov (for filings/fundamentals)
        │
        └──> Internal Analytics Pipeline (Python modules below)


⸻

🧩 2. Python Modules Used

Module	Purpose	Example Usage
pandas, numpy	Data structuring, numeric transformations	Compute moving averages, normalize volume
matplotlib	Visualization	Generate price-volume trend charts
talib (if available)	Technical indicators	RSI, MACD, EMA crossovers
sklearn (classifiers)	Pattern & signal classification	Identify bullish vs bearish patterns
datetime, time	Timeframe management	Convert timestamps from APIs
requests (internal to tools)	HTTP communication	Query Polygon/Finnhub endpoints
ace_tools (custom)	Output formatting	Display DataFrames to user


⸻

🧠 3. Classifiers and Pattern Engines

After raw data is retrieved, TraderPro GPTZ applies layered classifiers:

Classifier Type	Core Logic	Inspired By
VPA Classifier	Compares effort (volume) vs result (price spread) to identify accumulation, markup, distribution, markdown phases	Anna Coulling
Candlestick Classifier	Detects hammers, engulfing, doji, stars, soldiers/crows — validated by VPA context	Steve Nison
Pattern Recognition Engine	Recognizes flags, wedges, triangles, head & shoulders, double bottoms, etc.	Thomas Bulkowski
Volume Divergence Detector	Confirms if price and volume diverge (e.g., rising price + falling volume)	
Confluence Score Aggregator	Assigns a confidence score (0–100%) based on multiple confirmations (VPA + Candle + Pattern + Volume)	

Example flow:
Polygon screenTickers() → 1,000 tickers
→ getAllStockSnapshots() for intraday OHLCV
→ Compute Vol SMA, RSI, Pattern Match %
→ Feed into VPA + Candle + Pattern classifier
→ Return Top 3–5 high-confluence trade setups

⸻

🔄 4. Provider Routing Logic

If Request Type	Then Call	Backup / Fallback
“Scan” / “Screen”	Polygon.screenTickers()	Re-query with cursor if >1000 results
“Analyze [Ticker]”	Polygon.getTickerDetails() → getAggregateBars()	Finnhub.getQuote() if Polygon fails
“Intraday”	Polygon.getAllStockSnapshots()	—
“Filings / Fundamentals”	data.sec.gov.GetSubmissionsByCIK()	—
“Insiders / Earnings”	Finnhub.getInsiderTransactions(), getEarnings()	—


⸻

🔍 5. Data Handling Sequence Example

Let’s say you ask:

“Find small-cap bullish reversals under $5 with volume spikes.”

The sequence is:
	1.	screenTickers(market="stocks", active=True, limit=1000)
	2.	Filter tickers by price < $5 and volume > 1M.
	3.	Fetch getAllStockSnapshots() for top 50 filtered tickers.
	4.	Compute:
	•	Volume SMA (20-day)
	•	Price % change
	•	RSI divergence
	5.	Classify patterns:
	•	Bullish engulfing / hammer (Nison)
	•	Accumulation or stopping volume (VPA)
	•	Pattern success rate >70% (Bulkowski)
	6.	Rank by Confluence Score
	7.	Display top 3–5 setups as “Trading Cards”.

⸻

🧮 6. Example Output Format

Ticker	Price	Volume	Pattern	VPA Phase	Confidence
$ABC	$4.75	2.1M	Bullish Engulfing	Accumulation	86% ✅
$XYZ	$3.20	1.8M	Hammer	No Supply	82% ✅
$QRS	$2.90	3.5M	Flag Breakout	Markup	78% ✅


⸻

🧰 7. Safety & Fallback

If Polygon returns an error (e.g., rate limit), GPTZ:
	•	Falls back to Finnhub.io for last-trade & OHLCV.
	•	Summarizes results from already retrieved tickers.
	•	Warns the user that the scan may be incomplete.

⸻

✅ In short:

TraderPro GPTZ = Multi-source market data pipeline (Polygon + Finnhub + SEC) → Python analytics (pandas + talib + sklearn) → Layered VPA/Candle/Pattern classification → High-confluence trade setup output.

⸻

Would you like me to draw this as a data flow diagram (DFD) showing how each API and classifier connects visually?       