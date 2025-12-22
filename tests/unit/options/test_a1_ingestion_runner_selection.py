from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from core.ingestion.options import pipeline as a1_pipeline


@pytest.mark.unit
def test_provider_resolution_prefers_cli(monkeypatch) -> None:
    monkeypatch.setenv("OPTIONS_PROVIDER", "polygon")
    assert a1_pipeline._resolve_provider_name("unicorn") == "unicorn"


@pytest.mark.unit
def test_provider_resolution_env_fallback(monkeypatch) -> None:
    monkeypatch.setenv("OPTIONS_PROVIDER", "polygon")
    assert a1_pipeline._resolve_provider_name(None) == "polygon"


@pytest.mark.unit
def test_provider_resolution_default(monkeypatch) -> None:
    monkeypatch.delenv("OPTIONS_PROVIDER", raising=False)
    assert a1_pipeline._resolve_provider_name(None) == "unicorn"


@pytest.mark.unit
def test_dedupe_and_sort_symbols_is_deterministic() -> None:
    assert a1_pipeline.dedupe_and_sort_symbols(["msft", "AAPL", "MSFT", "  ", "goog"]) == [
        "AAPL",
        "GOOG",
        "MSFT",
    ]


@pytest.mark.unit
def test_runner_intersects_subset_with_watchlists() -> None:
    fake_db_url = "postgresql://example.invalid/db"
    snapshot_time = datetime(2025, 12, 20, tzinfo=timezone.utc)

    with (
        patch.object(a1_pipeline.options_db, "default_db_url", return_value=fake_db_url),
        patch.object(a1_pipeline, "_resolve_api_key", return_value="k"),
        patch.object(a1_pipeline.options_db, "connect") as mock_connect,
        patch.object(a1_pipeline.options_db, "fetch_active_watchlist_symbols", return_value=["MSFT", "AAPL"]),
        patch.object(a1_pipeline, "_run_ingestion", new=AsyncMock()) as mock_run,
    ):
        mock_connect.return_value.__enter__.return_value = object()
        mock_run.return_value = object()

        provider = object()
        a1_pipeline.ingest_options_chains_from_watchlists(
            db_url=fake_db_url,
            api_key="k",
            snapshot_time=snapshot_time,
            symbols=["msft", "tsla"],
            concurrency=1,
            provider=provider,
        )

    called_symbols = mock_run.call_args.kwargs["symbols"]
    assert called_symbols == ["MSFT"]
