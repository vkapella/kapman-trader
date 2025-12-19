from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta

from . import db as db_mod
from .parser import ParsedDay, parse_day_aggs_gz_csv
from .s3_flatfiles import (
    S3FlatfilesConfig,
    build_day_aggs_key,
    default_s3_flatfiles_config,
    fetch_gzipped_csv_bytes,
    get_s3_client,
    iter_calendar_dates,
    list_available_dates_in_range,
)


class IngestionError(RuntimeError):
    pass


@dataclass(frozen=True)
class IngestionRequest:
    mode: str
    start: date
    end: date
    dates: list[date]


@dataclass(frozen=True)
class IngestionReport:
    requested: IngestionRequest
    ingested_dates: list[date]
    total_rows_written: int
    missing_symbols_count: int
    missing_symbols_examples: list[str]
    duplicate_rows_seen: int
    duplicate_rows_resolved: int


logger = logging.getLogger(__name__)


def compute_base_range(*, days: int, end: date | None = None) -> tuple[date, date]:
    if days <= 0:
        raise IngestionError("--days must be > 0")
    end_date = end or (date.today() - timedelta(days=1))
    start_date = end_date - timedelta(days=days - 1)
    return start_date, end_date


def resolve_available_dates_to_ingest(
    s3,
    *,
    bucket: str,
    prefix: str,
    start: date,
    end: date,
    require_any: bool = True,
) -> list[date]:
    available = list_available_dates_in_range(
        s3,
        bucket=bucket,
        prefix=prefix,
        start=start,
        end=end,
    )
    if require_any and not available:
        raise IngestionError(
            f"No Polygon S3 daily files found in range {start.isoformat()}..{end.isoformat()} "
            f"under prefix {prefix!r}"
        )
    return available


def resolve_calendar_dates_to_ingest(
    s3,
    *,
    bucket: str,
    prefix: str,
    start: date,
    end: date,
) -> list[date]:
    desired = list(iter_calendar_dates(start, end))
    available = set(
        list_available_dates_in_range(
            s3,
            bucket=bucket,
            prefix=prefix,
            start=start,
            end=end,
        )
    )
    missing = [d for d in desired if d not in available]
    if missing:
        sample = ", ".join(d.isoformat() for d in missing[:15])
        raise IngestionError(
            f"Missing Polygon S3 daily files for {len(missing)} requested dates "
            f"(sample: {sample}) under prefix {prefix!r}"
        )
    return desired


def ingest_ohlcv(
    *,
    db_url: str | None = None,
    s3_cfg: S3FlatfilesConfig | None = None,
    mode: str,
    dates: list[date],
    symbols: set[str] | None = None,
    strict_missing_symbols: bool = True,
    max_missing_symbol_examples: int = 25,
) -> IngestionReport:
    if not dates:
        raise IngestionError("No dates resolved for ingestion")

    dates = sorted(set(dates))
    start = dates[0]
    end = dates[-1]

    include_symbols = {s.upper() for s in symbols} if symbols else None

    db_url = db_url or db_mod.default_db_url()
    s3_cfg = s3_cfg or default_s3_flatfiles_config()

    s3 = get_s3_client(s3_cfg)

    with db_mod.connect(db_url) as conn:
        tickers_count = db_mod.count_table(conn, "tickers")
        if tickers_count == 0:
            raise IngestionError("tickers table is empty; load ticker universe before OHLCV")

        pre_ohlcv_count = db_mod.count_table(conn, "ohlcv_daily")
        symbol_map = db_mod.load_symbol_map(conn)
        if not symbol_map:
            raise IngestionError("No tickers available to map symbols; tickers table is empty")

        if include_symbols is not None:
            include_symbols = {s for s in include_symbols if s in symbol_map}
            if not include_symbols:
                raise IngestionError("No requested symbols exist in tickers table")

        total_rows_written = 0
        ingested_dates: list[date] = []
        missing_symbols_examples: list[str] = []
        missing_symbols_total = 0
        duplicate_rows_seen = 0
        duplicate_rows_resolved = 0

        for d in dates:
            key = build_day_aggs_key(s3_cfg.prefix, d)
            try:
                gz_bytes = fetch_gzipped_csv_bytes(s3, bucket=s3_cfg.bucket, key=key)
            except Exception as e:
                raise IngestionError(f"S3 get_object failed for {key}: {e}") from e

            parsed: ParsedDay = parse_day_aggs_gz_csv(
                gz_bytes,
                current_date=d,
                symbol_to_ticker_id=symbol_map,
                include_symbols=include_symbols,
            )

            if parsed.invalid_rows:
                raise IngestionError(
                    f"{d.isoformat()}: encountered {parsed.invalid_rows} invalid rows "
                    f"(examples: {parsed.invalid_examples})"
                )
            if parsed.missing_symbols:
                missing_symbols_total += len(parsed.missing_symbols)
                sample = sorted(parsed.missing_symbols)[: max_missing_symbol_examples]
                if len(missing_symbols_examples) < max_missing_symbol_examples:
                    remaining = max_missing_symbol_examples - len(missing_symbols_examples)
                    missing_symbols_examples.extend(sample[:remaining])
                if strict_missing_symbols:
                    raise IngestionError(
                        f"{d.isoformat()}: {len(parsed.missing_symbols)} symbols present in S3 "
                        f"but missing from tickers table (examples: {sample})"
                    )
                logger.warning(
                    "%s: skipping %d symbols missing from tickers (sample=%s)",
                    d.isoformat(),
                    len(parsed.missing_symbols),
                    sample,
                )
            if not parsed.rows:
                raise IngestionError(f"{d.isoformat()}: S3 file parsed to 0 valid OHLCV rows")

            duplicate_rows_seen += parsed.duplicate_rows
            duplicate_rows_resolved += parsed.duplicate_rows_resolved

            db_mod.upsert_ohlcv_rows(conn, parsed.rows)
            total_rows_written += len(parsed.rows)
            ingested_dates.append(d)

            # Per-day existence validation (coarse, but fail-fast).
            if db_mod.count_ohlcv_for_date(conn, d) == 0:
                raise IngestionError(f"{d.isoformat()}: ohlcv_daily has 0 rows after ingestion")

        if ingested_dates != dates:
            raise IngestionError(
                "Internal error: ingested date list does not match resolved date list"
            )

        post_ohlcv_count = db_mod.count_table(conn, "ohlcv_daily")
        if pre_ohlcv_count == 0 and post_ohlcv_count == 0:
            raise IngestionError("ohlcv_daily remained empty after ingestion")

        # Date coverage validation: ensure DB has rows within requested bounds.
        if ingested_dates:
            range_count = db_mod.count_ohlcv_in_range(conn, min(ingested_dates), max(ingested_dates))
            if range_count == 0:
                raise IngestionError("ohlcv_daily has 0 rows in ingested date range after ingestion")

    return IngestionReport(
        requested=IngestionRequest(mode=mode, start=start, end=end, dates=dates),
        ingested_dates=ingested_dates,
        total_rows_written=total_rows_written,
        missing_symbols_count=missing_symbols_total,
        missing_symbols_examples=missing_symbols_examples,
        duplicate_rows_seen=duplicate_rows_seen,
        duplicate_rows_resolved=duplicate_rows_resolved,
    )


def default_base_days() -> int:
    raw = os.environ.get("OHLCV_HISTORY_DAYS")
    if not raw:
        return 730
    try:
        return int(raw)
    except ValueError as e:
        raise IngestionError(f"Invalid OHLCV_HISTORY_DAYS={raw!r}") from e
