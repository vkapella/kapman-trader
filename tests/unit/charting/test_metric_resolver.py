from core.charting.metric_resolver import resolve_json_path


def test_resolve_json_path_scalar_metric() -> None:
    payload = {"trend": {"macd": {"macd": 1.25}}}
    assert resolve_json_path(payload, ("trend", "macd", "macd")) == 1.25


def test_resolve_json_path_object_metric() -> None:
    payload = {"pattern_recognition": {"cdl2crows": 100, "cdl3blackcrows": -100}}
    assert resolve_json_path(payload, ("pattern_recognition",)) == {
        "cdl2crows": 100,
        "cdl3blackcrows": -100,
    }
