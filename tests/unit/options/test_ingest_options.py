from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from core.ingestion.options.pipeline import OptionsIngestionReport, SymbolIngestionOutcome
from scripts import ingest_options


def _build_sample_report(snapshot_time: datetime) -> OptionsIngestionReport:
    outcome = SymbolIngestionOutcome(
        symbol="AAPL",
        ok=True,
        snapshot_rows_fetched=1,
        snapshot_rows_normalized=1,
        rows_persisted=5,
        elapsed_s=0.1,
    )
    return OptionsIngestionReport(
        snapshot_time=snapshot_time,
        provider="polygon",
        symbols=["AAPL"],
        outcomes=[outcome],
        total_rows_persisted=5,
        elapsed_s=0.1,
    )


def test_resolve_snapshot_time_at_end_of_day() -> None:
    target = date(2025, 12, 1)
    result = ingest_options.resolve_snapshot_time(target)
    assert result == datetime(2025, 12, 1, 23, 59, 59, tzinfo=timezone.utc)


def test_resolve_trading_dates_includes_all_calendar_days() -> None:
    dates = ingest_options._resolve_trading_dates(date(2025, 12, 5), date(2025, 12, 9))
    assert dates == [
        date(2025, 12, 5),
        date(2025, 12, 6),
        date(2025, 12, 7),
        date(2025, 12, 8),
        date(2025, 12, 9),
    ]


def test_date_range_flags_require_both(monkeypatch) -> None:
    monkeypatch.setattr(ingest_options, "load_dotenv", lambda: None)
    with pytest.raises(SystemExit) as excinfo:
        ingest_options.main(["--start-date", "2025-12-01"])
    assert "--start-date and --end-date must be provided together" in str(excinfo.value)


def test_range_snapshot_time_conflict(monkeypatch) -> None:
    monkeypatch.setattr(ingest_options, "load_dotenv", lambda: None)
    with pytest.raises(SystemExit) as excinfo:
        ingest_options.main(
            [
                "--start-date",
                "2025-12-01",
                "--end-date",
                "2025-12-02",
                "--snapshot-time",
                "2025-12-01T00:00:00Z",
            ]
        )
    assert "--snapshot-time cannot be combined" in str(excinfo.value)


def test_as_of_conflicts_with_range_flags(monkeypatch) -> None:
    monkeypatch.setattr(ingest_options, "load_dotenv", lambda: None)
    with pytest.raises(SystemExit) as excinfo:
        ingest_options.main(
            [
                "--as-of",
                "2025-12-01",
                "--start-date",
                "2025-12-01",
                "--end-date",
                "2025-12-02",
            ]
        )
    assert "--as-of cannot be combined" in str(excinfo.value)


def test_single_day_defaults_snapshot_time(monkeypatch) -> None:
    monkeypatch.setattr(ingest_options, "load_dotenv", lambda: None)

    calls: list[dict] = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return _build_sample_report(kwargs["snapshot_time"])

    monkeypatch.setattr(ingest_options, "ingest_options_chains_from_watchlists", fake_run)

    exit_code = ingest_options.main(["--as-of", "2025-12-03"])
    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0]["snapshot_time"] == ingest_options.resolve_snapshot_time(date(2025, 12, 3))


def test_range_invokes_pipeline_per_date(monkeypatch) -> None:
    monkeypatch.setattr(ingest_options, "load_dotenv", lambda: None)

    calls: list[dict] = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return _build_sample_report(kwargs["snapshot_time"])

    monkeypatch.setattr(ingest_options, "ingest_options_chains_from_watchlists", fake_run)

    exit_code = ingest_options.main(["--start-date", "2025-12-01", "--end-date", "2025-12-02"])
    assert exit_code == 0
    assert len(calls) == 2
    assert calls[0]["as_of_date"] == date(2025, 12, 1)
    assert calls[1]["as_of_date"] == date(2025, 12, 2)
    assert calls[0]["snapshot_time"] == ingest_options.resolve_snapshot_time(date(2025, 12, 1))
    assert calls[1]["snapshot_time"] == ingest_options.resolve_snapshot_time(date(2025, 12, 2))


def test_range_includes_weekends(monkeypatch) -> None:
    monkeypatch.setattr(ingest_options, "load_dotenv", lambda: None)

    calls: list[dict] = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return _build_sample_report(kwargs["snapshot_time"])

    monkeypatch.setattr(ingest_options, "ingest_options_chains_from_watchlists", fake_run)

    exit_code = ingest_options.main(["--start-date", "2025-12-05", "--end-date", "2025-12-09"])
    assert exit_code == 0
    assert len(calls) == 5
    assert calls[0]["as_of_date"] == date(2025, 12, 5)
    assert calls[1]["as_of_date"] == date(2025, 12, 6)
    assert calls[2]["as_of_date"] == date(2025, 12, 7)
    assert calls[3]["as_of_date"] == date(2025, 12, 8)
    assert calls[4]["as_of_date"] == date(2025, 12, 9)
    for call in calls:
        assert call["snapshot_time"] == ingest_options.resolve_snapshot_time(call["as_of_date"])


def test_range_continues_after_date_failure(monkeypatch) -> None:
    monkeypatch.setattr(ingest_options, "load_dotenv", lambda: None)

    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return _build_sample_report(kwargs["snapshot_time"])

    monkeypatch.setattr(ingest_options, "ingest_options_chains_from_watchlists", fake_run)

    exit_code = ingest_options.main(["--start-date", "2025-12-01", "--end-date", "2025-12-02"])
    assert exit_code == 0
    assert len(calls) == 2
