import gzip
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest

from core.ingestion.ohlcv.parser import parse_day_aggs_gz_csv


def _gz_bytes(text: str) -> bytes:
    buf = BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(text.encode("utf-8"))
    return buf.getvalue()


@pytest.mark.unit
def test_parse_day_aggs_parses_valid_row() -> None:
    gz = _gz_bytes(
        "ticker,volume,open,close,high,low,window_start\n"
        "AAPL,100,150.0,152.0,153.0,149.5,0\n"
    )
    parsed = parse_day_aggs_gz_csv(
        gz,
        current_date=date(2025, 12, 5),
        symbol_to_ticker_id={"AAPL": "t1"},
    )
    assert parsed.invalid_rows == 0
    assert parsed.missing_symbols == set()
    assert len(parsed.rows) == 1
    row = parsed.rows[0]
    assert row.ticker_id == "t1"
    assert row.date == date(2025, 12, 5)
    assert row.open == Decimal("150.0")
    assert row.close == Decimal("152.0")
    assert row.volume == 100


@pytest.mark.unit
def test_parse_day_aggs_reports_missing_symbols() -> None:
    gz = _gz_bytes(
        "ticker,volume,open,close,high,low\n"
        "AAPL,100,150.0,152.0,153.0,149.5\n"
        "MSFT,200,300.0,301.0,305.0,299.0\n"
    )
    parsed = parse_day_aggs_gz_csv(
        gz,
        current_date=date(2025, 12, 5),
        symbol_to_ticker_id={"AAPL": "t1"},
    )
    assert parsed.missing_symbols == {"MSFT"}
    assert len(parsed.rows) == 1


@pytest.mark.unit
def test_parse_day_aggs_counts_invalid_rows() -> None:
    gz = _gz_bytes(
        "ticker,volume,open,close,high,low\n"
        "AAPL,NOT_A_NUMBER,150.0,152.0,153.0,149.5\n"
    )
    parsed = parse_day_aggs_gz_csv(
        gz,
        current_date=date(2025, 12, 5),
        symbol_to_ticker_id={"AAPL": "t1"},
    )
    assert parsed.invalid_rows == 1
    assert parsed.rows == []


@pytest.mark.unit
def test_parse_day_aggs_dedupes_identical_rows() -> None:
    gz = _gz_bytes(
        "ticker,volume,open,close,high,low\n"
        "AAPL,100,150.0,152.0,153.0,149.5\n"
        "AAPL,100,150.0,152.0,153.0,149.5\n"
    )
    parsed = parse_day_aggs_gz_csv(
        gz,
        current_date=date(2025, 12, 5),
        symbol_to_ticker_id={"AAPL": "t1"},
    )
    assert parsed.duplicate_rows == 1
    assert len(parsed.rows) == 1


@pytest.mark.unit
def test_parse_day_aggs_raises_on_inconsistent_duplicates() -> None:
    gz = _gz_bytes(
        "ticker,volume,open,close,high,low\n"
        "AAPL,100,150.0,152.0,153.0,149.5\n"
        "AAPL,100,150.0,999.0,153.0,149.5\n"
    )
    with pytest.raises(RuntimeError, match="Inconsistent duplicate rows"):
        parse_day_aggs_gz_csv(
            gz,
            current_date=date(2025, 12, 5),
            symbol_to_ticker_id={"AAPL": "t1"},
        )

