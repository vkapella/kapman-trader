from datetime import date

import pandas as pd

from core.charting.metric_resolver import resolve_json_path, resolve_metric_series


def test_resolve_json_path_scalar_metric() -> None:
    payload = {"trend": {"macd": {"macd": 1.25}}}
    assert resolve_json_path(payload, ("trend", "macd", "macd")) == 1.25


def test_resolve_json_path_object_metric() -> None:
    payload = {"pattern_recognition": {"cdl2crows": 100, "cdl3blackcrows": -100}}
    assert resolve_json_path(payload, ("pattern_recognition",)) == {
        "cdl2crows": 100,
        "cdl3blackcrows": -100,
    }


def test_resolve_metric_series_dealer_json() -> None:
    index = pd.to_datetime([date(2024, 1, 1), date(2024, 1, 2)])
    snapshots = {
        date(2024, 1, 1): {"gex_net": 12.5},
        date(2024, 1, 2): {"gex_net": -7.0},
    }
    series = resolve_metric_series(snapshots, index, ("gex_net",))
    assert series.iloc[0] == 12.5
    assert series.iloc[1] == -7.0


def test_resolve_metric_series_volatility_json() -> None:
    index = pd.to_datetime([date(2024, 2, 1), date(2024, 2, 2)])
    snapshots = {
        date(2024, 2, 1): {"metrics": {"avg_iv": 0.42}},
        date(2024, 2, 2): {"metrics": {"avg_iv": 0.55}},
    }
    series = resolve_metric_series(snapshots, index, ("metrics", "avg_iv"))
    assert series.iloc[0] == 0.42
    assert series.iloc[1] == 0.55
