from __future__ import annotations

import gzip
import os
from datetime import date
from io import BytesIO
from unittest.mock import patch

import psycopg2
import pytest

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.ingestion.tickers.polygon_reference import PolygonTicker


def _gz_bytes(text: str) -> bytes:
    buf = BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(text.encode("utf-8"))
    return buf.getvalue()


@pytest.mark.integration
@pytest.mark.db
def test_a0_bootstrap_then_ohlcv_ingest_is_idempotent() -> None:
    db_url = os.getenv("KAPMAN_TEST_DATABASE_URL")
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    os.environ["DATABASE_URL"] = db_url
    os.environ["POLYGON_API_KEY"] = "test-polygon-key"
    os.environ["S3_ENDPOINT_URL"] = "https://test-s3.invalid"
    os.environ["S3_BUCKET"] = "flatfiles"
    os.environ["AWS_ACCESS_KEY_ID"] = "test-aws-key"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test-aws-secret"

    target_date = date(2025, 12, 5)
    csv_text = (
        "ticker,volume,open,close,high,low\n"
        "AAPL,100,150.0,152.0,153.0,149.5\n"
        "MSFT,200,300.0,301.0,305.0,299.0\n"
        "BCPC,123,10.0,11.0,12.0,9.0\n"
    )
    gz = _gz_bytes(csv_text)

    fake_tickers = [
        PolygonTicker(symbol="AAPL", name="Apple", exchange="XNAS", asset_type="CS", currency="USD", is_active=True),
        PolygonTicker(symbol="MSFT", name="Microsoft", exchange="XNAS", asset_type="CS", currency="USD", is_active=True),
    ]

    from scripts.ingest_ohlcv import main as ingest_main

    with (
        patch("core.ingestion.tickers.loader.fetch_all_active_tickers", return_value=fake_tickers),
        patch("scripts.ingest_ohlcv.list_latest_available_dates", return_value=[target_date]),
        patch("core.ingestion.ohlcv.pipeline.fetch_gzipped_csv_bytes", return_value=gz),
    ):
        ingest_main(["base", "--days", "1", "--as-of", target_date.isoformat()])
        ingest_main(["base", "--days", "1", "--as-of", target_date.isoformat()])

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM tickers")
            tickers_count = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM ohlcv_daily")
            ohlcv_count = int(cur.fetchone()[0])

    assert tickers_count == 2
    assert ohlcv_count == 2
