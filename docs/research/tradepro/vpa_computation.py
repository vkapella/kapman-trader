import pandas as pd
import numpy as np

class VPAComputation:
    def __init__(self, data: pd.DataFrame):
        self.df = data.copy()

    def compute(self):
        self.df['spread'] = self.df['high'] - self.df['low']
        self.df['result'] = self.df['close'].diff()
        self.df['effort'] = self.df['volume']
        self.df['effort_result_ratio'] = self.df['result'] / self.df['effort']
        return self.df
