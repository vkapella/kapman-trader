from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
def test_ingest_ohlcv_bootstraps_tickers_when_empty() -> None:
    from scripts.ingest_ohlcv import main

    fake_conn = MagicMock()
    fake_connect = MagicMock()
    fake_connect.return_value.__enter__.return_value = fake_conn

    with (
        patch("scripts.ingest_ohlcv.ohlcv_db.connect", new=fake_connect),
        patch("scripts.ingest_ohlcv.ohlcv_db.count_table", side_effect=[0, 2]),
        patch("scripts.ingest_ohlcv.ensure_universe_loaded") as ensure_called,
        patch("scripts.ingest_ohlcv.default_s3_flatfiles_config") as cfg,
        patch("scripts.ingest_ohlcv.get_s3_client") as get_s3,
        patch("scripts.ingest_ohlcv.list_latest_available_dates", return_value=[date(2025, 12, 5)]),
        patch("scripts.ingest_ohlcv.ingest_ohlcv") as ingest_called,
    ):
        cfg.return_value = MagicMock(bucket="b", prefix="p")
        get_s3.return_value = MagicMock()
        ingest_called.return_value = MagicMock(
            requested=MagicMock(mode="base", start=date(2025, 12, 5), end=date(2025, 12, 5)),
            ingested_dates=[date(2025, 12, 5)],
            total_rows_written=0,
        )

        main(["base", "--days", "1", "--as-of", "2025-12-05"])

    ensure_called.assert_called_once()


@pytest.mark.unit
def test_ingest_ohlcv_does_not_bootstrap_when_tickers_present() -> None:
    from scripts.ingest_ohlcv import main

    fake_conn = MagicMock()
    fake_connect = MagicMock()
    fake_connect.return_value.__enter__.return_value = fake_conn

    with (
        patch("scripts.ingest_ohlcv.ohlcv_db.connect", new=fake_connect),
        patch("scripts.ingest_ohlcv.ohlcv_db.count_table", return_value=10),
        patch("scripts.ingest_ohlcv.ensure_universe_loaded") as ensure_called,
        patch("scripts.ingest_ohlcv.default_s3_flatfiles_config") as cfg,
        patch("scripts.ingest_ohlcv.get_s3_client") as get_s3,
        patch("scripts.ingest_ohlcv.list_latest_available_dates", return_value=[date(2025, 12, 5)]),
        patch("scripts.ingest_ohlcv.ingest_ohlcv") as ingest_called,
    ):
        cfg.return_value = MagicMock(bucket="b", prefix="p")
        get_s3.return_value = MagicMock()
        ingest_called.return_value = MagicMock(
            requested=MagicMock(mode="base", start=date(2025, 12, 5), end=date(2025, 12, 5)),
            ingested_dates=[date(2025, 12, 5)],
            total_rows_written=0,
        )

        main(["base", "--days", "1", "--as-of", "2025-12-05"])

    ensure_called.assert_not_called()


@pytest.mark.unit
def test_ingest_ohlcv_respects_no_ticker_bootstrap_flag() -> None:
    from scripts.ingest_ohlcv import main

    fake_conn = MagicMock()
    fake_connect = MagicMock()
    fake_connect.return_value.__enter__.return_value = fake_conn

    with (
        patch("scripts.ingest_ohlcv.ohlcv_db.connect", new=fake_connect),
        patch("scripts.ingest_ohlcv.ohlcv_db.count_table", return_value=0),
        patch("scripts.ingest_ohlcv.ensure_universe_loaded") as ensure_called,
    ):
        with pytest.raises(Exception, match="tickers table is empty; load ticker universe before OHLCV"):
            main(["base", "--days", "1", "--as-of", "2025-12-05", "--no-ticker-bootstrap"])

    ensure_called.assert_not_called()
