import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from core.metrics.computations import (
    compute_all_metrics,
    compute_ema,
    compute_hv,
    compute_macd,
    compute_rsi,
    compute_rvol,
    compute_sma,
)


def _build_df(prices, volumes, start_date=date(2024, 1, 1)):
    dates = [start_date + timedelta(days=i) for i in range(len(prices))]
    return pd.DataFrame(
        {
            "date": dates,
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": volumes,
        }
    )


def test_rsi_computation_known_series():
    close = pd.Series([44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64, 46.21])
    rsi = compute_rsi(close)
    # Known RSI(14) result for this series is ~70.46 on the last point
    assert pytest.approx(rsi.iloc[-1], rel=1e-3) == 70.46


def test_macd_components_match_definition():
    close = pd.Series(np.linspace(100, 150, 60))
    components = compute_macd(close)
    macd_line = components["macd_line"]
    macd_signal = components["macd_signal"]
    ema12 = components["ema_12"]
    ema26 = components["ema_26"]

    assert pytest.approx(macd_line.iloc[-1], rel=1e-9) == pytest.approx(ema12.iloc[-1] - ema26.iloc[-1], rel=1e-9)
    assert pytest.approx(components["macd_histogram"].iloc[-1], rel=1e-9) == pytest.approx(macd_line.iloc[-1] - macd_signal.iloc[-1], rel=1e-9)


def test_sma_ema_windows_match_expected():
    close = pd.Series(range(1, 51))  # 1..50
    sma20 = compute_sma(close, 20).iloc[-1]
    sma50 = compute_sma(close, 50).iloc[-1]
    ema12 = compute_ema(close, 12).iloc[-1]
    ema26 = compute_ema(close, 26).iloc[-1]

    assert sma20 == pytest.approx(sum(range(31, 51)) / 20)
    assert sma50 == pytest.approx(sum(range(1, 51)) / 50)
    assert not math.isnan(ema12)
    assert not math.isnan(ema26)


def test_hv20_log_return_annualization():
    close = pd.Series([100, 102, 101, 103, 104, 103, 105, 104, 106, 107, 108, 109, 108, 110, 111, 112, 111, 113, 114, 115, 116])
    hv_series = compute_hv(close, window=20)
    returns = np.log(close / close.shift(1))
    expected = returns.rolling(window=20, min_periods=20).std(ddof=0) * math.sqrt(252)
    assert hv_series.iloc[-1] == pytest.approx(expected.iloc[-1])


def test_rvol_excludes_target_day_from_denominator():
    volumes = [100] * 20 + [200]
    rvol = compute_rvol(pd.Series(volumes), window=20)
    assert rvol.iloc[-1] == pytest.approx(2.0)


def test_insufficient_history_returns_nulls():
    prices = [100 + i for i in range(10)]
    volumes = [1_000_000] * 10
    df = _build_df(prices, volumes)
    metrics = compute_all_metrics(df, df["date"].iloc[-1])
    assert all(value is None for value in metrics.__dict__.values())


def test_determinism_same_input_same_output():
    prices = [100 + i for i in range(60)]
    volumes = [1_000_000 + i * 10 for i in range(60)]
    df = _build_df(prices, volumes)
    target = df["date"].iloc[-1]

    metrics_a = compute_all_metrics(df, target)
    metrics_b = compute_all_metrics(df.copy(), target)

    assert metrics_a == metrics_b

