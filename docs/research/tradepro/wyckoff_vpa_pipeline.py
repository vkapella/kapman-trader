import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression

class WyckoffVPAPipeline:
    def __init__(self, data: pd.DataFrame):
        self.df = data.copy()
        self.vol_mean = self.df['volume'].rolling(20).mean()
        self.results = {}

    def classify_vpa(self):
        self.df['spread'] = self.df['high'] - self.df['low']
        self.df['result'] = self.df['close'].diff()
        self.df['effort'] = self.df['volume']
        self.df['effort_result'] = self.df['result'] / self.df['effort']
        return self.df

    def classify_wyckoff(self):
        vol_mean = self.vol_mean
        spread = self.df['spread']
        price_change = self.df['close'].pct_change()
        wyckoff_phases = []

        for i in range(len(self.df)):
            vol = self.df['volume'].iloc[i]
            change = price_change.iloc[i]

            if (vol < vol_mean.iloc[i]*0.8) and (abs(change) < 0.01):
                wyckoff_phases.append("Accumulation")
            elif (change > 0.02) and (vol > vol_mean.iloc[i]*1.5):
                wyckoff_phases.append("Markup")
            elif (change < 0) and (vol > vol_mean.iloc[i]*1.3):
                wyckoff_phases.append("Markdown")
            elif (change > 0) and (vol < vol_mean.iloc[i]):
                wyckoff_phases.append("Distribution")
            else:
                wyckoff_phases.append("Reaccumulation/Redistribution")

        self.df['wyckoff_phase'] = wyckoff_phases
        return self.df

    def confluence_score(self):
        scores = []
        for i in range(len(self.df)):
            phase = self.df['wyckoff_phase'].iloc[i]
            if phase == "Accumulation":
                scores.append(0.8)
            elif phase == "Markup":
                scores.append(0.9)
            elif phase == "Distribution":
                scores.append(0.6)
            elif phase == "Markdown":
                scores.append(0.5)
            else:
                scores.append(0.7)
        self.df['confluence_score'] = scores
        return self.df

    def run(self):
        self.classify_vpa()
        self.classify_wyckoff()
        self.confluence_score()
        return self.df
