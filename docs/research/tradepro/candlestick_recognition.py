import pandas as pd

class CandlestickRecognition:
    def __init__(self, data: pd.DataFrame):
        self.df = data.copy()

    def detect_patterns(self):
        candles = []
        for i in range(1, len(self.df)):
            o, h, l, c = self.df.iloc[i][['open','high','low','close']]
            prev_c = self.df.iloc[i-1]['close']
            if (c > o) and ((c - o) / (h - l) > 0.6):
                candles.append('Bullish Marubozu')
            elif (o > c) and ((o - c) / (h - l) > 0.6):
                candles.append('Bearish Marubozu')
            elif (abs(c - o) < (h - l) * 0.1):
                candles.append('Doji')
            elif (c > prev_c) and (o < prev_c):
                candles.append('Bullish Engulfing')
            elif (c < prev_c) and (o > prev_c):
                candles.append('Bearish Engulfing')
            else:
                candles.append('Neutral')
        candles.insert(0, 'N/A')
        self.df['candlestick_pattern'] = candles
        return self.df
