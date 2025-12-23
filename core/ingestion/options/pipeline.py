from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import os
import re
import time
from collections import deque
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
_DEFAULT_LARGE_SYMBOLS = {"AAPL", "MSFT", "NVDA", "TSLA"}


def _large_symbol_timeout(base_timeout: float) -> float:
    return max(base_timeout * 2, base_timeout + 20.0, 60.0)


def derive_run_id(
    provider_name: str,
    symbols: list[str],
    snapshot_time: datetime,
    as_of_date: date | None,
    mode: str,
) -> str:
    normalized_symbols = ",".join(symbols)
    components = [
        provider_name,
        snapshot_time.isoformat(),
        as_of_date.isoformat() if as_of_date else "",
        mode,
        normalized_symbols,
    ]
    digest = hashlib.sha1("|".join(components).encode("utf-8")).hexdigest()
    return digest[:8]


class RequestRateLimiter:
    def __init__(
        self,
        *,
        max_requests_per_minute: int = 850,
        window_s: float = 60.0,
        target_spacing_s: float = 0.07,
    ) -> None:
        self._max_requests = max_requests_per_minute
        self._window_s = window_s
        self._spacing_s = target_spacing_s
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()
        self._last_request_ts = 0.0

    async def wait_for_slot(self) -> None:
        while True:
            now = time.monotonic()
            sleep_duration = 0.0
            async with self._lock:
                cutoff = now - self._window_s
                while self._timestamps and self._timestamps[0] <= cutoff:
                    self._timestamps.popleft()

                if len(self._timestamps) >= self._max_requests:
                    earliest = self._timestamps[0]
                    sleep_duration = max(0.0, earliest + self._window_s - now)
                else:
                    elapsed = now - self._last_request_ts if self._last_request_ts else None
                    if elapsed is not None and elapsed < self._spacing_s:
                        sleep_duration = self._spacing_s - elapsed
                    else:
                        timestamp = now
                        self._timestamps.append(timestamp)
                        self._last_request_ts = timestamp
                        return
            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)
            else:
                await asyncio.sleep(0)

    async def handle_rate_headers(self, response: httpx.Response) -> None:
        remaining_raw = response.headers.get("X-RateLimit-Remaining")
        if remaining_raw is None:
            return
        try:
            remaining = int(remaining_raw)
        except Exception:
            return

        if remaining >= 50:
            return

        limit_raw = response.headers.get("X-RateLimit-Limit")
        limit_value = None
        if limit_raw is not None:
            try:
                limit_value = int(limit_raw)
            except Exception:
                limit_value = None

        sleep_duration = 5.0 + min(5.0, (50 - remaining) * (5.0 / 49))
        sleep_duration = min(10.0, max(5.0, sleep_duration))
        logger.warning(
            "Low rate-limit remaining, pausing outbound requests",
            extra={
                "stage": "rate_limit",
                "remaining": remaining,
                "limit": limit_value,
                "sleep_s": round(sleep_duration, 3),
            },
        )
        await asyncio.sleep(sleep_duration)


GLOBAL_REQUEST_RATE_LIMITER = RequestRateLimiter()


class ThrottledAsyncClient:
    def __init__(self, client: httpx.AsyncClient, limiter: RequestRateLimiter) -> None:
        self._client = client
        self._limiter = limiter

    async def __aenter__(self) -> "ThrottledAsyncClient":
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool | None:
        return await self._client.__aexit__(exc_type, exc, tb)

    async def _send(self, sender: Callable[..., Awaitable[httpx.Response]], *args, **kwargs) -> httpx.Response:
        await self._limiter.wait_for_slot()
        response = await sender(*args, **kwargs)
        await self._limiter.handle_rate_headers(response)
        return response

    async def get(self, *args, **kwargs) -> httpx.Response:
        return await self._send(self._client.get, *args, **kwargs)

    async def request(self, method: str, *args, **kwargs) -> httpx.Response:
        return await self._send(self._client.request, method, *args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._client, item)


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
    skipped: bool = False


@dataclass(frozen=True)
class OptionsIngestionReport:
    snapshot_time: datetime
    provider: str
    symbols: list[str]
    outcomes: list[SymbolIngestionOutcome]
    total_rows_persisted: int
    elapsed_s: float
    cancelled: bool = False
    run_id: str | None = None


def resolve_snapshot_time(as_of_date: date) -> datetime:
    """Resolve an as_of date to the deterministic snapshot time at 23:59:59 UTC."""
    return datetime(
        as_of_date.year,
        as_of_date.month,
        as_of_date.day,
        23,
        59,
        59,
        tzinfo=timezone.utc,
    )


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


def _option_conflict_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("time"),
        row.get("ticker_id"),
        row.get("expiration_date"),
        row.get("strike_price"),
        row.get("option_type"),
    )


def _should_replace_row(existing: dict[str, Any], candidate: dict[str, Any]) -> bool:
    for field in ("open_interest", "gamma"):
        cand_has = candidate.get(field) is not None
        exist_has = existing.get(field) is not None
        if cand_has != exist_has:
            return cand_has

    candidate_volume = candidate.get("volume")
    existing_volume = existing.get("volume")
    if existing_volume is None and candidate_volume is None:
        return False
    if existing_volume is None:
        return True
    if candidate_volume is None:
        return False
    return candidate_volume > existing_volume


def deduplicate_option_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    dedupe_map: dict[tuple[Any, ...], dict[str, Any]] = {}
    duplicates = 0
    for row in rows:
        key = _option_conflict_key(row)
        existing = dedupe_map.get(key)
        if existing is None:
            dedupe_map[key] = row
            continue
        duplicates += 1
        if _should_replace_row(existing, row):
            dedupe_map[key] = row

    deduped_rows = list(dedupe_map.values())
    assert len(deduped_rows) == len(dedupe_map), "option dedup result mismatch"
    return deduped_rows, duplicates


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

        provider_kind = getattr(provider, "name", "").lower()
        rows_to_write, duplicate_key_count = deduplicate_option_rows(rows)
        if duplicate_key_count:
            logger.debug(
                "Deduplicated option rows before DB write",
                extra={
                    "stage": "pipeline",
                    "symbol": symbol,
                    "provider": provider_kind,
                    "rows_before": len(rows),
                    "rows_after": len(rows_to_write),
                    "duplicate_key_count": duplicate_key_count,
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
    large_symbols: frozenset[str] | None = None,
    large_symbol_source: str | None = None,
    run_id: str | None = None,
    heartbeat_interval: int = 25,
    emit_summary: bool = False,
    dry_run: bool = False,
) -> OptionsIngestionReport:
    started = time.perf_counter()
    _install_request_log_redaction()

    provider_name = provider_name or getattr(provider, "name", _DEFAULT_PROVIDER)
    resolved_run_id = run_id or derive_run_id(
        provider_name,
        symbols,
        snapshot_time,
        as_of_date,
        mode,
    )
    symbols_total = len(symbols)
    requested_concurrency = concurrency
    effective_concurrency = max(1, min(concurrency, 3))
    semaphore = asyncio.Semaphore(effective_concurrency)

    normalized_large_symbols = frozenset(
        str(s).strip().upper()
        for s in large_symbols
        if s and str(s).strip()
    ) if large_symbols else frozenset()
    resolved_large_symbol_source = large_symbol_source or "none"

    logger.info(
        "Options ingestion started",
        extra={
            "stage": "pipeline",
            "mode": mode,
            "provider": provider_name,
            "snapshot_time": snapshot_time.isoformat(),
            "as_of": as_of_date.isoformat() if as_of_date else None,
            "symbols_total": symbols_total,
            "concurrency": effective_concurrency,
            "requested_concurrency": requested_concurrency,
            "run_id": resolved_run_id,
        },
    )

    large_symbols_display = ", ".join(sorted(normalized_large_symbols)) if normalized_large_symbols else "none"
    logger.info(
        "[A1] Large-symbol isolation configured for: %s (source=%s)",
        large_symbols_display,
        resolved_large_symbol_source,
        extra={
            "stage": "pipeline",
            "provider": provider_name,
            "large_symbols": list(sorted(normalized_large_symbols)),
            "large_symbol_source": resolved_large_symbol_source,
            "run_id": resolved_run_id,
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
    if heartbeat_interval and heartbeat_interval > 0:
        next_heartbeat_threshold = heartbeat_interval
    else:
        next_heartbeat_threshold = float("inf")

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

    def _log_progress(current_symbol: str | None, snapshot: dict[str, Any]) -> None:
        logger.info(
            "Options ingestion progress",
            extra={
                "stage": "pipeline",
                "mode": mode,
                "provider": provider_name,
                "snapshot_time": snapshot_time.isoformat(),
                "symbols_completed": snapshot["symbols_completed"],
                "symbols_total": symbols_total,
                "symbols_succeeded": snapshot["symbols_succeeded"],
                "symbols_failed": snapshot["symbols_failed"],
                "snapshot_rows_fetched_total": snapshot["snapshot_rows_fetched_total"],
                "rows_persisted_total": snapshot["rows_persisted_total"],
                "pages_fetched_total": snapshot["pages_fetched_total"],
                "elapsed_s": snapshot["elapsed_s"],
                "current_symbol": current_symbol,
                "run_id": resolved_run_id,
            },
        )

    async def _record_outcome(outcome: SymbolIngestionOutcome, *, current_symbol: str | None) -> None:
        nonlocal next_heartbeat_threshold
        should_log = False
        snapshot: dict[str, Any] = {}
        async with progress_lock:
            progress["symbols_completed"] += 1
            progress["symbols_ok"] += int(outcome.ok)
            progress["symbols_failed"] += int(not outcome.ok)
            progress["last_progress_s"] = time.perf_counter()
            symbols_completed = int(progress["symbols_completed"])
            snapshot = {
                "symbols_completed": symbols_completed,
                "symbols_succeeded": int(progress["symbols_ok"]),
                "symbols_failed": int(progress["symbols_failed"]),
                "snapshot_rows_fetched_total": int(progress["snapshot_rows_fetched_total"]),
                "rows_persisted_total": int(progress["rows_persisted_total"]),
                "pages_fetched_total": int(progress["pages_fetched_total"]),
                "elapsed_s": round(max(0.0, time.perf_counter() - started), 6),
            }
            if heartbeat_interval and symbols_completed >= next_heartbeat_threshold:
                should_log = True
                next_heartbeat_threshold = symbols_completed + heartbeat_interval
        if should_log:
            _log_progress(current_symbol, snapshot)

    async def heartbeat() -> None:
        interval_s = float(os.environ.get("KAPMAN_OPTIONS_INGEST_PROGRESS_S") or 30.0)
        try:
            while True:
                await asyncio.sleep(interval_s)
                async with progress_lock:
                    snapshot = {
                        "symbols_completed": int(progress["symbols_completed"]),
                        "symbols_succeeded": int(progress["symbols_ok"]),
                        "symbols_failed": int(progress["symbols_failed"]),
                        "snapshot_rows_fetched_total": int(progress["snapshot_rows_fetched_total"]),
                        "rows_persisted_total": int(progress["rows_persisted_total"]),
                        "pages_fetched_total": int(progress["pages_fetched_total"]),
                        "elapsed_s": round(max(0.0, time.perf_counter() - started), 6),
                    }
                _log_progress(None, snapshot)
        except asyncio.CancelledError:
            return

    run_cancelled = False
    outcomes: list[SymbolIngestionOutcome] = []

    async def _run_with_clients(
        default_http_client: ThrottledAsyncClient,
        large_symbol_http_client: ThrottledAsyncClient,
    ) -> tuple[list[SymbolIngestionOutcome], list[SymbolIngestionOutcome]]:
        nonlocal run_cancelled
        with options_db.connect(db_url) as lock_conn:
            lock_key = options_db.options_ingest_lock_key()
            if not options_db.try_advisory_lock(lock_conn, lock_key):
                raise OptionsIngestionLockError("Options ingestion is already running (advisory lock not acquired)")

            ticker_ids = options_db.fetch_ticker_ids(lock_conn, symbols)

            skipped_outcomes: list[SymbolIngestionOutcome] = []
            symbols_to_process: list[str] = []
            for sym in symbols:
                ticker_id = ticker_ids.get(sym)
                if ticker_id and options_db.has_snapshot_rows(
                    lock_conn,
                    ticker_id=ticker_id,
                    snapshot_time=snapshot_time,
                ):
                    logger.info(
                        "A1 symbol skipped",
                        extra={
                            "stage": "pipeline",
                            "symbol": sym,
                            "provider": provider_name,
                            "snapshot_time": snapshot_time.isoformat(),
                            "reason": "already_ingested",
                            "run_id": resolved_run_id,
                        },
                    )
                    outcome = SymbolIngestionOutcome(
                        symbol=sym,
                        ok=True,
                        snapshot_rows_fetched=0,
                        snapshot_rows_normalized=0,
                        rows_persisted=0,
                        elapsed_s=0.0,
                        skipped=True,
                    )
                    skipped_outcomes.append(outcome)
                    await _record_outcome(outcome, current_symbol=sym)
                    continue
                symbols_to_process.append(sym)

            large_symbol_lock = asyncio.Lock()

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
                        outcome = SymbolIngestionOutcome(
                            symbol=sym,
                            ok=False,
                            snapshot_rows_fetched=0,
                            snapshot_rows_normalized=0,
                            rows_persisted=0,
                            elapsed_s=elapsed,
                            error_type="missing_ticker_id",
                            error="Missing ticker_id for symbol (tickers table does not contain symbol)",
                        )
                        await _record_outcome(outcome, current_symbol=sym)
                        return outcome

                    if dry_run:
                        outcome = SymbolIngestionOutcome(
                            symbol=sym,
                            ok=True,
                            snapshot_rows_fetched=0,
                            snapshot_rows_normalized=0,
                            rows_persisted=0,
                            elapsed_s=0.0,
                        )
                    else:
                        async def _fetch() -> SymbolIngestionOutcome:
                            return await _ingest_one_symbol(
                                db_url=db_url,
                                provider=provider,
                                symbol=sym,
                                ticker_id=ticker_id,
                                snapshot_time=snapshot_time,
                                http_client=(
                                    large_symbol_http_client if sym in normalized_large_symbols else default_http_client
                                ),
                                progress_cb=report_progress,
                            )

                        if sym in normalized_large_symbols:
                            async with large_symbol_lock:
                                outcome = await _fetch()
                        else:
                            outcome = await _fetch()

                    await _record_outcome(outcome, current_symbol=sym)
                    return outcome

            runner_tasks = [asyncio.create_task(run_symbol(s)) for s in symbols_to_process]
            heartbeat_task: asyncio.Task | None = None
            actual_outcomes: list[SymbolIngestionOutcome] = []
            try:
                heartbeat_task = asyncio.create_task(heartbeat())
                actual_outcomes = list(await asyncio.gather(*runner_tasks))
            except asyncio.CancelledError:
                run_cancelled = True
                for t in runner_tasks:
                    t.cancel()
                results: list[object] = []
                with contextlib.suppress(asyncio.CancelledError):
                    results = list(await asyncio.gather(*runner_tasks, return_exceptions=True))
                actual_outcomes = [r for r in results if isinstance(r, SymbolIngestionOutcome)]
            finally:
                if heartbeat_task is not None:
                    heartbeat_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await heartbeat_task
                try:
                    options_db.advisory_unlock(lock_conn, lock_key)
                except Exception:
                    logger.exception("Failed to release advisory lock", extra={"stage": "pipeline"})
            return skipped_outcomes, actual_outcomes

    default_timeout = provider.request_timeout
    large_timeout = _large_symbol_timeout(default_timeout)
    async with ThrottledAsyncClient(
        httpx.AsyncClient(timeout=default_timeout),
        GLOBAL_REQUEST_RATE_LIMITER,
    ) as default_http_client:
        if normalized_large_symbols:
            async with ThrottledAsyncClient(
                httpx.AsyncClient(timeout=large_timeout),
                GLOBAL_REQUEST_RATE_LIMITER,
            ) as large_symbol_http_client:
                skipped_outcomes, actual_outcomes = await _run_with_clients(
                    default_http_client,
                    large_symbol_http_client,
                )
        else:
            skipped_outcomes, actual_outcomes = await _run_with_clients(
                default_http_client,
                default_http_client,
            )
    outcomes = skipped_outcomes + actual_outcomes

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
            run_id=resolved_run_id,
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
            "run_id": resolved_run_id,
        },
    )

    if emit_summary:
        summary_extra = {
            "stage": "pipeline",
            "summary": True,
            "provider": provider_name,
            "snapshot_time": snapshot_time.isoformat(),
            "symbols_total": symbols_total,
            "symbols_ok": total_ok,
            "symbols_failed": total_failed,
            "rows_written": total_rows_persisted,
            "duration_sec": round(elapsed, 6),
            "run_id": resolved_run_id,
        }
        logger.info("Options ingestion summary", extra=summary_extra)

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
        run_id=resolved_run_id,
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
    large_symbols: Iterable[str] | None = None,
    run_id: str | None = None,
    heartbeat_interval: int = 25,
    emit_summary: bool = False,
    dry_run: bool = False,
) -> OptionsIngestionReport:
    if concurrency <= 0:
        raise OptionsIngestionError("concurrency must be > 0")

    db_url = db_url or options_db.default_db_url()
    if snapshot_time is None:
        if as_of_date is None:
            as_of_date = datetime.now(timezone.utc).date()
        snapshot_time = resolve_snapshot_time(as_of_date)
    elif as_of_date is None:
        as_of_date = snapshot_time.date()
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

    if large_symbols is None:
        resolved_large_symbols = frozenset(_DEFAULT_LARGE_SYMBOLS)
        large_symbol_source = "default"
    else:
        normalized = frozenset(str(s).strip().upper() for s in large_symbols if s and str(s).strip())
        resolved_large_symbols = normalized
        large_symbol_source = "cli"

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
            large_symbols=resolved_large_symbols,
            large_symbol_source=large_symbol_source,
            run_id=run_id,
            heartbeat_interval=heartbeat_interval,
            emit_summary=emit_summary,
            dry_run=dry_run,
        )
    )
