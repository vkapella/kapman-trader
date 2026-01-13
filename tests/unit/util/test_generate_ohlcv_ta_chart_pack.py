import pytest

from core.charting.metrics_registry import filter_metrics, select_panels
from scripts.util.generate_ohlcv_ta_chart_pack import MA_PERIODS, build_parser, parse_ta_metrics


def test_parser_requires_symbols_or_watchlist() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_rejects_symbols_and_watchlist_together() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--symbols", "AAPL", "--watchlist", "core"])


def test_parse_ta_metrics_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        parse_ta_metrics("MA,NOPE")


def test_panel_order_is_deterministic() -> None:
    metrics = filter_metrics(["MACD", "RSI", "ADX"])
    available_keys = {metric.key for metric in metrics if metric.panel in {"RSI", "MACD"}}
    panels = select_panels(metrics, available_keys)
    assert panels == ["PRICE", "RSI", "MACD"]


def test_ma_period_defaults() -> None:
    assert MA_PERIODS == (20, 50, 200)
