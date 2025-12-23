#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import logging
import sys
from argparse import ArgumentParser
from datetime import date, datetime, timezone, timedelta

from dotenv import load_dotenv

from core.ingestion.options import (
    OptionsIngestionError,
    ingest_options_chains_from_watchlists,
    resolve_snapshot_time,
)

logger = logging.getLogger(__name__)


def _parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise SystemExit(f"Invalid date {s!r}; expected YYYY-MM-DD") from e


def _parse_snapshot_time(s: str) -> datetime:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as e:
        raise SystemExit(f"Invalid --snapshot-time {s!r}; expected ISO-8601") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def build_parser() -> ArgumentParser:
    p = ArgumentParser(
        description=(
            "A1 options chain ingestion (watchlists -> options_chains). "
            "Reads active symbols from public.watchlists, fetches options snapshots from the selected provider, "
            "and upserts into public.options_chains."
        )
    )
    p.add_argument("--db-url", default=None, help="Overrides DATABASE_URL (default: env DATABASE_URL)")
    p.add_argument(
        "--api-key",
        default=None,
        help="Overrides provider API key (default: env POLYGON_API_KEY or UNICORN_API_TOKEN depending on provider)",
    )
    p.add_argument("--as-of", default=None, type=_parse_date, help="Provider as_of date (YYYY-MM-DD)")
    p.add_argument(
        "--snapshot-time",
        default=None,
        type=_parse_snapshot_time,
        help="Snapshot identity (ISO-8601). In normal usage this is derived deterministically from --as-of or date range and should not be overridden.",
    )
    p.add_argument(
        "--start-date",
        default=None,
        type=_parse_date,
        help="Start date for range-mode historical ingestion (YYYY-MM-DD)",
    )
    p.add_argument(
        "--end-date",
        default=None,
        type=_parse_date,
        help="End date for range-mode historical ingestion (inclusive, YYYY-MM-DD)",
    )
    p.add_argument("--concurrency", default=5, type=int, help="Max concurrent symbols (default: 5)")
    p.add_argument(
        "--symbols",
        default=None,
        help="Comma-separated subset of symbols (still intersected with active watchlists)",
    )
    p.add_argument(
        "--provider",
        choices=["unicorn", "polygon"],
        default=None,
        help="Options provider (override env OPTIONS_PROVIDER; default: unicorn)",
    )
    p.add_argument(
        "--large-symbols",
        default=None,
        help="Comma-separated symbols that should be ingested serially (default: AAPL,MSFT,NVDA,TSLA)",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Overrides the default logging level (default: INFO)",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Shorthand for --log-level DEBUG",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress INFO logs (overrides --log-level unless DEBUG explicitly set)",
    )
    p.add_argument(
        "--heartbeat",
        default=25,
        type=int,
        help="Emit a heartbeat log every N symbols processed (default: 25)",
    )
    p.add_argument(
        "--run-id",
        default=None,
        help="Optional run identifier for observability and tracing",
    )
    p.add_argument(
        "--emit-summary",
        action="store_true",
        help="Emit a structured INFO summary at the end of the run",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve symbols and scheduling without fetching provider data or writing to the DB",
    )
    return p


def _current_utc_date() -> date:
    return datetime.now(timezone.utc).date()


def _iterate_date_range(start: date, end: date) -> list[date]:
    if start > end:
        raise SystemExit("--start-date must be <= --end-date")
    delta = (end - start).days
    return [start + timedelta(days=i) for i in range(delta + 1)]


def _resolve_trading_dates(start: date, end: date) -> list[date]:
    """Resolve every calendar date in the inclusive range."""
    return _iterate_date_range(start, end)


def _print_report_summary(report):
    ok_count = sum(1 for o in report.outcomes if o.ok)
    failed_count = len(report.outcomes) - ok_count
    run_id_suffix = f" run_id={report.run_id}" if report.run_id else ""
    print(
        f"✅ options ingestion complete: provider={report.provider} snapshot_time={report.snapshot_time.isoformat()} "
        f"symbols={len(report.symbols)} ok={ok_count} failed={failed_count} rows_written={report.total_rows_persisted}{run_id_suffix}"
    )
    if failed_count:
        for o in report.outcomes:
            if not o.ok:
                print(f"⚠️ {o.symbol}: {o.error}", file=sys.stderr)


def main(argv: list[str]) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    resolved_level = args.log_level.upper()
    if args.verbose:
        resolved_level = "DEBUG"
    elif args.quiet and resolved_level != "DEBUG":
        resolved_level = "WARNING"
    if args.heartbeat <= 0:
        raise SystemExit("--heartbeat must be > 0")

    logging.basicConfig(
        level=getattr(logging, resolved_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    symbols = None
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    large_symbols = None
    if args.large_symbols is not None:
        large_symbols = [s.strip().upper() for s in args.large_symbols.split(",") if s.strip()]

    range_args_provided = args.start_date is not None or args.end_date is not None
    if args.as_of is not None and range_args_provided:
        raise SystemExit("--as-of cannot be combined with --start-date/--end-date")
    if bool(args.start_date) != bool(args.end_date):
        raise SystemExit("--start-date and --end-date must be provided together for range ingestion")
    range_mode = args.start_date is not None
    if range_mode and args.snapshot_time is not None:
        raise SystemExit("--snapshot-time cannot be combined with --start-date/--end-date")
    selected_start = args.start_date
    selected_end = args.end_date

    resolved_as_of: date | None = args.as_of
    snapshot_time_for_single_day = args.snapshot_time

    if range_mode:
        dates = _resolve_trading_dates(selected_start, selected_end)
        total_dates = len(dates)
        logger.info(
            "Options ingestion range run: %s → %s (%d days)",
            selected_start.isoformat(),
            selected_end.isoformat(),
            total_dates,
            extra={"run_id": args.run_id},
        )
        logger.info(
            "A1 ingestion start",
            extra={
                "mode": "range",
                "start": selected_start.isoformat(),
                "end": selected_end.isoformat(),
                "run_id": args.run_id,
            },
        )
        if total_dates == 0:
            logger.warning(
                "Options ingestion range resolved zero dates",
                extra={"start_date": selected_start.isoformat(), "end_date": selected_end.isoformat()},
            )
            logger.info(
                "A1 ingestion complete",
                extra={
                    "mode": "range",
                    "days": 0,
                    "symbols_ok": 0,
                    "symbols_skipped": 0,
                    "run_id": args.run_id,
                },
            )
            print(
                "✅ options ingestion range complete: dates_total=0 dates_succeeded=0 "
                "dates_failed=0 symbols_ok=0 symbols_failed=0 rows_written=0"
            )
            return 0
        dates_succeeded = 0
        dates_failed = 0
        symbols_ok = 0
        symbols_failed = 0
        symbols_skipped = 0
        rows_written = 0
        last_run_id: str | None = None
        failure_details: list[dict[str, str]] = []
        for run_date in dates:
            run_snapshot = resolve_snapshot_time(run_date)
            logger.info(
                "Options ingestion range date start",
                extra={
                    "date": run_date.isoformat(),
                    "snapshot_time": run_snapshot.isoformat(),
                },
            )
            logger.info(
                "A1 snapshot resolved",
                extra={
                    "as_of": run_date.isoformat(),
                    "snapshot_time": run_snapshot.isoformat(),
                    "mode": "range",
                    "run_id": args.run_id,
                },
            )
            try:
                report = ingest_options_chains_from_watchlists(
                    db_url=args.db_url,
                    api_key=args.api_key,
                    as_of_date=run_date,
                    snapshot_time=run_snapshot,
                    concurrency=int(args.concurrency),
                    symbols=symbols,
                    provider_name=args.provider,
                    large_symbols=large_symbols,
                    run_id=args.run_id,
                    heartbeat_interval=args.heartbeat,
                    emit_summary=args.emit_summary,
                    dry_run=args.dry_run,
                )
            except Exception:
                logger.exception(
                    "Options ingestion range date failed",
                    extra={
                        "date": run_date.isoformat(),
                        "snapshot_time": run_snapshot.isoformat(),
                    },
                )
                failure_details.append(
                    {"date": run_date.isoformat(), "snapshot_time": run_snapshot.isoformat()}
                )
                dates_failed += 1
                continue

            _print_report_summary(report)
            dates_succeeded += 1
            ok_count = sum(1 for o in report.outcomes if o.ok)
            failed_count = len(report.outcomes) - ok_count
            success_count = sum(1 for o in report.outcomes if o.ok and not o.skipped)
            skipped_count = sum(1 for o in report.outcomes if o.skipped)
            symbols_ok += success_count
            symbols_skipped += skipped_count
            symbols_failed += failed_count
            rows_written += report.total_rows_persisted
            last_run_id = report.run_id
            logger.info(
                "Options ingestion range date complete",
                extra={
                    "date": run_date.isoformat(),
                    "rows_written": report.total_rows_persisted,
                    "symbols_ok": ok_count,
                    "symbols_failed": failed_count,
                },
            )

        if failure_details:
            for failure in failure_details:
                logger.warning(
                    "Options ingestion range day failed",
                    extra={
                        "date": failure["date"],
                        "snapshot_time": failure["snapshot_time"],
                    },
                )

        final_run_id = args.run_id or last_run_id
        logger.info(
            "Options ingestion range run complete",
            extra={
                "start_date": selected_start.isoformat(),
                "end_date": selected_end.isoformat(),
                "dates_total": total_dates,
                "dates_attempted": total_dates,
                "dates_succeeded": dates_succeeded,
                "dates_failed": dates_failed,
                "symbols_ok": symbols_ok,
                "symbols_failed": symbols_failed,
                "rows_written": rows_written,
                "run_id": final_run_id,
            },
        )
        logger.info(
            "A1 ingestion complete",
            extra={
                "mode": "range",
                "run_id": final_run_id,
                "days": total_dates,
                "symbols_ok": symbols_ok,
                "symbols_skipped": symbols_skipped,
            },
        )
        run_id_suffix = f" run_id={final_run_id}" if final_run_id else ""
        print(
            f"✅ options ingestion range complete: dates_total={total_dates} dates_succeeded={dates_succeeded} "
            f"dates_failed={dates_failed} symbols_ok={symbols_ok} symbols_failed={symbols_failed} rows_written={rows_written}"
            f"{run_id_suffix}"
        )
        return 0 if dates_succeeded > 0 else 1

    if not range_mode:
        if snapshot_time_for_single_day is None:
            resolved_as_of = resolved_as_of or _current_utc_date()
            snapshot_time_for_single_day = resolve_snapshot_time(resolved_as_of)

        active_as_of = resolved_as_of or snapshot_time_for_single_day.date()
        logger.info(
            "A1 ingestion start",
            extra={
                "mode": "single",
                "as_of": active_as_of.isoformat(),
                "snapshot_time": snapshot_time_for_single_day.isoformat(),
                "run_id": args.run_id,
            },
        )
        logger.info(
            "A1 snapshot resolved",
            extra={
                "as_of": active_as_of.isoformat(),
                "snapshot_time": snapshot_time_for_single_day.isoformat(),
                "mode": "single",
                "run_id": args.run_id,
            },
        )
        report = ingest_options_chains_from_watchlists(
            db_url=args.db_url,
            api_key=args.api_key,
            as_of_date=active_as_of,
            snapshot_time=snapshot_time_for_single_day,
            concurrency=int(args.concurrency),
            symbols=symbols,
            provider_name=args.provider,
            large_symbols=large_symbols,
            run_id=args.run_id,
            heartbeat_interval=args.heartbeat,
            emit_summary=args.emit_summary,
            dry_run=args.dry_run,
        )

        _print_report_summary(report)
        symbols_skipped = sum(1 for o in report.outcomes if o.skipped)
        symbols_ok = sum(1 for o in report.outcomes if o.ok and not o.skipped)
        logger.info(
            "A1 ingestion complete",
            extra={
                "mode": "single",
                "days": 1,
                "symbols_ok": symbols_ok,
                "symbols_skipped": symbols_skipped,
                "run_id": args.run_id,
            },
        )
        return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except asyncio.CancelledError:
        raise SystemExit(130)
    except OptionsIngestionError as e:
        print(f"❌ options ingestion failed: {e}", file=sys.stderr)
        raise SystemExit(2)
