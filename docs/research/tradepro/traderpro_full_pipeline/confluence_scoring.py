import pandas as pd

class ConfluenceScoring:
    def __init__(self, data: pd.DataFrame):
        self.df = data.copy()

    def score(self):
        scores = []
        for _, row in self.df.iterrows():
            score = 0.5
            if 'Bullish' in str(row.get('candlestick_pattern')):
                score += 0.2
            if 'Flag' in str(row.get('chart_pattern')):
                score += 0.2
            if row.get('volume', 0) > self.df['volume'].mean():
                score += 0.1
            scores.append(min(score, 1.0))
        self.df['confluence_score'] = scores
        return self.df
