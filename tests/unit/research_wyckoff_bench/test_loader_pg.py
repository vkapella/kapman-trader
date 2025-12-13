import os

import pandas as pd
import pytest

from research.wyckoff_bench.harness.loader_pg import load_ohlcv


@pytest.mark.skipif(os.getenv("USE_TEST_DB") != "true", reason="requires test Postgres with ohlcv_daily")
def test_load_ohlcv_smoke():
    df = load_ohlcv(["AAPL"], start="2023-01-01", end="2023-02-01")
    assert isinstance(df, pd.DataFrame)
    assert {"time", "open", "high", "low", "close", "volume", "symbol"}.issubset(df.columns)
