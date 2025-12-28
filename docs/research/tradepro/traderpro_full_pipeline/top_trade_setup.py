import pandas as pd

class TopTradeSetup:
    def __init__(self, data: pd.DataFrame):
        self.df = data.copy()

    def extract_top(self, top_n=5):
        ranked = self.df.sort_values(by='confluence_score', ascending=False)
        return ranked.head(top_n)[['close','candlestick_pattern','chart_pattern','confluence_score']]
