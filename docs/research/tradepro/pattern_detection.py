import pandas as pd

class PatternDetection:
    def __init__(self, data: pd.DataFrame):
        self.df = data.copy()

    def detect(self):
        patterns = []
        for i in range(2, len(self.df)):
            prev_close = self.df.iloc[i-1]['close']
            curr_close = self.df.iloc[i]['close']
            if curr_close > prev_close * 1.05:
                patterns.append('Flag Breakout')
            elif curr_close < prev_close * 0.95:
                patterns.append('Breakdown')
            else:
                patterns.append('Consolidation')
        patterns = ['N/A','N/A'] + patterns
        self.df['chart_pattern'] = patterns
        return self.df
