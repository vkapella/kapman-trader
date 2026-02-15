from datetime import date

import pytest

from core.ingestion.ohlcv.pipeline import IngestionError, resolve_calendar_dates_to_ingest


def test_resolve_calendar_dates_skips_missing_with_warning(monkeypatch, caplog):
    start = date(2026, 1, 30)
    end = date(2026, 2, 2)

    # Only two of the four desired dates exist.
    monkeypatch.setattr(
        "core.ingestion.ohlcv.pipeline.list_available_dates_in_range",
        lambda *_args, **_kwargs: [date(2026, 1, 31), date(2026, 2, 1)],
    )

    caplog.set_level("WARNING", logger="core.ingestion.ohlcv.pipeline")

    out = resolve_calendar_dates_to_ingest(
        s3=None,
        bucket="b",
        prefix="p",
        start=start,
        end=end,
    )

    assert out == [date(2026, 1, 31), date(2026, 2, 1)]
    assert any("Missing Polygon S3 daily files for 2 requested dates" in r.message for r in caplog.records)


def test_resolve_calendar_dates_raises_when_none_available(monkeypatch):
    start = date(2026, 1, 30)
    end = date(2026, 2, 2)

    monkeypatch.setattr(
        "core.ingestion.ohlcv.pipeline.list_available_dates_in_range",
        lambda *_args, **_kwargs: [],
    )

    with pytest.raises(IngestionError):
        resolve_calendar_dates_to_ingest(
            s3=None,
            bucket="b",
            prefix="p",
            start=start,
            end=end,
        )
