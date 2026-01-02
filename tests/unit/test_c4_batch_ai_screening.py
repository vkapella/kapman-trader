import pytest

from core.metrics.c4_batch_ai_screening_job import (
    compute_backoff_seconds,
    partition_batches,
    sort_tickers,
)


def test_partition_batches() -> None:
    items = [1, 2, 3, 4, 5]
    assert partition_batches(items, 2) == [[1, 2], [3, 4], [5]]

    with pytest.raises(ValueError):
        partition_batches(items, 0)


def test_compute_backoff_seconds() -> None:
    assert compute_backoff_seconds(attempt=1, base_seconds=1.0) == 1.0
    assert compute_backoff_seconds(attempt=2, base_seconds=1.0) == 2.0
    assert compute_backoff_seconds(attempt=3, base_seconds=1.0) == 4.0

    with pytest.raises(ValueError):
        compute_backoff_seconds(attempt=0, base_seconds=1.0)


def test_sort_tickers_is_deterministic() -> None:
    tickers = [("2", "msft"), ("1", "AAPL"), ("3", "aapl")]
    assert sort_tickers(tickers) == [("1", "AAPL"), ("3", "AAPL"), ("2", "MSFT")]
