import pandas as pd

def apply_experiment(events_df, ohlcv_by_symbol, config):
    # Identity filter: baseline AR only
    return events_df[events_df["event"] == "AR"].copy()