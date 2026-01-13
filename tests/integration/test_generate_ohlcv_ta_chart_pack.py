from datetime import date, timedelta
from pathlib import Path
from typing import Optional
import os
import shutil

import pytest
import psycopg2
from psycopg2.extras import execute_values

from scripts.util.generate_ohlcv_ta_chart_pack import main


def _test_db_url() -> Optional[str]:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


def _has_imagemagick() -> bool:
    return shutil.which("magick") is not None or shutil.which("convert") is not None


def _has_matplotlib() -> bool:
    try:
        import matplotlib  # noqa: F401
    except Exception:
        return False
    return True


def _ensure_ticker(conn, symbol: str) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT id::text FROM tickers WHERE symbol = %s", (symbol,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO tickers (symbol, name, created_at) VALUES (%s, %s, NOW()) RETURNING id::text",
            (symbol, f"{symbol} Test"),
        )
        return cur.fetchone()[0]


def _seed_ohlcv(conn, symbol: str, start: date, bars: int) -> None:
    ticker_id = _ensure_ticker(conn, symbol)
    rows = []
    for i in range(bars):
        current = start + timedelta(days=i)
        base = 100 + i * 0.5
        open_p = base
        close_p = base + ((i % 5) - 2) * 0.2
        high_p = max(open_p, close_p) + 0.3
        low_p = min(open_p, close_p) - 0.3
        volume = 100000 + i * 1000
        rows.append((ticker_id, current, open_p, high_p, low_p, close_p, volume))
    end_date = start + timedelta(days=bars - 1)
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM ohlcv WHERE ticker_id = %s AND date >= %s AND date <= %s",
            (ticker_id, start, end_date),
        )
        execute_values(
            cur,
            """
            INSERT INTO ohlcv (ticker_id, date, open, high, low, close, volume)
            VALUES %s
            """,
            rows,
        )
    conn.commit()


def _first_run_dir(out_dir: Path) -> Path:
    run_dirs = [p for p in out_dir.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1
    return run_dirs[0]


def test_chart_pack_generates_png_and_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")
    if not _has_imagemagick():
        pytest.skip("ImageMagick is not available")
    if not _has_matplotlib():
        pytest.skip("matplotlib is not available")

    start_date = date(2024, 1, 2)
    bars = 60
    symbols = ["ZZT1", "ZZT2"]

    with psycopg2.connect(db_url) as conn:
        for symbol in symbols:
            _seed_ohlcv(conn, symbol, start_date, bars)

    monkeypatch.setenv("DATABASE_URL", db_url)

    exit_code = main(
        [
            "--symbols",
            ",".join(symbols),
            "--start-date",
            start_date.isoformat(),
            "--end-date",
            (start_date + timedelta(days=bars - 1)).isoformat(),
            "--bars",
            str(bars),
            "--ta-metrics",
            "MA,RSI,MACD,ADX,OBV",
            "--out-dir",
            str(tmp_path),
            "--pdf-batch-size",
            "2",
        ]
    )
    assert exit_code == 0

    run_dir = _first_run_dir(tmp_path)
    png_dir = run_dir / "png"
    pdf_dir = run_dir / "pdf"

    pngs = sorted(png_dir.glob("*.png"))
    pdfs = sorted(pdf_dir.glob("*.pdf"))

    assert len(pngs) == len(symbols)
    assert len(pdfs) == 1
    assert pngs[0].name.startswith("001_")
    assert pdfs[0].stat().st_size > 0
