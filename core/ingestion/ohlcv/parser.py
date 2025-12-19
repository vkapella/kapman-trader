from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from .s3_flatfiles import open_gzip_bytes


@dataclass(frozen=True)
class OhlcvRow:
    ticker_id: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True)
class ParsedDay:
    date: date
    rows: list[OhlcvRow]
    missing_symbols: set[str]
    invalid_rows: int
    invalid_examples: list[str]
    duplicate_rows: int
    duplicate_rows_resolved: int


def _get_decimal(record: dict, keys: list[str]) -> Decimal | None:
    for key in keys:
        value = record.get(key)
        if value in (None, ""):
            continue
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    return None


def _get_int(record: dict, keys: list[str]) -> int | None:
    for key in keys:
        value = record.get(key)
        if value in (None, ""):
            continue
        try:
            return int(Decimal(str(value)))
        except (InvalidOperation, ValueError):
            return None
    return None


def _get_timestamp(record: dict, keys: list[str]) -> int | None:
    for key in keys:
        value = record.get(key)
        if value in (None, ""):
            continue
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None
    return None


def parse_day_aggs_gz_csv(
    gz_bytes: bytes,
    *,
    current_date: date,
    symbol_to_ticker_id: dict[str, str],
    include_symbols: set[str] | None = None,
    max_invalid_examples: int = 25,
) -> ParsedDay:
    # Promoted from archive/scripts/init/04_load_ohlcv_base.py (CSV parsing + symbol mapping)
    missing: set[str] = set()
    invalid_rows = 0
    invalid_examples: list[str] = []
    duplicate_rows = 0
    duplicate_rows_resolved = 0

    by_ticker_id: dict[str, tuple[OhlcvRow, int | None]] = {}

    with open_gzip_bytes(gz_bytes) as text_stream:
        reader = csv.DictReader(text_stream)
        for record in reader:
            symbol = (record.get("ticker") or record.get("symbol") or "").upper()
            if not symbol:
                invalid_rows += 1
                if len(invalid_examples) < max_invalid_examples:
                    invalid_examples.append("missing symbol")
                continue

            if include_symbols is not None and symbol not in include_symbols:
                continue

            ticker_id = symbol_to_ticker_id.get(symbol)
            if not ticker_id:
                missing.add(symbol)
                continue

            open_price = _get_decimal(record, ["open", "o"])
            high_price = _get_decimal(record, ["high", "h"])
            low_price = _get_decimal(record, ["low", "l"])
            close_price = _get_decimal(record, ["close", "c"])
            volume = _get_int(record, ["volume", "v"])

            if None in (open_price, high_price, low_price, close_price, volume):
                invalid_rows += 1
                if len(invalid_examples) < max_invalid_examples:
                    invalid_examples.append(f"{symbol}: missing/invalid OHLCV fields")
                continue

            ts = _get_timestamp(
                record,
                ["timestamp", "t", "sip_timestamp", "participant_timestamp", "ts"],
            )
            row = OhlcvRow(
                ticker_id=ticker_id,
                date=current_date,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
            )

            existing = by_ticker_id.get(ticker_id)
            if existing is not None:
                duplicate_rows += 1
                _, existing_ts = existing

                replace = False
                if existing_ts is None and ts is not None:
                    replace = True
                elif existing_ts is not None and ts is None:
                    replace = False
                elif existing_ts is not None and ts is not None:
                    replace = ts >= existing_ts
                else:  # both None
                    replace = True

                if replace:
                    by_ticker_id[ticker_id] = (row, ts)
                    duplicate_rows_resolved += 1
                continue

            by_ticker_id[ticker_id] = (row, ts)

    rows = sorted((row for (row, _) in by_ticker_id.values()), key=lambda r: r.ticker_id)
    return ParsedDay(
        date=current_date,
        rows=rows,
        missing_symbols=missing,
        invalid_rows=invalid_rows,
        invalid_examples=invalid_examples,
        duplicate_rows=duplicate_rows,
        duplicate_rows_resolved=duplicate_rows_resolved,
    )
