from core.charting.metrics_registry import filter_metrics, select_panels


def test_select_panels_skips_empty_panels() -> None:
    metrics = filter_metrics(["RSI", "MACD", "ADX"])
    available_keys = {metric.key for metric in metrics if metric.panel == "RSI"}
    panels = select_panels(metrics, available_keys)
    assert panels == ["PRICE", "RSI"]


def test_select_panels_orders_panels_by_registry() -> None:
    metrics = filter_metrics(["MACD", "RSI"])
    available_keys = {metric.key for metric in metrics if metric.panel in {"RSI", "MACD"}}
    panels = select_panels(metrics, available_keys)
    assert panels == ["PRICE", "RSI", "MACD"]
