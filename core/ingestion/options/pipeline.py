from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator, Awaitable, Callable, Iterable, Protocol

import httpx
from psycopg2.extras import execute_values

from core.providers.market_data.polygon_options import PolygonOptionsProvider
from core.providers.market_data.unicorn_options import UnicornOptionsProvider

from . import db as options_db
from .normalizer import (
    NormalizedOptionContract,
    NormalizedPolygonSnapshot,
    normalize_polygon_snapshot_results,
    normalize_unicorn_contracts,
    polygon_snapshots_to_option_contracts,
)


logger = logging.getLogger(__name__)

_API_KEY_RE = re.compile(r"(?i)(apikey|api_key|access_token|token)=([^&\\s]+)")
_URL_QUERY_RE = re.compile(r"(https?://[^\\s\\)\\]]*?)\\?[^\\s\\)\\]]+")
_REDACTION_INSTALLED = False
_SUPPORTED_PROVIDERS = {"unicorn", "polygon"}
_DEFAULT_PROVIDER = "unicorn"


def _redact_secrets(value: str) -> str:
    return _API_KEY_RE.sub(lambda m: f"{m.group(1)}=REDACTED", value)


def _strip_url_queries(value: str) -> str:
    return _URL_QUERY_RE.sub(r"\\1", value)


class _ApiKeyRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if isinstance(record.msg, str):
            record.msg = _redact_secrets(_strip_url_queries(record.msg))
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    _redact_secrets(_strip_url_queries(a)) if isinstance(a, str) else a for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (_redact_secrets(_strip_url_queries(v)) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
        for key, value in list(record.__dict__.items()):
            if isinstance(value, str):
                record.__dict__[key] = _redact_secrets(_strip_url_queries(value))
        return True


def _install_request_log_redaction() -> None:
    global _REDACTION_INSTALLED
    if _REDACTION_INSTALLED:
        return

    redaction_filter = _ApiKeyRedactionFilter()
    for name in ("httpx", "httpcore"):
        lib_logger = logging.getLogger(name)
        lib_logger.setLevel(max(lib_logger.level or logging.WARNING, logging.WARNING))
        lib_logger.addFilter(redaction_filter)

    _REDACTION_INSTALLED = True


class OptionsProvider(Protocol):
    name: str
    request_timeout: float

    async def fetch_options_snapshot_chain(
        self,
        underlying: str,
        *,
        snapshot_date: date,
        client: httpx.AsyncClient,
        on_page: Callable[[int], Awaitable[None]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        ...

    def normalize_results(
        self,
        raw_results: list[dict[str, Any]],
        *,
        snapshot_date: date,
    ) -> list[NormalizedOptionContract]:
        ...


class PolygonOptionsProviderAdapter:
    name = "polygon"

    def __init__(self, api_key: str) -> None:
        self._provider = PolygonOptionsProvider(api_key=api_key)
        self.request_timeout = self._provider.request_timeout

    async def fetch_options_snapshot_chain(
        self,
        underlying: str,
        *,
        snapshot_date: date,
        client: httpx.AsyncClient,
        on_page: Callable[[int], Awaitable[None]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        async for row in self._provider.fetch_options_snapshot_chain(
            underlying,
            client=client,
            on_page=on_page,
        ):
            yield row

    def normalize_results(
        self,
        raw_results: list[dict[str, Any]],
        *,
        snapshot_date: date,
    ) -> list[NormalizedOptionContract]:
        normalized = normalize_polygon_snapshot_results(raw_results)
        return polygon_snapshots_to_option_contracts(normalized)


class OptionsIngestionError(RuntimeError):
    pass


class OptionsIngestionLockError(OptionsIngestionError):
    pass


@dataclass(frozen=True)
class SymbolIngestionOutcome:
    symbol: str
    ok: bool
    snapshot_rows_fetched: int
    snapshot_rows_normalized: int
    rows_persisted: int
    elapsed_s: float
    error_type: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class OptionsIngestionReport:
    snapshot_time: datetime
    provider: str
    symbols: list[str]
    outcomes: list[SymbolIngestionOutcome]
    total_rows_persisted: int
    elapsed_s: float
    cancelled: bool = False


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def dedupe_and_sort_symbols(symbols: Iterable[str]) -> list[str]:
    return sorted({str(s).strip().upper() for s in symbols if s and str(s).strip()})


def _resolve_provider_name(cli_provider: str | None) -> str:
    env_value = os.environ.get("OPTIONS_PROVIDER")
    provider = (cli_provider or env_value or _DEFAULT_PROVIDER).strip().lower()
    if provider not in _SUPPORTED_PROVIDERS:
        raise OptionsIngestionError(f"Unsupported provider {provider!r}; expected one of {sorted(_SUPPORTED_PROVIDERS)}")

    source = "cli" if cli_provider else "env" if env_value else "default"
    logger.debug(
        "Options provider resolved",
        extra={
            "stage": "pipeline",
            "provider": provider,
            "source": source,
        },
    )
    return provider


def _resolve_api_key(provider_name: str, api_key: str | None) -> str:
    if api_key:
        return api_key

    env_keys = ["POLYGON_API_KEY"] if provider_name == "polygon" else ["UNICORN_API_TOKEN", "UNICORN_API_KEY", "EODHD_API_TOKEN"]
    for key in env_keys:
        value = os.environ.get(key)
        if value:
            return value

    raise OptionsIngestionError(f"{env_keys[0]} is not set for provider {provider_name}")


def _format_error_safe(exc: BaseException) -> str:
    return _redact_secrets(_strip_url_queries(f"{type(exc).__name__}: {exc}"))


def _format_hhmmss(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _build_provider(provider_name: str, api_key: str) -> OptionsProvider:
    if provider_name == "polygon":
        return PolygonOptionsProviderAdapter(api_key=api_key)
    if provider_name == "unicorn":
        return UnicornOptionsProvider(api_token=api_key)
    raise OptionsIngestionError(f"Unsupported provider {provider_name!r}")


def _build_upsert_rows(
    normalized: list[NormalizedOptionContract],
    *,
    ticker_id: str,
    snapshot_time: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for item in normalized:
        exp = item.db_expiration_date()
        strike = item.db_strike_price()
        opt_type = item.db_option_type()
        if exp is None or strike is None or opt_type is None:
            invalid.append(
                {
                    "contract_ticker": item.contract_symbol,
                    "expiration_date": exp,
                    "strike_price": strike,
                    "contract_type": item.option_type,
                }
            )
            continue

        rows.append(
            {
                "time": snapshot_time,
                "ticker_id": ticker_id,
                "expiration_date": exp,
                "strike_price": strike,
                "option_type": opt_type,
                "bid": item.bid,
                "ask": item.ask,
                "last": item.last,
                "volume": item.volume,
                "open_interest": item.open_interest,
                "implied_volatility": item.implied_volatility,
                "delta": item.delta,
                "gamma": item.gamma,
                "theta": item.theta,
                "vega": item.vega,
            }
        )
    return rows, invalid


def _upsert_options_chains_rows_transactional(conn, *, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    insert_sql = """
        INSERT INTO options_chains (
            time,
            ticker_id,
            expiration_date,
            strike_price,
            option_type,
            bid,
            ask,
            last,
            volume,
            open_interest,
            implied_volatility,
            delta,
            gamma,
            theta,
            vega
        )
        VALUES %s
        ON CONFLICT (time, ticker_id, expiration_date, strike_price, option_type)
        DO UPDATE SET
            bid = EXCLUDED.bid,
            ask = EXCLUDED.ask,
            last = EXCLUDED.last,
            volume = EXCLUDED.volume,
            open_interest = EXCLUDED.open_interest,
            implied_volatility = EXCLUDED.implied_volatility,
            delta = EXCLUDED.delta,
            gamma = EXCLUDED.gamma,
            theta = EXCLUDED.theta,
            vega = EXCLUDED.vega
        WHERE (options_chains.bid, options_chains.ask, options_chains.last, options_chains.volume,
               options_chains.open_interest, options_chains.implied_volatility, options_chains.delta,
               options_chains.gamma, options_chains.theta, options_chains.vega)
              IS DISTINCT FROM
              (EXCLUDED.bid, EXCLUDED.ask, EXCLUDED.last, EXCLUDED.volume,
               EXCLUDED.open_interest, EXCLUDED.implied_volatility, EXCLUDED.delta,
               EXCLUDED.gamma, EXCLUDED.theta, EXCLUDED.vega)
    """

    values = [
        (
            r["time"],
            r["ticker_id"],
            r["expiration_date"],
            r["strike_price"],
            r["option_type"],
            r.get("bid"),
            r.get("ask"),
            r.get("last"),
            r.get("volume"),
            r.get("open_interest"),
            r.get("implied_volatility"),
            r.get("delta"),
            r.get("gamma"),
            r.get("theta"),
            r.get("vega"),
        )
        for r in rows
    ]

    total = 0
    with conn.cursor() as cur:
        batch_size = 2000
        for i in range(0, len(values), batch_size):
            batch = values[i : i + batch_size]
            execute_values(cur, insert_sql, batch, page_size=len(batch))
            total += len(batch)
    return total


async def _ingest_one_symbol(
    *,
    db_url: str,
    provider: OptionsProvider,
    symbol: str,
    ticker_id: str,
    snapshot_time: datetime,
    http_client: httpx.AsyncClient,
    progress_cb: Any,
) -> SymbolIngestionOutcome:
    started = time.perf_counter()
    snapshot_rows_fetched = 0
    pages_fetched = 0
    snapshot_date = snapshot_time.date()
    raw_results: list[dict[str, Any]] = []

    async def on_page(rows_in_page: int) -> None:
        nonlocal pages_fetched
        pages_fetched += 1
        await progress_cb(snapshot_rows_fetched_delta=0, rows_persisted_delta=0, pages_fetched_delta=1)

    try:
        try:
            async for row in provider.fetch_options_snapshot_chain(
                symbol,
                snapshot_date=snapshot_date,
                client=http_client,
                on_page=on_page,
            ):
                snapshot_rows_fetched += 1
                raw_results.append(row)
                await progress_cb(snapshot_rows_fetched_delta=1, rows_persisted_delta=0, pages_fetched_delta=0)
        except asyncio.CancelledError:
            raise
        except httpx.HTTPStatusError as exc:
            status = int(exc.response.status_code) if exc.response is not None else None
            logger.error(
                "Options snapshot fetch failed",
                extra={
                    "stage": "pipeline",
                    "symbol": symbol,
                    "provider": getattr(provider, "name", None),
                    "status_code": status,
                    "root_cause": f"http_{status}" if status is not None else type(exc).__name__,
                    "error": _format_error_safe(exc),
                },
            )
            raise
        except Exception as exc:
            logger.error(
                "Options snapshot fetch failed",
                extra={
                    "stage": "pipeline",
                    "symbol": symbol,
                    "provider": getattr(provider, "name", None),
                    "root_cause": type(exc).__name__,
                    "error": _format_error_safe(exc),
                },
            )
            raise

        snapshots_normalized = provider.normalize_results(raw_results, snapshot_date=snapshot_date)
        rows, invalid = _build_upsert_rows(
            snapshots_normalized,
            ticker_id=ticker_id,
            snapshot_time=snapshot_time,
        )

        if invalid:
            logger.error(
                "Some snapshot rows cannot be persisted (missing required fields)",
                extra={
                    "stage": "normalizer",
                    "symbol": symbol,
                    "provider": getattr(provider, "name", None),
                    "root_cause": "missing_required_fields",
                    "invalid_rows": len(invalid),
                    "normalized_rows": len(snapshots_normalized),
                    "example_contract_ticker": invalid[0].get("contract_ticker") if invalid else None,
                },
            )

        def _write_db(rows_to_write: list[dict[str, Any]]) -> int:
            total_rows = len(rows_to_write)
            null_counts = {
                "expiration_date": sum(1 for r in rows_to_write if r.get("expiration_date") is None),
                "strike_price": sum(1 for r in rows_to_write if r.get("strike_price") is None),
                "option_type": sum(1 for r in rows_to_write if r.get("option_type") is None),
            }
            seen_keys: set[tuple] = set()
            dup_count = 0
            for row in rows_to_write:
                key = (
                    row.get("expiration_date"),
                    row.get("strike_price"),
                    row.get("option_type"),
                )
                if key in seen_keys:
                    dup_count += 1
                else:
                    seen_keys.add(key)

            logger.info(
                "Preparing to persist option rows",
                extra={
                    "stage": "pipeline",
                    "symbol": symbol,
                    "rows_total": total_rows,
                    "null_counts": null_counts,
                    "duplicate_key_count": dup_count,
                    "sample_rows": rows_to_write[:3],
                },
            )
            conn = options_db.connect(db_url)
            try:
                conn.autocommit = False
                rows_written = _upsert_options_chains_rows_transactional(conn, rows=rows_to_write)
                conn.commit()
                return rows_written
            except Exception as exc:
                sample_row = rows_to_write[0] if rows_to_write else None
                logger.error(
                    "Options ingestion DB commit failed",
                    extra={
                        "stage": "db",
                        "symbol": symbol,
                        "provider": getattr(provider, "name", None),
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                        "sample_row": sample_row,
                    },
                )
                conn.rollback()
                raise
            finally:
                conn.close()

        rows_to_write: list[dict[str, Any]] = rows
        provider_kind = getattr(provider, "name", "").lower()
        if provider_kind == "unicorn":
            dedupe_map: dict[tuple, dict[str, Any]] = {}
            duplicates = 0
            for row in rows:
                key = (
                    row["time"],
                    row["ticker_id"],
                    row["expiration_date"],
                    row["strike_price"],
                    row["option_type"],
                )
                if key in dedupe_map:
                    duplicates += 1
                dedupe_map[key] = row
            rows_to_write = list(dedupe_map.values())
            assert len(rows_to_write) == len(set(dedupe_map.keys())), (
                f"Provider {provider_kind} dedup mismatch: duplicate_key_count={duplicates}"
            )
            logger.debug(
                "Deduplicated option rows before DB write",
                extra={
                    "stage": "pipeline",
                    "symbol": symbol,
                    "provider": provider_kind,
                    "rows_before": len(rows),
                    "rows_after": len(rows_to_write),
                    "duplicate_key_count": duplicates,
                },
            )

        try:
            rows_persisted = await asyncio.to_thread(_write_db, rows_to_write)
        except Exception as exc:
            logger.exception(
                "Options ingestion DB commit failed",
                extra={
                    "stage": "db",
                    "symbol": symbol,
                    "provider": getattr(provider, "name", None),
                },
            )
            raise

        elapsed = time.perf_counter() - started
        ok = True
        log_extra = {
            "stage": "pipeline",
            "symbol": symbol,
            "provider": getattr(provider, "name", None),
            "rows_persisted": rows_persisted,
            "snapshot_rows_fetched": snapshot_rows_fetched,
            "snapshot_rows_normalized": len(snapshots_normalized),
            "pages_fetched": pages_fetched,
            "duration_ms": int(round(elapsed * 1000)),
        }
        if rows_persisted > 0:
            logger.info("Options ingestion symbol committed", extra=log_extra)
        else:
            logger.info(
                "Options ingestion symbol committed with zero rows",
                extra={**log_extra, "root_cause": "zero_rows_persisted"},
            )

        await progress_cb(snapshot_rows_fetched_delta=0, rows_persisted_delta=rows_persisted, pages_fetched_delta=0)
        return SymbolIngestionOutcome(
            symbol=symbol,
            ok=ok,
            snapshot_rows_fetched=snapshot_rows_fetched,
            snapshot_rows_normalized=len(snapshots_normalized),
            rows_persisted=rows_persisted,
            elapsed_s=elapsed,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        elapsed = time.perf_counter() - started
        logger.error(
            "Options ingestion symbol failed",
            extra={
                "stage": "pipeline",
                "symbol": symbol,
                "provider": getattr(provider, "name", None),
                "rows_persisted": 0,
                "snapshot_rows_fetched": snapshot_rows_fetched,
                "pages_fetched": pages_fetched,
                "root_cause": type(exc).__name__,
                "error": _format_error_safe(exc),
            },
        )
        return SymbolIngestionOutcome(
            symbol=symbol,
            ok=False,
            snapshot_rows_fetched=snapshot_rows_fetched,
            snapshot_rows_normalized=0,
            rows_persisted=0,
            elapsed_s=elapsed,
            error_type=type(exc).__name__,
            error=_format_error_safe(exc),
        )


async def _run_ingestion(
    *,
    db_url: str,
    api_key: str | None = None,
    provider: OptionsProvider,
    provider_name: str | None = None,
    snapshot_time: datetime,
    as_of_date: date | None,
    concurrency: int,
    symbols: list[str],
    mode: str,
) -> OptionsIngestionReport:
    started = time.perf_counter()
    _install_request_log_redaction()

    provider_name = provider_name or getattr(provider, "name", _DEFAULT_PROVIDER)
    symbols_total = len(symbols)
    semaphore = asyncio.Semaphore(concurrency)

    logger.info(
        "Options ingestion started",
        extra={
            "stage": "pipeline",
            "mode": mode,
            "provider": provider_name,
            "snapshot_time": snapshot_time.isoformat(),
            "as_of": as_of_date.isoformat() if as_of_date else None,
            "symbols_total": symbols_total,
            "concurrency": concurrency,
        },
    )

    progress_lock = asyncio.Lock()
    progress = {
        "symbols_completed": 0,
        "symbols_ok": 0,
        "symbols_failed": 0,
        "snapshot_rows_fetched_total": 0,
        "rows_persisted_total": 0,
        "pages_fetched_total": 0,
        "last_progress_s": started,
    }

    async def report_progress(
        *,
        snapshot_rows_fetched_delta: int,
        rows_persisted_delta: int,
        pages_fetched_delta: int,
    ) -> None:
        async with progress_lock:
            progress["snapshot_rows_fetched_total"] += int(snapshot_rows_fetched_delta)
            progress["rows_persisted_total"] += int(rows_persisted_delta)
            progress["pages_fetched_total"] += int(pages_fetched_delta)
            progress["last_progress_s"] = time.perf_counter()

    async def heartbeat() -> None:
        interval_s = float(os.environ.get("KAPMAN_OPTIONS_INGEST_PROGRESS_S") or 30.0)
        try:
            while True:
                await asyncio.sleep(interval_s)
                async with progress_lock:
                    completed = int(progress["symbols_completed"])
                    ok = int(progress["symbols_ok"])
                    failed = int(progress["symbols_failed"])
                    fetched_total = int(progress["snapshot_rows_fetched_total"])
                    persisted_total = int(progress["rows_persisted_total"])
                    pages_fetched_total = int(progress["pages_fetched_total"])

                elapsed_s = max(0.0, time.perf_counter() - started)
                logger.info(
                    "Options ingestion progress",
                    extra={
                        "stage": "pipeline",
                        "mode": mode,
                        "provider": provider_name,
                        "snapshot_time": snapshot_time.isoformat(),
                        "symbols_completed": completed,
                        "symbols_total": symbols_total,
                        "symbols_succeeded": ok,
                        "symbols_failed": failed,
                        "snapshot_rows_fetched_total": fetched_total,
                        "rows_persisted_total": persisted_total,
                        "pages_fetched_total": pages_fetched_total,
                        "elapsed_s": round(elapsed_s, 6),
                    },
                )
        except asyncio.CancelledError:
            return

    run_cancelled = False
    outcomes: list[SymbolIngestionOutcome] = []

    async with httpx.AsyncClient(timeout=provider.request_timeout) as http_client:
        with options_db.connect(db_url) as lock_conn:
            lock_key = options_db.options_ingest_lock_key()
            if not options_db.try_advisory_lock(lock_conn, lock_key):
                raise OptionsIngestionLockError("Options ingestion is already running (advisory lock not acquired)")

            ticker_ids = options_db.fetch_ticker_ids(lock_conn, symbols)

            async def run_symbol(sym: str) -> SymbolIngestionOutcome:
                async with semaphore:
                    sym_started = time.perf_counter()
                    ticker_id = ticker_ids.get(sym)
                    if not ticker_id:
                        logger.error(
                            "Options ingestion symbol failed (missing ticker_id)",
                            extra={
                                "stage": "pipeline",
                                "symbol": sym,
                                "provider": provider_name,
                                "root_cause": "missing_ticker_id",
                            },
                        )
                        elapsed = time.perf_counter() - sym_started
                        return SymbolIngestionOutcome(
                            symbol=sym,
                            ok=False,
                            snapshot_rows_fetched=0,
                            snapshot_rows_normalized=0,
                            rows_persisted=0,
                            elapsed_s=elapsed,
                            error_type="missing_ticker_id",
                            error="Missing ticker_id for symbol (tickers table does not contain symbol)",
                        )

                    outcome = await _ingest_one_symbol(
                        db_url=db_url,
                        provider=provider,
                        symbol=sym,
                        ticker_id=ticker_id,
                        snapshot_time=snapshot_time,
                        http_client=http_client,
                        progress_cb=report_progress,
                    )

                    async with progress_lock:
                        progress["symbols_completed"] += 1
                        if outcome.ok:
                            progress["symbols_ok"] += 1
                        else:
                            progress["symbols_failed"] += 1
                        progress["last_progress_s"] = time.perf_counter()

                    return outcome

            runner_tasks = [asyncio.create_task(run_symbol(s)) for s in symbols]
            heartbeat_task: asyncio.Task | None = None
            try:
                heartbeat_task = asyncio.create_task(heartbeat())
                outcomes = list(await asyncio.gather(*runner_tasks))
            except asyncio.CancelledError:
                run_cancelled = True
                for t in runner_tasks:
                    t.cancel()
                results: list[object] = []
                with contextlib.suppress(asyncio.CancelledError):
                    results = list(await asyncio.gather(*runner_tasks, return_exceptions=True))
                outcomes = [r for r in results if isinstance(r, SymbolIngestionOutcome)]
            finally:
                if heartbeat_task is not None:
                    heartbeat_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await heartbeat_task
                try:
                    options_db.advisory_unlock(lock_conn, lock_key)
                except Exception:
                    logger.exception("Failed to release advisory lock", extra={"stage": "pipeline"})

    elapsed = time.perf_counter() - started
    total_rows_persisted = sum(int(o.rows_persisted) for o in outcomes)
    total_ok = sum(1 for o in outcomes if o.ok)
    total_failed = sum(1 for o in outcomes if not o.ok)
    total_pages_fetched = int(progress["pages_fetched_total"])
    total_rows_fetched = int(progress["snapshot_rows_fetched_total"])

    if run_cancelled:
        return OptionsIngestionReport(
            snapshot_time=snapshot_time,
            provider=provider_name,
            symbols=symbols,
            outcomes=outcomes,
            total_rows_persisted=total_rows_persisted,
            elapsed_s=elapsed,
            cancelled=True,
        )

    logger.info(
        "Options ingestion run complete",
        extra={
            "stage": "pipeline",
            "mode": mode,
            "provider": provider_name,
            "snapshot_time": snapshot_time.isoformat(),
            "symbols_total": symbols_total,
            "symbols_succeeded": total_ok,
            "symbols_failed": total_failed,
            "rows_persisted_total": total_rows_persisted,
            "pages_fetched_total": total_pages_fetched,
            "elapsed_s": round(elapsed, 6),
            "duration": _format_hhmmss(elapsed),
        },
    )

    if symbols_total > 0 and total_ok == 0:
        raise OptionsIngestionError("Options ingestion failed (all symbols failed)")

    return OptionsIngestionReport(
        snapshot_time=snapshot_time,
        provider=provider_name,
        symbols=symbols,
        outcomes=outcomes,
        total_rows_persisted=total_rows_persisted,
        elapsed_s=elapsed,
        cancelled=False,
    )


def ingest_options_chains_from_watchlists(
    *,
    db_url: str | None = None,
    api_key: str | None = None,
    as_of_date: date | None = None,
    snapshot_time: datetime | None = None,
    concurrency: int = 5,
    symbols: Iterable[str] | None = None,
    provider: OptionsProvider | None = None,
    provider_name: str | None = None,
) -> OptionsIngestionReport:
    if concurrency <= 0:
        raise OptionsIngestionError("concurrency must be > 0")

    db_url = db_url or options_db.default_db_url()
    snapshot_time = snapshot_time or _utcnow()
    resolved_provider_name = getattr(provider, "name", None) or _resolve_provider_name(provider_name)

    resolved_api_key = api_key
    provider_impl = provider
    if provider_impl is None:
        resolved_api_key = _resolve_api_key(resolved_provider_name, api_key)
        provider_impl = _build_provider(resolved_provider_name, resolved_api_key)

    if isinstance(provider_impl, PolygonOptionsProvider):
        provider_impl = PolygonOptionsProviderAdapter(api_key=provider_impl.api_key)

    with options_db.connect(db_url) as conn:
        watchlist_symbols = options_db.fetch_active_watchlist_symbols(conn)

    selected = dedupe_and_sort_symbols(watchlist_symbols)
    if symbols is not None:
        requested = dedupe_and_sort_symbols(symbols)
        selected_set = set(selected)
        selected = [s for s in requested if s in selected_set]

    if not selected:
        raise OptionsIngestionError("No active watchlist symbols resolved for options ingestion")

    mode = "adhoc" if symbols is not None else "batch"
    return asyncio.run(
        _run_ingestion(
            db_url=db_url,
            api_key=resolved_api_key,
            provider=provider_impl,
            provider_name=resolved_provider_name,
            snapshot_time=snapshot_time,
            as_of_date=as_of_date,
            concurrency=concurrency,
            symbols=selected,
            mode=mode,
        )
    )
