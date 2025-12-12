import gzip
import io
from datetime import date
from unittest.mock import MagicMock

import pytest

from scripts.init.load_ohlcv_base import (
    compute_date_range,
    enforce_retention,
    insert_ohlcv,
    parse_csv_rows,
    process_day,
)


def make_gzip(content: str) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(content.encode())
    return buf.getvalue()


class FakeS3:
    class exceptions:
        class NoSuchKey(Exception):
            pass

    def __init__(self, body: bytes):
        self._body = body

    def get_object(self, Bucket, Key):  # noqa: N802
        return {"Body": io.BytesIO(self._body)}


def test_date_range_calculation():
    start, end = compute_date_range(3, end_date=date(2025, 1, 10))
    assert start == date(2025, 1, 8)
    assert end == date(2025, 1, 10)


def test_empty_file_no_crash():
    body = make_gzip("ticker,open,high,low,close,volume\n")
    s3 = FakeS3(body)
    session = MagicMock()
    inserted, missing = process_day(
        session,
        s3,
        "bucket",
        date(2025, 1, 1),
        {"AAPL": "id1"},
    )
    assert inserted == 0
    assert missing == set()
    session.execute.assert_not_called()
    session.commit.assert_not_called()


def test_bulk_insert_called():
    csv_content = "\n".join([
        "ticker,open,high,low,close,volume",
        "AAPL,1,2,3,4,100",
        "MSFT,2,3,4,5,200",
        "MISSING,2,3,4,5,200",
    ])
    body = make_gzip(csv_content)
    s3 = FakeS3(body)
    session = MagicMock()

    inserted, missing = process_day(
        session,
        s3,
        "bucket",
        date(2025, 1, 2),
        {"AAPL": "id1", "MSFT": "id2"},
    )

    assert inserted == 2
    assert missing == {"MISSING"}
    session.execute.assert_called_once()
    args, kwargs = session.execute.call_args
    assert "ON CONFLICT" in str(args[0])
    assert len(args[1]) == 2  # two rows attempted
    session.commit.assert_called_once()


def test_retention_cleanup():
    session = MagicMock()
    session.execute.return_value.rowcount = 5
    removed = enforce_retention(session, days=2, as_of=date(2025, 1, 10))
    session.execute.assert_called_once()
    _, kwargs = session.execute.call_args
    assert kwargs["cutoff"] == date(2025, 1, 8)
    assert removed == 5
    session.commit.assert_called_once()


def test_idempotent_re_run():
    session = MagicMock()
    rows = [{
        "ticker_id": "id1",
        "date": date(2025, 1, 1),
        "open": 1.0,
        "high": 2.0,
        "low": 0.5,
        "close": 1.5,
        "volume": 100,
    }]

    first = insert_ohlcv(session, rows)
    second = insert_ohlcv(session, rows)

    assert first == 1
    assert second == 1  # safe to re-run due to ON CONFLICT
    assert session.execute.call_count == 2
    sql_text = str(session.execute.call_args_list[0][0][0])
    assert "ON CONFLICT" in sql_text

