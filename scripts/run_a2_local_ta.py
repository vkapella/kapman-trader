from __future__ import annotations

import argparse
import logging
import multiprocessing
import sys
from datetime import date, datetime, timezone

import psycopg2

import core.metrics.a2_local_ta_job as a2_job
from core.ingestion.ohlcv.db import default_db_url
from core.metrics.a2_local_ta_job import (
    DEFAULT_MODEL_VERSION,
    DEFAULT_TICKER_CHUNK_SIZE,
    build_snapshot_ticker_plan,
    get_indicator_surface_for_tests,
    run_a2_local_ta_job,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KapMan A2: Compute local TA + price metrics into daily_snapshots"
    )
    parser.add_argument("--db-url", type=str, default=None, help="Override DATABASE_URL")
    parser.add_argument("--date", type=_parse_date, default=None, help="Single trading date (YYYY-MM-DD)")
    parser.add_argument("--start-date", type=_parse_date, default=None, help="Start trading date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=_parse_date, default=None, help="End trading date (YYYY-MM-DD)")
    parser.add_argument("--fill-missing", action="store_true", help="Only compute rows missing in daily_snapshots")

    parser.add_argument("--verbose", action="store_true", help="INFO-level per-ticker logging")
    parser.add_argument("--debug", action="store_true", help="DEBUG-level indicator logging (implies --verbose)")
    parser.add_argument("--quiet", action="store_true", help="Only warnings + final summary")
    parser.add_argument("--heartbeat", type=int, default=50, help="Heartbeat every N tickers (default: 50)")
    parser.add_argument(
        "--enable-pattern-indicators",
        action="store_true",
        help="Enable TA-Lib candlestick pattern indicators (CDL*)",
    )
    parser.add_argument(
        "--ticker-chunk-size",
        type=int,
        default=None,
        help=f"Tickers per chunk (default: {DEFAULT_TICKER_CHUNK_SIZE})",
    )
    parser.add_argument("--workers", type=int, default=None, help="Worker processes (default: auto)")
    parser.add_argument("--max-workers", type=int, default=6, help="Hard cap on workers (default: 6)")

    return parser


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date: {value} (expected YYYY-MM-DD)") from e


def _resolve_snapshot_time(trading_date: date) -> datetime:
    return datetime(
        year=trading_date.year,
        month=trading_date.month,
        day=trading_date.day,
        hour=23,
        minute=59,
        second=59,
        microsecond=999999,
        tzinfo=timezone.utc,
    )


def _ohlcv_dates_in_range(conn, start: date, end: date) -> list[date]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT date
            FROM ohlcv
            WHERE date >= %s AND date <= %s
            ORDER BY date ASC
            """,
            (start, end),
        )
        return [r[0] for r in cur.fetchall()]


def _latest_ohlcv_date(conn) -> date | None:
    with conn.cursor() as cur:
        cur.execute("SELECT max(date) FROM ohlcv")
        return cur.fetchone()[0]


class _QuietFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return (
            bool(getattr(record, "a2_summary", False))
            or bool(getattr(record, "a2_run_config", False))
            or record.levelno >= logging.WARNING
        )


def _configure_logging(*, quiet: bool, debug: bool) -> logging.Logger:
    log = logging.getLogger("kapman.a2")
    log.handlers.clear()
    log.propagate = False

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    handler.setLevel(logging.DEBUG if debug else logging.INFO)
    if quiet:
        handler.addFilter(_QuietFilter())

    log.addHandler(handler)
    log.setLevel(logging.DEBUG if debug else logging.INFO)

    return log


def _log_run_config(log: logging.Logger, line: str) -> None:
    log.info("[A2] RUN CONFIG %s", line, extra={"a2_run_config": True})


def _resolve_ticker_chunk_size(args: argparse.Namespace) -> tuple[str, int]:
    if getattr(args, "ticker_chunk_size", None) is not None:
        return ("override", int(args.ticker_chunk_size))
    return ("default", DEFAULT_TICKER_CHUNK_SIZE)


def _resolve_workers(
    args: argparse.Namespace,
) -> tuple[str, int, int, int, int | None]:
    try:
        cpu_count_raw = multiprocessing.cpu_count()
    except NotImplementedError:
        cpu_count_raw = 1
    cpu_count = int(cpu_count_raw) if cpu_count_raw else 1
    max_workers = int(getattr(args, "max_workers", 6))
    if max_workers <= 0:
        raise SystemExit("--max-workers must be >= 1")

    requested = getattr(args, "workers", None)
    if requested is not None:
        requested_i = int(requested)
        if requested_i <= 0:
            raise SystemExit("--workers must be >= 1")
        effective = min(requested_i, max_workers)
        return ("override", effective, max_workers, cpu_count, requested_i)

    auto = max(1, min(4, cpu_count - 2))
    effective = min(auto, max_workers)
    return ("auto", effective, max_workers, cpu_count, None)


def _log_run_header(
    log: logging.Logger,
    *,
    ticker_chunk_size: int,
    chunk_size_source: str,
    total_tickers: int,
    total_chunks: int,
    workers: int,
    workers_source: str,
    workers_requested: int | None,
    max_workers: int,
    cpu_count: int,
) -> None:
    log.info(
        "[A2] RUN HEADER ticker_chunk_size=%s chunk_size_source=%s total_tickers=%s total_chunks=%s workers=%s workers_source=%s workers_requested=%s max_workers=%s cpu_count=%s deterministic=true",
        ticker_chunk_size,
        chunk_size_source,
        total_tickers,
        total_chunks,
        workers,
        workers_source,
        workers_requested,
        max_workers,
        cpu_count,
        extra={"a2_run_config": True},
    )


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    debug = bool(args.debug)
    verbose = bool(args.verbose) or debug
    quiet = bool(args.quiet)
    enable_patterns = bool(args.enable_pattern_indicators)
    chunk_size_source, ticker_chunk_size = _resolve_ticker_chunk_size(args)
    workers_source, workers, max_workers, cpu_count, workers_requested = _resolve_workers(args)

    if quiet:
        debug = False
        verbose = False

    log = _configure_logging(quiet=quiet, debug=debug)

    db_url = args.db_url or default_db_url()

    with psycopg2.connect(db_url) as conn:
        snapshot_mode: str
        run_date: date | None = None
        if args.date is not None:
            snapshot_mode = "single_date"
            run_date = args.date
            dates = [args.date]
        elif args.start_date is not None or args.end_date is not None:
            if args.start_date is None or args.end_date is None:
                raise SystemExit("--start-date and --end-date must be provided together")
            snapshot_mode = "date_range"
            dates = _ohlcv_dates_in_range(conn, args.start_date, args.end_date)
        else:
            latest = _latest_ohlcv_date(conn)
            if latest is None:
                log.warning("[A2] ohlcv is empty; nothing to compute")
                return 0
            snapshot_mode = "single_date"
            run_date = latest
            dates = [latest]

        a2_job._snapshot_time_utc = _resolve_snapshot_time
        for trading_date in dates:
            snapshot_time = _resolve_snapshot_time(trading_date)
            log.info(
                "A2 resolved snapshot_time=%s for trading_date=%s",
                snapshot_time.isoformat(),
                trading_date.isoformat(),
            )

        plan = build_snapshot_ticker_plan(conn, snapshot_dates=dates, fill_missing=bool(args.fill_missing))
        total_tickers_all_dates = sum(len(v) for v in plan.values())
        total_chunks_all_dates = sum(
            (len(v) + ticker_chunk_size - 1) // ticker_chunk_size for v in plan.values()
        )

        _log_run_header(
            log,
            ticker_chunk_size=ticker_chunk_size,
            chunk_size_source=chunk_size_source,
            total_tickers=total_tickers_all_dates,
            total_chunks=total_chunks_all_dates,
            workers=workers,
            workers_source=workers_source,
            workers_requested=workers_requested,
            max_workers=max_workers,
            cpu_count=cpu_count,
        )

        surface = get_indicator_surface_for_tests()
        technical_categories = ["momentum", "trend", "volatility", "volume", "others"]
        technical_categories_str = f"[{', '.join(technical_categories)}]"
        technical_count = sum(
            len(info.get("outputs", []))
            for category, indicators in surface.INDICATOR_REGISTRY.items()
            for info in indicators.values()
        )
        pattern_count = len(surface.PATTERN_RECOGNITION_OUTPUT_KEYS)
        if enable_patterns:
            backend_available = bool(getattr(surface, "talib", None) is not None)
            pattern_reason = "enabled" if backend_available else "backend_unavailable"
        else:
            backend_available = False
            pattern_reason = "disabled_by_flag"

        _log_run_config(log, f"snapshot_mode={snapshot_mode}")
        if snapshot_mode == "single_date":
            _log_run_config(log, f"date={run_date.isoformat() if run_date else ''}")
        else:
            _log_run_config(log, f"start_date={args.start_date.isoformat()}")
            _log_run_config(log, f"end_date={args.end_date.isoformat()}")
        _log_run_config(log, f"fill_missing={bool(args.fill_missing)}")

        _log_run_config(log, f"ticker_chunk_size={ticker_chunk_size}")
        _log_run_config(log, f"ticker_chunk_size_source={chunk_size_source}")
        _log_run_config(log, f"total_tickers={total_tickers_all_dates}")
        _log_run_config(log, f"total_chunks={total_chunks_all_dates}")

        _log_run_config(log, "technical_indicators=enabled")
        _log_run_config(log, f"technical_indicator_categories={technical_categories_str}")
        _log_run_config(log, f"technical_indicator_count={technical_count}")

        _log_run_config(log, "price_metrics=enabled")
        _log_run_config(log, "price_metrics_list=[rvol, vsi, hv]")

        _log_run_config(log, f"pattern_indicators_enabled={enable_patterns}")
        _log_run_config(log, f"pattern_backend_available={backend_available}")
        _log_run_config(log, f"pattern_indicator_count={pattern_count}")
        _log_run_config(log, f"pattern_indicators_reason={pattern_reason}")

        _log_run_config(log, "flags:")
        _log_run_config(log, f"  enable_pattern_indicators={enable_patterns}")
        _log_run_config(log, f"  verbose={verbose}")
        _log_run_config(log, f"  debug={debug}")
        _log_run_config(log, f"  quiet={quiet}")
        _log_run_config(log, f"  log_heartbeat_interval={int(args.heartbeat)}")
        _log_run_config(log, f"  ticker_chunk_size={ticker_chunk_size}")
        _log_run_config(log, f"  workers={workers}")
        _log_run_config(log, f"  workers_source={workers_source}")
        _log_run_config(log, f"  workers_requested={workers_requested}")
        _log_run_config(log, f"  max_workers={max_workers}")

        _log_run_config(log, f"model_version={DEFAULT_MODEL_VERSION}")
        _log_run_config(log, "deterministic=true")

        run_a2_local_ta_job(
            conn,
            snapshot_dates=dates,
            fill_missing=args.fill_missing,
            heartbeat_every=int(args.heartbeat),
            verbose=verbose,
            enable_pattern_indicators=enable_patterns,
            ticker_chunk_size=ticker_chunk_size,
            ticker_ids_by_date=plan,
            workers=workers,
            db_url=db_url,
            log=log,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
