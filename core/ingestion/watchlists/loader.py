from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import db as watchlists_db


logger = logging.getLogger(__name__)


class WatchlistLoadError(RuntimeError):
    pass


class WatchlistReconcileError(RuntimeError):
    pass


_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,19}$")


def normalize_symbol(raw: str) -> str | None:
    candidate = raw.strip().upper()
    if not candidate:
        return None
    if candidate.startswith("#"):
        return None
    if not _SYMBOL_RE.match(candidate):
        return None
    return candidate


@dataclass(frozen=True)
class ParsedWatchlist:
    watchlist_id: str
    symbols: list[str]
    invalid_lines: list[str]
    duplicate_symbols: list[str]
    source_path: Path


def parse_watchlist_file(path: Path) -> ParsedWatchlist:
    if not path.exists():
        raise WatchlistLoadError(f"Watchlist file not found: {path}")
    if not path.is_file():
        raise WatchlistLoadError(f"Watchlist path is not a file: {path}")
    if path.suffix.lower() != ".txt":
        raise WatchlistLoadError(f"Watchlist file must be .txt: {path.name}")

    watchlist_id = path.stem

    text = path.read_text(encoding="utf-8")
    raw_lines = text.splitlines()

    meaningful_lines = [ln for ln in raw_lines if ln.strip() and not ln.lstrip().startswith("#")]
    if not meaningful_lines:
        raise WatchlistLoadError(f"Empty watchlist file: {path.name}")

    symbols: list[str] = []
    invalid_lines: list[str] = []
    seen: set[str] = set()
    duplicate_symbols: list[str] = []

    for ln in raw_lines:
        stripped = ln.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        sym = normalize_symbol(stripped)
        if sym is None:
            invalid_lines.append(stripped)
            continue
        if sym in seen:
            duplicate_symbols.append(sym)
            continue
        seen.add(sym)
        symbols.append(sym)

    if duplicate_symbols:
        logger.warning(
            "watchlist_id=%s: deduped %d duplicate symbols (sample=%s)",
            watchlist_id,
            len(duplicate_symbols),
            sorted(set(duplicate_symbols))[:10],
        )
    if invalid_lines:
        logger.warning(
            "watchlist_id=%s: skipped %d invalid symbols (sample=%s)",
            watchlist_id,
            len(invalid_lines),
            invalid_lines[:10],
        )

    if not symbols:
        raise WatchlistLoadError(f"Watchlist file has no valid symbols: {path.name}")

    return ParsedWatchlist(
        watchlist_id=watchlist_id,
        symbols=symbols,
        invalid_lines=invalid_lines,
        duplicate_symbols=duplicate_symbols,
        source_path=path,
    )


def default_watchlists_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "watchlists"


def list_watchlist_files(watchlists_dir: Path) -> list[Path]:
    if not watchlists_dir.exists():
        raise WatchlistLoadError(f"Watchlists directory not found: {watchlists_dir}")
    if not watchlists_dir.is_dir():
        raise WatchlistLoadError(f"Watchlists path is not a directory: {watchlists_dir}")

    files = sorted([p for p in watchlists_dir.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])
    if not files:
        raise WatchlistLoadError(f"No .txt watchlist files found in {watchlists_dir}")
    return files


def _lock_key(name: str) -> int:
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


@dataclass(frozen=True)
class WatchlistReconcileResult:
    watchlist_id: str
    source: str
    symbols_added: list[str]
    symbols_soft_deactivated: list[str]
    active_total: int


@dataclass(frozen=True)
class ReconcileAllResult:
    processed: list[WatchlistReconcileResult]


@dataclass(frozen=True)
class ReconcileDiff:
    inserted: list[str]
    reactivated: list[str]
    soft_deactivated: list[str]


def compute_reconcile_diff(
    *,
    existing: dict[str, bool],
    incoming: set[str],
) -> ReconcileDiff:
    existing_symbols = set(existing.keys())
    existing_active = {s for s, active in existing.items() if active}
    existing_inactive = existing_symbols - existing_active

    inserted = sorted(incoming - existing_symbols)
    reactivated = sorted(incoming & existing_inactive)
    soft_deactivated = sorted(existing_active - incoming)
    return ReconcileDiff(
        inserted=inserted,
        reactivated=reactivated,
        soft_deactivated=soft_deactivated,
    )


def reconcile_watchlists(
    *,
    db_url: str,
    watchlists_dir: Path | None = None,
    effective_date: date | None = None,
) -> ReconcileAllResult:
    watchlists_dir = watchlists_dir or default_watchlists_dir()
    effective_date = effective_date or date.today()

    files = list_watchlist_files(watchlists_dir)
    parsed = [parse_watchlist_file(p) for p in files]

    lock_key = _lock_key("kapman:watchlists:reconcile")
    results: list[WatchlistReconcileResult] = []

    with watchlists_db.connect(db_url) as conn:
        if not watchlists_db.try_advisory_lock(conn, lock_key):
            raise WatchlistReconcileError(
                "Watchlist reconcile is already running (advisory lock not acquired)"
            )

        try:
            for wl in parsed:
                watchlist_id = wl.watchlist_id
                source = str(wl.source_path)
                logger.info("watchlist_id=%s: processing source=%s", watchlist_id, source)

                existing = watchlists_db.fetch_memberships(conn, watchlist_id)
                incoming = set(wl.symbols)

                diff = compute_reconcile_diff(existing=existing, incoming=incoming)

                watchlists_db.upsert_active_symbols(
                    conn,
                    watchlist_id=watchlist_id,
                    symbols=sorted(incoming),
                    source=source,
                    effective_date=effective_date,
                )
                watchlists_db.deactivate_symbols(
                    conn,
                    watchlist_id=watchlist_id,
                    symbols=diff.soft_deactivated,
                    effective_date=effective_date,
                )
                active_total = watchlists_db.count_active(conn, watchlist_id)

                symbols_added = sorted(set(diff.inserted) | set(diff.reactivated))
                logger.info(
                    "watchlist_id=%s: symbols_added=%s symbols_soft_deactivated=%s active_total=%d",
                    watchlist_id,
                    symbols_added,
                    diff.soft_deactivated,
                    active_total,
                )

                results.append(
                    WatchlistReconcileResult(
                        watchlist_id=watchlist_id,
                        source=source,
                        symbols_added=symbols_added,
                        symbols_soft_deactivated=diff.soft_deactivated,
                        active_total=active_total,
                    )
                )
        finally:
            watchlists_db.advisory_unlock(conn, lock_key)

    return ReconcileAllResult(processed=results)
