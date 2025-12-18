from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from core.ingestion.ohlcv.s3_flatfiles import (
    build_day_aggs_key,
    default_s3_flatfiles_config,
    fetch_gzipped_csv_bytes,
    get_s3_client,
    open_gzip_bytes,
)


@dataclass(frozen=True)
class DailyLoadResult:
    loaded: list[dict[str, Any]]
    errors: list[str]


def _get_decimal(record: dict, keys: Iterable[str]) -> Decimal | None:
    for key in keys:
        value = record.get(key)
        if value in (None, ""):
            continue
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    return None


def _get_int(record: dict, keys: Iterable[str]) -> int | None:
    for key in keys:
        value = record.get(key)
        if value in (None, ""):
            continue
        try:
            return int(Decimal(str(value)))
        except (InvalidOperation, ValueError):
            return None
    return None


class S3OHLCVLoader:
    """
    Convenience loader for reading Polygon S3 day aggregates.

    Not an ingestion entry point; A0 canonical ingestion lives in `scripts/ingest_ohlcv.py`.
    """

    def __init__(self):
        self.cfg = default_s3_flatfiles_config()
        self.s3 = get_s3_client(self.cfg)

    async def load_daily(self, symbols: list[str], d: date) -> dict[str, Any]:
        wanted = {s.upper() for s in symbols}
        key = build_day_aggs_key(self.cfg.prefix, d)
        try:
            gz_bytes = fetch_gzipped_csv_bytes(self.s3, bucket=self.cfg.bucket, key=key)
        except Exception as e:
            return {"loaded": [], "errors": [f"S3 get_object failed for {key}: {e}"]}

        loaded: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            with open_gzip_bytes(gz_bytes) as text_stream:
                reader = csv.DictReader(text_stream)
                for record in reader:
                    symbol = (record.get("ticker") or record.get("symbol") or "").upper()
                    if symbol not in wanted:
                        continue

                    open_price = _get_decimal(record, ["open", "o"])
                    high_price = _get_decimal(record, ["high", "h"])
                    low_price = _get_decimal(record, ["low", "l"])
                    close_price = _get_decimal(record, ["close", "c"])
                    volume = _get_int(record, ["volume", "v"])

                    if None in (open_price, high_price, low_price, close_price, volume):
                        errors.append(f"{symbol}: invalid OHLCV fields")
                        continue

                    loaded.append(
                        {
                            "symbol": symbol,
                            "date": d,
                            "open": open_price,
                            "high": high_price,
                            "low": low_price,
                            "close": close_price,
                            "volume": volume,
                        }
                    )
        except Exception as e:
            errors.append(f"Failed to parse {key}: {e}")

        return {"loaded": loaded, "errors": errors}

