from __future__ import annotations

import importlib.util
import json
import logging
import math
import os
import subprocess
import time
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import psycopg2
from psycopg2.extras import Json, execute_values


DEFAULT_HEARTBEAT_TICKERS = 50

logger = logging.getLogger("kapman.b2")


@dataclass
class B2BatchStats:
    total_tickers: int
    processed: int = 0
    snapshots_written: int = 0
    missing_history: int = 0
    errors: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    def duration(self) -> float:
        return self.end_time - self.start_time

    def to_log_extra(self) -> Dict[str, Any]:
        return {
            "total_tickers": self.total_tickers,
            "processed": self.processed,
            "snapshots_written": self.snapshots_written,
            "missing_history": self.missing_history,
            "errors": self.errors,
            "duration_sec": self.duration(),
        }


def _git_revision() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[2]
        sha_bytes = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL
        )
        return sha_bytes.decode().strip()
    except Exception:
        return "unknown"


def _resolve_model_version() -> str:
    override = os.getenv("KAPMAN_B2_MODEL_VERSION")
    if override:
        return override
    sha = _git_revision()
    return f"b2-wyckoff-structural@{sha}"


MODEL_VERSION = _resolve_model_version()


def _json_dumps_strict(value: Any) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _snapshot_time_utc(snapshot_date: date) -> datetime:
    return datetime(
        year=snapshot_date.year,
        month=snapshot_date.month,
        day=snapshot_date.day,
        hour=23,
        minute=59,
        second=59,
        microsecond=999999,
        tzinfo=timezone.utc,
    )


@lru_cache(maxsize=1)
def _structural_surface():
    repo_root = Path(__file__).resolve().parents[2]
    surface_path = repo_root / "docs" / "research_inputs" / "structural.py"
    spec = importlib.util.spec_from_file_location("structural", surface_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load structural surface from {surface_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fetch_active_tickers(conn) -> list[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, UPPER(symbol)
            FROM tickers
            WHERE is_active = TRUE
            ORDER BY UPPER(symbol), id::text
            """
        )
        rows = cur.fetchall()
    return [(str(tid), str(symbol)) for tid, symbol in rows]


def _fetch_watchlist_tickers(conn) -> list[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT t.id::text, UPPER(t.symbol)
            FROM watchlists w
            JOIN tickers t ON UPPER(t.symbol) = UPPER(w.symbol)
            WHERE w.active = TRUE
            ORDER BY UPPER(t.symbol), t.id::text
            """
        )
        rows = cur.fetchall()
    return [(str(tid), str(symbol)) for tid, symbol in rows]


def _fetch_tickers_for_symbols(conn, symbols: Iterable[str]) -> tuple[list[tuple[str, str]], list[str]]:
    normalized = sorted({str(sym).upper() for sym in symbols if str(sym).strip()})
    if not normalized:
        return [], []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT UPPER(symbol), id::text FROM tickers WHERE UPPER(symbol) = ANY(%s) ORDER BY UPPER(symbol)",
            (normalized,),
        )
        rows = cur.fetchall()
    found = {str(symbol): str(ticker_id) for symbol, ticker_id in rows}
    missing = [sym for sym in normalized if sym not in found]
    return [(ticker_id, symbol) for symbol, ticker_id in rows], missing


def _fetch_ohlcv_history(
    conn,
    *,
    ticker_id: str,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[tuple]:
    if start_date and end_date:
        where_clause = "date >= %s AND date <= %s"
        params = (ticker_id, start_date, end_date)
    elif start_date:
        where_clause = "date >= %s"
        params = (ticker_id, start_date)
    elif end_date:
        where_clause = "date <= %s"
        params = (ticker_id, end_date)
    else:
        where_clause = "TRUE"
        params = (ticker_id,)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT date, open, high, low, close, volume
            FROM ohlcv
            WHERE ticker_id = %s AND {where_clause}
            ORDER BY date ASC
            """,
            params,
        )
        rows = cur.fetchall()
    return rows


def _normalize_score(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        val = float(value)
    except Exception:
        return None
    if math.isnan(val) or math.isinf(val):
        return None
    return val


def _group_events_by_date(events: Sequence[Dict[str, Any]]) -> dict[date, list[Dict[str, Any]]]:
    by_date: dict[date, list[Dict[str, Any]]] = {}
    for ev in events:
        date_str = ev.get("date")
        label = ev.get("label")
        if not date_str or not label:
            continue
        try:
            ev_date = date.fromisoformat(str(date_str))
        except ValueError:
            continue
        entry = {
            "event": str(label).upper(),
            "score": _normalize_score(ev.get("score")),
        }
        by_date.setdefault(ev_date, []).append(entry)
    return by_date


def _select_primary_event(events: Sequence[Dict[str, Any]]) -> Optional[str]:
    if not events:
        return None
    best_idx = 0
    best_score = events[0].get("score")
    best_score_val = best_score if best_score is not None else float("-inf")
    for idx, ev in enumerate(events[1:], start=1):
        score = ev.get("score")
        score_val = score if score is not None else float("-inf")
        if score_val > best_score_val:
            best_idx = idx
            best_score_val = score_val
    return str(events[best_idx].get("event") or "").upper() or None


def _upsert_event_snapshots(conn, *, rows: list[tuple]) -> None:
    if not rows:
        return
    insert_sql = """
        INSERT INTO daily_snapshots (
            time,
            ticker_id,
            events_detected,
            primary_event,
            events_json,
            model_version,
            created_at
        )
        VALUES %s
        ON CONFLICT (time, ticker_id)
        DO UPDATE SET
            events_detected = EXCLUDED.events_detected,
            primary_event = EXCLUDED.primary_event,
            events_json = EXCLUDED.events_json,
            model_version = EXCLUDED.model_version,
            created_at = EXCLUDED.created_at
    """
    with conn.cursor() as cur:
        execute_values(cur, insert_sql, rows, page_size=1000)
    conn.commit()


def _should_emit_heartbeat(processed: int, heartbeat_every: int) -> bool:
    return heartbeat_every > 0 and processed > 0 and processed % heartbeat_every == 0


def run_wyckoff_structural_events_job(
    conn,
    *,
    symbols: Optional[Iterable[str]] = None,
    use_watchlist: bool = False,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    heartbeat_every: int = 0,
    verbose: bool = False,
    model_version: str = MODEL_VERSION,
    log: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    log = log or logger
    t0 = time.monotonic()

    if symbols is not None and use_watchlist:
        raise ValueError("symbols and use_watchlist are mutually exclusive")

    if symbols is not None:
        tickers, missing = _fetch_tickers_for_symbols(conn, symbols)
        if missing:
            log.warning("[B2] Symbols missing ticker_id: %s", ", ".join(missing))
    elif use_watchlist:
        tickers = _fetch_watchlist_tickers(conn)
    else:
        tickers = _fetch_active_tickers(conn)

    total_tickers = len(tickers)
    stats = B2BatchStats(total_tickers=total_tickers, start_time=t0)
    if total_tickers == 0:
        log.warning("[B2] No tickers resolved; nothing to compute")
        stats.end_time = time.monotonic()
        return stats.to_log_extra()

    if verbose:
        log.info(
            "[B2] RUN HEADER tickers=%s start_date=%s end_date=%s heartbeat_every=%s deterministic=true",
            total_tickers,
            start_date.isoformat() if start_date else "none",
            end_date.isoformat() if end_date else "none",
            heartbeat_every,
        )

    structural = _structural_surface()

    for ticker_id, symbol in tickers:
        try:
            rows = _fetch_ohlcv_history(
                conn,
                ticker_id=ticker_id,
                start_date=start_date,
                end_date=end_date,
            )
            if not rows:
                stats.missing_history += 1
                log.warning(
                    "[B2] Symbol %s (%s) has insufficient OHLCV history; skipping",
                    symbol,
                    ticker_id,
                )
                continue

            df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
            numeric_cols = ["open", "high", "low", "close", "volume"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = df[col].astype(float)
            result = structural.detect_structural_wyckoff(df, cfg=None)
            events = result.get("events", [])
            events_by_date = _group_events_by_date(events)

            if verbose:
                log.info(
                    "[B2] Processing %s (%s): dates=%s events=%s",
                    symbol,
                    ticker_id,
                    len(rows),
                    sum(len(v) for v in events_by_date.values()),
                )

            upsert_rows: list[tuple] = []
            now = datetime.now(timezone.utc)
            for event_date in sorted(events_by_date.keys()):
                evs = events_by_date[event_date]
                events_detected = [ev["event"] for ev in evs]
                primary_event = _select_primary_event(evs)
                events_json = {"events": evs}
                upsert_rows.append(
                    (
                        _snapshot_time_utc(event_date),
                        ticker_id,
                        events_detected,
                        primary_event,
                        Json(events_json, dumps=_json_dumps_strict),
                        model_version,
                        now,
                    )
                )

            _upsert_event_snapshots(conn, rows=upsert_rows)
            stats.snapshots_written += len(upsert_rows)
            stats.processed += 1

            if _should_emit_heartbeat(stats.processed, heartbeat_every):
                log.info(
                    "[B2] Heartbeat processed=%s total=%s written=%s",
                    stats.processed,
                    stats.total_tickers,
                    stats.snapshots_written,
                )
        except Exception:
            stats.errors += 1
            conn.rollback()
            log.exception("[B2] Failed symbol %s (%s)", symbol, ticker_id)

    stats.end_time = time.monotonic()
    log.info("[B2] RUN SUMMARY %s", stats.to_log_extra())
    return stats.to_log_extra()
