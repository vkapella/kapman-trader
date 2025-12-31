from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import psycopg2
from psycopg2.extras import execute_values


DEFAULT_HEARTBEAT_TICKERS = 50

logger = logging.getLogger("kapman.b1")

REGIME_UNKNOWN = "UNKNOWN"
REGIME_MARKUP = "MARKUP"
REGIME_MARKDOWN = "MARKDOWN"

REGIME_SETTING_EVENTS = {
    "SOS": REGIME_MARKUP,
    "SOW": REGIME_MARKDOWN,
}

REGIME_EVENT_PRIORITY = ["SOS", "SOW"]


@dataclass(frozen=True)
class RegimeState:
    regime: str
    confidence: Optional[float]
    set_by_event: Optional[str]


@dataclass
class B1BatchStats:
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
    override = os.getenv("KAPMAN_B1_MODEL_VERSION")
    if override:
        return override
    sha = _git_revision()
    return f"b1-wyckoff-regime@{sha}"


MODEL_VERSION = _resolve_model_version()


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


def _fetch_ohlcv_dates(
    conn,
    *,
    ticker_id: str,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[date]:
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
            SELECT date
            FROM ohlcv
            WHERE ticker_id = %s AND {where_clause}
            ORDER BY date ASC
            """,
            params,
        )
        rows = cur.fetchall()
    return [row[0] for row in rows]


def _fetch_events_by_date(
    conn,
    *,
    ticker_id: str,
    start_date: Optional[date],
    end_date: Optional[date],
) -> dict[date, list[str]]:
    if start_date and end_date:
        where_clause = "time::date >= %s AND time::date <= %s"
        params = (ticker_id, start_date, end_date)
    elif start_date:
        where_clause = "time::date >= %s"
        params = (ticker_id, start_date)
    elif end_date:
        where_clause = "time::date <= %s"
        params = (ticker_id, end_date)
    else:
        where_clause = "TRUE"
        params = (ticker_id,)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT time::date, events_detected, primary_event, events_json
            FROM daily_snapshots
            WHERE ticker_id = %s AND {where_clause}
            ORDER BY time ASC
            """,
            params,
        )
        rows = cur.fetchall()

    events_by_date: dict[date, list[str]] = {}
    for snapshot_date, events_detected, primary_event, events_json in rows:
        codes = _extract_event_codes(events_detected, primary_event, events_json)
        if codes:
            events_by_date[snapshot_date] = codes
    return events_by_date


def _fetch_prior_regime_state(
    conn,
    *,
    ticker_id: str,
    before_time: datetime,
) -> Optional[RegimeState]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT wyckoff_regime, wyckoff_regime_confidence, wyckoff_regime_set_by_event
            FROM daily_snapshots
            WHERE ticker_id = %s
              AND time < %s
              AND wyckoff_regime IS NOT NULL
            ORDER BY time DESC
            LIMIT 1
            """,
            (ticker_id, before_time),
        )
        row = cur.fetchone()
    if not row:
        return None
    regime, confidence, set_by_event = row
    return RegimeState(
        regime=str(regime),
        confidence=float(confidence) if confidence is not None else None,
        set_by_event=str(set_by_event) if set_by_event is not None else None,
    )


def _extract_event_codes(
    events_detected: Any,
    primary_event: Any,
    events_json: Any,
) -> list[str]:
    codes: list[str] = []
    if primary_event:
        codes.append(str(primary_event))
    if events_detected:
        if isinstance(events_detected, (list, tuple)):
            codes.extend(str(item) for item in events_detected)
        else:
            codes.append(str(events_detected))
    if events_json:
        if isinstance(events_json, dict):
            nested = events_json.get("events") or events_json.get("events_detected")
            if isinstance(nested, (list, tuple)):
                for item in nested:
                    if isinstance(item, dict):
                        code = item.get("event") or item.get("code") or item.get("type")
                        if code:
                            codes.append(str(code))
                    else:
                        codes.append(str(item))
        elif isinstance(events_json, (list, tuple)):
            codes.extend(str(item) for item in events_json)
    normalized = []
    for code in codes:
        if not code:
            continue
        normalized.append(str(code).strip().upper())
    return normalized


def _resolve_regime_for_date(
    event_codes: Sequence[str],
    prior_state: RegimeState,
) -> RegimeState:
    selected_event: Optional[str] = None
    events_set = set(event_codes)
    for candidate in REGIME_EVENT_PRIORITY:
        if candidate in events_set:
            selected_event = candidate

    if selected_event:
        return RegimeState(
            regime=REGIME_SETTING_EVENTS[selected_event],
            confidence=1.0,
            set_by_event=selected_event,
        )

    return RegimeState(
        regime=prior_state.regime,
        confidence=prior_state.confidence,
        set_by_event=prior_state.set_by_event,
    )


def _upsert_regime_snapshots(
    conn,
    *,
    rows: list[tuple],
) -> None:
    if not rows:
        return
    insert_sql = """
        INSERT INTO daily_snapshots (
            time,
            ticker_id,
            wyckoff_regime,
            wyckoff_regime_confidence,
            wyckoff_regime_set_by_event,
            model_version,
            created_at
        )
        VALUES %s
        ON CONFLICT (time, ticker_id)
        DO UPDATE SET
            wyckoff_regime = EXCLUDED.wyckoff_regime,
            wyckoff_regime_confidence = EXCLUDED.wyckoff_regime_confidence,
            wyckoff_regime_set_by_event = EXCLUDED.wyckoff_regime_set_by_event,
            model_version = EXCLUDED.model_version,
            created_at = EXCLUDED.created_at
    """
    with conn.cursor() as cur:
        execute_values(cur, insert_sql, rows, page_size=1000)
    conn.commit()


def _should_emit_heartbeat(processed: int, heartbeat_every: int) -> bool:
    return heartbeat_every > 0 and processed > 0 and processed % heartbeat_every == 0


def run_wyckoff_regime_job(
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
            log.warning("[B1] Symbols missing ticker_id: %s", ", ".join(missing))
    elif use_watchlist:
        tickers = _fetch_watchlist_tickers(conn)
    else:
        tickers = _fetch_active_tickers(conn)

    total_tickers = len(tickers)
    stats = B1BatchStats(total_tickers=total_tickers, start_time=t0)
    if total_tickers == 0:
        log.warning("[B1] No tickers resolved; nothing to compute")
        stats.end_time = time.monotonic()
        return stats.to_log_extra()

    if verbose:
        log.info(
            "[B1] RUN HEADER tickers=%s start_date=%s end_date=%s heartbeat_every=%s deterministic=true",
            total_tickers,
            start_date.isoformat() if start_date else "none",
            end_date.isoformat() if end_date else "none",
            heartbeat_every,
        )

    for ticker_id, symbol in tickers:
        try:
            dates = _fetch_ohlcv_dates(
                conn,
                ticker_id=ticker_id,
                start_date=start_date,
                end_date=end_date,
            )
            if not dates:
                stats.missing_history += 1
                log.warning(
                    "[B1] Symbol %s (%s) has insufficient OHLCV history; assigning UNKNOWN",
                    symbol,
                    ticker_id,
                )
                continue

            events_by_date = _fetch_events_by_date(
                conn,
                ticker_id=ticker_id,
                start_date=dates[0],
                end_date=dates[-1],
            )

            initial_time = _snapshot_time_utc(dates[0])
            prior_state = _fetch_prior_regime_state(conn, ticker_id=ticker_id, before_time=initial_time)
            if prior_state is None:
                prior_state = RegimeState(regime=REGIME_UNKNOWN, confidence=None, set_by_event=None)

            if verbose:
                log.info(
                    "[B1] Processing %s (%s): dates=%s start=%s end=%s prior_regime=%s",
                    symbol,
                    ticker_id,
                    len(dates),
                    dates[0].isoformat(),
                    dates[-1].isoformat(),
                    prior_state.regime,
                )

            rows: list[tuple] = []
            current_state = prior_state
            for snapshot_date in dates:
                event_codes = events_by_date.get(snapshot_date, [])
                current_state = _resolve_regime_for_date(event_codes, current_state)
                rows.append(
                    (
                        _snapshot_time_utc(snapshot_date),
                        ticker_id,
                        current_state.regime,
                        current_state.confidence,
                        current_state.set_by_event,
                        model_version,
                        datetime.now(timezone.utc),
                    )
                )

            _upsert_regime_snapshots(conn, rows=rows)
            stats.snapshots_written += len(rows)
            stats.processed += 1

            if _should_emit_heartbeat(stats.processed, heartbeat_every):
                log.info(
                    "[B1] Heartbeat processed=%s total=%s written=%s",
                    stats.processed,
                    stats.total_tickers,
                    stats.snapshots_written,
                )
        except Exception:
            stats.errors += 1
            conn.rollback()
            log.exception("[B1] Failed symbol %s (%s)", symbol, ticker_id)

    stats.end_time = time.monotonic()
    log.info("[B1] RUN SUMMARY %s", stats.to_log_extra())
    return stats.to_log_extra()
