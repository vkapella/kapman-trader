from decimal import Decimal

from core.providers.ai.payload_normalization import normalize_payload


def test_decimal_normalization_simple() -> None:
    assert normalize_payload(Decimal("1.5")) == 1.5


def test_decimal_normalization_nested() -> None:
    payload = {"a": Decimal("1.25"), "b": {"c": Decimal("2.5")}}
    normalized = normalize_payload(payload)
    assert normalized == {"a": 1.25, "b": {"c": 2.5}}


def test_decimal_normalization_list_of_dicts() -> None:
    payload = [{"a": Decimal("1.0")}, {"b": Decimal("2.0")}]
    normalized = normalize_payload(payload)
    assert normalized == [{"a": 1.0}, {"b": 2.0}]


def test_non_decimal_values_unchanged() -> None:
    payload = {"text": "ok", "count": 3, "flag": True, "missing": None, "ratio": 0.5}
    normalized = normalize_payload(payload)
    assert normalized == payload
