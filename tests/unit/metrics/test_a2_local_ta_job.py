from __future__ import annotations

import logging
import warnings
from datetime import date, timedelta

import pandas as pd
import pytest

from core.metrics.a2_local_ta_job import (
    DEFAULT_TICKER_CHUNK_SIZE,
    compute_eta_seconds,
    compute_price_metrics_json,
    compute_technical_indicators_json,
    get_indicator_surface_for_tests,
    partition_chunks_for_workers,
    partition_ticker_ids,
    run_a2_local_ta_job,
)
from scripts.run_a2_local_ta import _resolve_ticker_chunk_size, build_parser


def _ohlcv_df(n: int) -> pd.DataFrame:
    start = date(2025, 1, 1)
    dates = [start + timedelta(days=i) for i in range(n)]
    prices = [100.0 + i for i in range(n)]
    volumes = [1_000_000.0 + (i * 1000.0) for i in range(n)]
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": volumes,
        },
        index=dates,
    ).reset_index(drop=True)


def test_technical_json_has_authoritative_shape_and_keys() -> None:
    surface = get_indicator_surface_for_tests()
    df = _ohlcv_df(10)

    technical = compute_technical_indicators_json(df)

    for category in surface.TECHNICAL_TOP_LEVEL_CATEGORIES:
        assert category in technical

    for category, indicators in surface.INDICATOR_REGISTRY.items():
        assert category in technical
        for name, info in indicators.items():
            assert name in technical[category]
            for output_key in info.get("outputs", []):
                assert output_key in technical[category][name]

    for k in surface.PATTERN_RECOGNITION_OUTPUT_KEYS:
        assert k in technical["pattern_recognition"]

    assert all(v is None for v in technical["pattern_recognition"].values())


def test_sma_variants_exist_and_sma200_null_when_insufficient_history() -> None:
    df = _ohlcv_df(50)
    technical = compute_technical_indicators_json(df)

    sma = technical["trend"]["sma"]
    assert "sma_14" in sma
    assert "sma_20" in sma
    assert "sma_50" in sma
    assert "sma_200" in sma
    assert sma["sma_200"] is None


def test_price_metrics_keys_always_emitted_and_null_for_short_history() -> None:
    df = _ohlcv_df(10)
    metrics = compute_price_metrics_json(df)
    assert set(metrics.keys()) == {"rvol", "vsi", "hv"}
    assert metrics["rvol"] is None
    assert metrics["vsi"] is None
    assert metrics["hv"] is None


def test_partition_ticker_ids_is_deterministic_and_lossless() -> None:
    ids = [f"t{i}" for i in range(7)]
    chunks = partition_ticker_ids(ids, chunk_size=3)
    assert chunks == [["t0", "t1", "t2"], ["t3", "t4", "t5"], ["t6"]]
    flattened = [x for c in chunks for x in c]
    assert flattened == ids
    assert len(set(flattened)) == len(flattened)


def test_partition_chunks_for_workers_is_round_robin_and_deterministic() -> None:
    chunks = list(range(8))
    assignments = partition_chunks_for_workers(chunks, workers=3)
    assert assignments == [[0, 3, 6], [1, 4, 7], [2, 5]]
    flattened = [x for worker in assignments for x in worker]
    assert sorted(flattened) == chunks


def test_default_chunk_size_applies_when_flag_omitted() -> None:
    args = build_parser().parse_args([])
    source, size = _resolve_ticker_chunk_size(args)
    assert source == "default"
    assert size == DEFAULT_TICKER_CHUNK_SIZE


def test_eta_math_matches_spec() -> None:
    avg, eta = compute_eta_seconds(
        cumulative_chunk_time_sec=10.0,
        tickers_processed_so_far=5,
        remaining_tickers=15,
    )
    assert avg == pytest.approx(2.0)
    assert eta == pytest.approx(30.0)


def test_warning_suppression_blocks_expected_runtimewarnings() -> None:
    df = _ohlcv_df(50)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        compute_technical_indicators_json(df)

    assert not any(isinstance(w.message, RuntimeWarning) for w in captured)


def test_warning_suppression_does_not_change_outputs_for_sample_indicator() -> None:
    surface = get_indicator_surface_for_tests()
    df = _ohlcv_df(60)

    technical = compute_technical_indicators_json(df)
    sma_14 = technical["trend"]["sma"]["sma_14"]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        expected = surface.compute_indicator_latest(df, "trend", "sma")["outputs"]["sma_14"]

    assert sma_14 == expected


def test_job_emits_summary_stats(caplog, monkeypatch) -> None:
    df = _ohlcv_df(60)
    surface = get_indicator_surface_for_tests()
    expected_outputs_per_ticker = sum(
        len(info.get("outputs", []))
        for category in surface.INDICATOR_REGISTRY.values()
        for info in category.values()
    )

    class DummyConn:
        def commit(self) -> None:
            return None

    monkeypatch.setattr(
        "core.metrics.a2_local_ta_job._fetch_active_ticker_ids", lambda conn: ["t1", "t2"]
    )
    monkeypatch.setattr(
        "core.metrics.a2_local_ta_job._load_ohlcv_history", lambda conn, ticker_id, snapshot_date: df
    )
    monkeypatch.setattr(
        "core.metrics.a2_local_ta_job._upsert_daily_snapshot", lambda *args, **kwargs: None
    )

    caplog.set_level(logging.INFO)
    log = logging.getLogger("kapman.tests.a2")
    run_a2_local_ta_job(
        DummyConn(),
        snapshot_dates=[date(2025, 12, 5)],
        heartbeat_every=0,
        verbose=False,
        log=log,
    )

    summaries = [r for r in caplog.records if getattr(r, "a2_summary", False)]
    assert len(summaries) == 1
    stats = getattr(summaries[0], "a2_stats", None)
    assert isinstance(stats, dict)
    assert stats["tickers_processed"] == 2
    assert stats["snapshots_written"] == 2
    assert stats["total_chunks"] == 1
    assert isinstance(stats["chunk_times_sec"], list)
    assert len(stats["chunk_times_sec"]) == 1
    assert stats["chunk_time_sec_total"] >= 0.0
    assert stats["indicators_computed_total"] == expected_outputs_per_ticker * 2
    assert 0 <= stats["indicators_null_total"] <= stats["indicators_computed_total"]
    assert stats["pattern_indicators_enabled"] is False
    assert stats["pattern_backend_available"] is False
    assert stats["pattern_indicators_attempted"] == 0
    assert stats["pattern_indicators_present"] == 0
    assert stats["technical_indicator_time_sec"] >= 0.0
    assert stats["pattern_indicator_time_sec"] == 0.0
