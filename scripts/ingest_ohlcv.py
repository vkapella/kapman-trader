#!/usr/bin/env python3
from __future__ import annotations

import logging
import sys
from argparse import ArgumentParser
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from threading import Event, Lock, Thread
from time import monotonic

from dotenv import load_dotenv

from core.ingestion.ohlcv import db as ohlcv_db
from core.ingestion.ohlcv import pipeline as ohlcv_pipeline
from core.ingestion.ohlcv.pipeline import (
    IngestionError,
    default_base_days,
    ingest_ohlcv,
    resolve_calendar_dates_to_ingest,
)
from core.ingestion.ohlcv.s3_flatfiles import default_s3_flatfiles_config, get_s3_client, list_latest_available_dates
from core.ingestion.tickers.loader import TickerBootstrapError, ensure_universe_loaded


def _parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise SystemExit(f"Invalid date {s!r}; expected YYYY-MM-DD") from e


def _yesterday() -> date:
    return date.today() - timedelta(days=1)


def _format_symbol_sample(symbols: set[str] | list[str], *, cap: int) -> str:
    if cap <= 0:
        return ""
    ordered = sorted(set(symbols))
    shown = ordered[:cap]
    more = len(ordered) - len(shown)
    rendered = ", ".join(shown)
    if more > 0:
        rendered = f"{rendered} (+{more} more)"
    return rendered


@dataclass
class _ProgressState:
    total_dates: int
    verbosity: str
    max_symbol_sample: int

    started_at: float = field(default_factory=monotonic)
    dates_processed: int = 0
    rows_written: int = 0
    missing_symbols_count: int = 0
    duplicates_seen: int = 0
    duplicates_resolved: int = 0

    _rate_samples: deque[tuple[float, int]] = field(default_factory=lambda: deque(maxlen=64))
    _pending_day: date | None = None
    _pending_rows: int = 0
    _pending_missing: int = 0
    _pending_dup_seen: int = 0
    _pending_dup_resolved: int = 0

    _lock: Lock = field(default_factory=Lock, repr=False)

    def record_parse(self, parsed) -> None:
        with self._lock:
            self.missing_symbols_count += len(parsed.missing_symbols)
            self.duplicates_seen += int(parsed.duplicate_rows)
            self.duplicates_resolved += int(parsed.duplicate_rows_resolved)

            self._pending_day = parsed.date
            self._pending_rows = len(parsed.rows)
            self._pending_missing = len(parsed.missing_symbols)
            self._pending_dup_seen = int(parsed.duplicate_rows)
            self._pending_dup_resolved = int(parsed.duplicate_rows_resolved)

    def record_write(self, *, rows_written: int) -> tuple[date | None, str | None]:
        with self._lock:
            self.dates_processed += 1
            self.rows_written += rows_written
            self._rate_samples.append((monotonic(), self.rows_written))

            if self.verbosity != "debug":
                return None, None

            d = self._pending_day
            if d is None:
                return None, None

            line = (
                f"date={d.isoformat()} rows_written={rows_written} "
                f"missing_symbols={self._pending_missing} "
                f"duplicates_seen={self._pending_dup_seen} "
                f"duplicates_resolved={self._pending_dup_resolved}"
            )
            self._pending_day = None
            return d, line

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            rate = 0.0
            if len(self._rate_samples) >= 2:
                (t0, r0) = self._rate_samples[0]
                (t1, r1) = self._rate_samples[-1]
                dt = max(1e-6, t1 - t0)
                rate = (r1 - r0) / dt
            return {
                "dates_processed": self.dates_processed,
                "total_dates": self.total_dates,
                "rows_written": self.rows_written,
                "rows_per_sec": rate,
                "missing_symbols_count": self.missing_symbols_count,
                "duplicates_seen": self.duplicates_seen,
                "duplicates_resolved": self.duplicates_resolved,
            }


class _IngestionInstrumentation:
    def __init__(self, state: _ProgressState):
        self._state = state
        self._orig_parse = ohlcv_pipeline.parse_day_aggs_gz_csv
        self._orig_upsert = ohlcv_pipeline.db_mod.upsert_ohlcv_rows

    def __enter__(self) -> _ProgressState:
        def parse_wrapper(*args, **kwargs):
            parsed = self._orig_parse(*args, **kwargs)
            self._state.record_parse(parsed)
            return parsed

        def upsert_wrapper(conn, rows):
            result = self._orig_upsert(conn, rows)
            _, debug_line = self._state.record_write(rows_written=len(rows))
            if debug_line:
                print(f"… {debug_line}", file=sys.stderr)
            return result

        ohlcv_pipeline.parse_day_aggs_gz_csv = parse_wrapper
        ohlcv_pipeline.db_mod.upsert_ohlcv_rows = upsert_wrapper
        return self._state

    def __exit__(self, exc_type, exc, tb) -> None:
        ohlcv_pipeline.parse_day_aggs_gz_csv = self._orig_parse
        ohlcv_pipeline.db_mod.upsert_ohlcv_rows = self._orig_upsert


def _run_heartbeat(*, state: _ProgressState, stop: Event, interval_s: float) -> None:
    while not stop.wait(interval_s):
        snap = state.snapshot()
        print(
            "… progress: "
            f"{snap['dates_processed']}/{snap['total_dates']} dates, "
            f"rows_written={snap['rows_written']}, "
            f"rows/sec={float(snap['rows_per_sec']):.1f}, "
            f"missing_symbols={snap['missing_symbols_count']}, "
            f"duplicates_seen={snap['duplicates_seen']}, "
            f"duplicates_resolved={snap['duplicates_resolved']}",
            file=sys.stderr,
        )


def build_parser() -> ArgumentParser:
    p = ArgumentParser(
        description=(
            "Canonical OHLCV ingestion pipeline (A0). "
            "Reads Polygon S3 flat files and upserts into public.ohlcv."
        )
    )
    p.add_argument("--db-url", default=None, help="Overrides DATABASE_URL (default: env DATABASE_URL)")

    sub = p.add_subparsers(dest="mode", required=True)

    def add_common_flags(sp: ArgumentParser) -> None:
        sp.add_argument("--db-url", default=None, help="Overrides DATABASE_URL (default: env DATABASE_URL)")
        sp.add_argument(
            "--verbosity",
            choices=["quiet", "normal", "debug"],
            default="normal",
            help="Output mode: quiet (summary only), normal (heartbeat), debug (per-date + samples)",
        )
        sp.add_argument(
            "--max-symbol-sample",
            type=int,
            default=10,
            help="Max symbols to show when samples are printed (debug only; default: 10)",
        )
        sp.add_argument(
            "--symbols",
            default=None,
            help="Comma-separated symbol subset (NON-AUTHORITATIVE; default: full universe from tickers table)",
        )
        sp.add_argument(
            "--strict-missing-symbols",
            action="store_true",
            help=(
                "Fail ingestion if Polygon flatfiles contain symbols missing from the tickers table. "
                "By default, all modes skip unknown symbols (recommended for curated universes)."
            ),
        )
        sp.add_argument(
            "--no-ticker-bootstrap",
            action="store_true",
            help="Disable automatic ticker bootstrapping; if tickers is empty, fail as-is",
        )

    base = sub.add_parser("base", help="Full-universe base load (last N available trading days)")
    add_common_flags(base)
    base.add_argument(
        "--days",
        type=int,
        default=None,
        help="Number of available daily files to ingest (default: OHLCV_HISTORY_DAYS or 730)",
    )
    base.add_argument(
        "--as-of",
        type=_parse_date,
        default=None,
        help="Latest date to consider (default: yesterday)",
    )

    inc = sub.add_parser("incremental", help="Incremental daily ingestion (skips unknown symbols by default)")
    add_common_flags(inc)
    inc.add_argument("--date", type=_parse_date, default=None, help="Single date (YYYY-MM-DD)")
    inc.add_argument("--start", type=_parse_date, default=None, help="Start date (YYYY-MM-DD)")
    inc.add_argument("--end", type=_parse_date, default=None, help="End date (YYYY-MM-DD)")

    backfill = sub.add_parser("backfill", help="Bounded historical backfill (skips unknown symbols by default)")
    add_common_flags(backfill)
    backfill.add_argument("--start", type=_parse_date, required=True, help="Start date (YYYY-MM-DD)")
    backfill.add_argument("--end", type=_parse_date, required=True, help="End date (YYYY-MM-DD)")

    return p


def main(argv: list[str]) -> int:
    load_dotenv()

    args = build_parser().parse_args(argv)

    db_url = args.db_url or ohlcv_db.default_db_url()
    verbosity = getattr(args, "verbosity", "normal")
    max_symbol_sample = int(getattr(args, "max_symbol_sample", 10))
    if max_symbol_sample < 0:
        raise SystemExit("--max-symbol-sample must be >= 0")

    # Silence pipeline per-date missing symbol warnings; the CLI reports aggregated counts instead.
    ohlcv_pipeline.logger.setLevel(logging.ERROR)

    requested_symbols: set[str] | None = None
    if args.symbols:
        requested_symbols = {s.strip().upper() for s in args.symbols.split(",") if s.strip()}
        if not requested_symbols:
            raise SystemExit("--symbols provided but no valid symbols parsed")
        if verbosity == "debug":
            sample = _format_symbol_sample(requested_symbols, cap=max_symbol_sample)
            if sample:
                print(
                    f"⚠️ NON-AUTHORITATIVE subset mode enabled: symbols_count={len(requested_symbols)} "
                    f"(sample: {sample})",
                    file=sys.stderr,
                )
            else:
                print(
                    f"⚠️ NON-AUTHORITATIVE subset mode enabled: symbols_count={len(requested_symbols)}",
                    file=sys.stderr,
                )
        elif verbosity != "quiet":
            print(
                f"⚠️ NON-AUTHORITATIVE subset mode enabled: symbols_count={len(requested_symbols)} "
                f"(use --verbosity debug for samples)",
                file=sys.stderr,
            )

    with ohlcv_db.connect(db_url) as conn:
        tickers_count = ohlcv_db.count_table(conn, "tickers")
        if tickers_count == 0 and not args.no_ticker_bootstrap:
            try:
                ensure_universe_loaded(conn, force=False)
            except TickerBootstrapError as e:
                raise SystemExit(f"Ticker bootstrap failed: {e}") from e

        tickers_count = ohlcv_db.count_table(conn, "tickers")
        if tickers_count == 0:
            raise IngestionError("tickers table is empty; load ticker universe before OHLCV")

        if requested_symbols is not None:
            symbol_map = ohlcv_db.load_symbol_map(conn)
            existing = set(symbol_map.keys())
            missing = sorted(requested_symbols - existing)
            if missing:
                if verbosity == "debug":
                    sample = _format_symbol_sample(missing, cap=max_symbol_sample)
                    if sample:
                        print(
                            f"⚠️ Requested symbols missing from tickers and will be ignored: count={len(missing)} "
                            f"(sample: {sample})",
                            file=sys.stderr,
                        )
                    else:
                        print(
                            f"⚠️ Requested symbols missing from tickers and will be ignored: count={len(missing)}",
                            file=sys.stderr,
                        )
                elif verbosity != "quiet":
                    print(
                        f"⚠️ Requested symbols missing from tickers and will be ignored: count={len(missing)} "
                        f"(use --verbosity debug for samples)",
                        file=sys.stderr,
                    )
            requested_symbols = requested_symbols & existing

    s3_cfg = default_s3_flatfiles_config()
    s3 = get_s3_client(s3_cfg)

    if args.mode == "base":
        days = args.days if args.days is not None else default_base_days()
        as_of = args.as_of or _yesterday()
        dates = list_latest_available_dates(
            s3,
            bucket=s3_cfg.bucket,
            prefix=s3_cfg.prefix,
            limit=days,
            as_of=as_of,
        )
    elif args.mode == "incremental":
        if args.date and (args.start or args.end):
            raise SystemExit("Use either --date or --start/--end (not both)")
        if args.date:
            start = end = args.date
        else:
            start = args.start or _yesterday()
            end = args.end or start
        dates = resolve_calendar_dates_to_ingest(
            s3,
            bucket=s3_cfg.bucket,
            prefix=s3_cfg.prefix,
            start=start,
            end=end,
        )
    elif args.mode == "backfill":
        start = args.start
        end = args.end
        dates = resolve_calendar_dates_to_ingest(
            s3,
            bucket=s3_cfg.bucket,
            prefix=s3_cfg.prefix,
            start=start,
            end=end,
        )
    else:
        raise SystemExit(f"Unknown mode: {args.mode!r}")

    # Strict missing symbol enforcement is opt-in only.
    strict_missing_symbols = bool(args.strict_missing_symbols)
    if verbosity != "quiet":
        if dates:
            print(
                f"▶️ OHLCV ingestion start: mode={args.mode} "
                f"dates={dates[0].isoformat()}..{dates[-1].isoformat()} "
                f"files={len(dates)} strict_missing_symbols={strict_missing_symbols}",
                file=sys.stderr,
            )

    state = _ProgressState(
        total_dates=len(dates),
        verbosity=verbosity,
        max_symbol_sample=max_symbol_sample,
    )
    stop = Event()
    hb_thread: Thread | None = None
    if verbosity in ("normal", "debug"):
        hb_thread = Thread(
            target=_run_heartbeat,
            kwargs={"state": state, "stop": stop, "interval_s": 60.0},
            daemon=True,
        )
        hb_thread.start()

    try:
        with _IngestionInstrumentation(state):
            report = ingest_ohlcv(
                db_url=db_url,
                s3_cfg=s3_cfg,
                mode=args.mode,
                dates=dates,
                symbols=requested_symbols,
                strict_missing_symbols=strict_missing_symbols,
            )
    finally:
        stop.set()
        if hb_thread is not None:
            hb_thread.join(timeout=1.0)

    print(
        f"✅ OHLCV ingestion complete: mode={report.requested.mode} "
        f"dates={report.requested.start.isoformat()}..{report.requested.end.isoformat()} "
        f"({len(report.ingested_dates)} files), rows_written={report.total_rows_written} "
        f"missing_symbols={report.missing_symbols_count} "
        f"duplicates_seen={report.duplicate_rows_seen} "
        f"duplicates_resolved={report.duplicate_rows_resolved}"
    )
    if report.missing_symbols_count:
        if verbosity != "quiet":
            print(
                f"⚠️ Missing symbols encountered (skipped): count={report.missing_symbols_count}",
                file=sys.stderr,
            )
            if verbosity == "debug":
                sample = _format_symbol_sample(report.missing_symbols_examples, cap=max_symbol_sample)
                if sample:
                    print(f"⚠️ Missing symbols sample (max {max_symbol_sample}): {sample}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except IngestionError as e:
        print(f"❌ OHLCV ingestion failed: {e}", file=sys.stderr)
        raise SystemExit(2)
