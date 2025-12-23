from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import psycopg2
from psycopg2.extras import Json

from core.metrics.volatility_metrics import (
    OptionContractVol,
    calculate_average_iv,
    calculate_iv_rank,
    calculate_iv_skew,
    calculate_iv_term_structure,
    calculate_oi_ratio,
    calculate_put_call_ratio,
)

DEFAULT_HISTORY_LOOKBACK = 252
DEFAULT_MIN_IV_HISTORY = 20
DEFAULT_HEARTBEAT_TICKERS = 50

logger = logging.getLogger("kapman.a4")


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


def _describe_date_range(snapshot_dates: Sequence[date]) -> str:
    if not snapshot_dates:
        return "none"
    if len(snapshot_dates) == 1:
        return snapshot_dates[0].isoformat()
    return f"{snapshot_dates[0].isoformat()}..{snapshot_dates[-1].isoformat()}"


def _resolve_options_snapshot_time(conn, ticker_id: str, snapshot_time: datetime) -> Optional[datetime]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT MAX(time)
            FROM options_chains
            WHERE ticker_id = %s AND time <= %s
            """,
            (ticker_id, snapshot_time),
        )
        row = cur.fetchone()
    if not row or row[0] is None:
        return None
    ts: datetime = row[0]
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _fetch_watchlist_tickers(conn) -> list[Tuple[str, str]]:
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


def _log_missing_watchlist_symbols(conn, log: logging.Logger) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT 
                w.symbol,
                UPPER(w.symbol) AS symbol_upper
            FROM watchlists w
            WHERE w.active = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM tickers t WHERE UPPER(t.symbol) = UPPER(w.symbol)
              )
            ORDER BY symbol_upper;
            """
        )
        missing = [str(sym).upper() for (sym, _) in cur.fetchall()]
    if missing:
        log.warning("[A4] watchlist symbols missing ticker_id: %s", ", ".join(missing))


def _fetch_watchlist_tickers_missing_snapshot(conn, snapshot_time: datetime) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT t.id::text
            FROM watchlists w
            JOIN tickers t ON UPPER(t.symbol) = UPPER(w.symbol)
            WHERE w.active = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM daily_snapshots s
                  WHERE s.time = %s AND s.ticker_id = t.id
              )
            ORDER BY UPPER(t.symbol), t.id::text
            """,
            (snapshot_time,),
        )
        rows = cur.fetchall()
    return [row[0] for row in rows]


def _load_options_contracts(
    conn, *, ticker_id: str, options_snapshot_time: datetime, snapshot_time: datetime
) -> list[OptionContractVol]:
    if options_snapshot_time is None:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT expiration_date, strike_price, option_type, delta, implied_volatility,
                   volume, open_interest
            FROM options_chains
            WHERE ticker_id = %s AND time = %s
            ORDER BY expiration_date ASC, strike_price ASC, option_type ASC
            """,
            (ticker_id, options_snapshot_time),
        )
        rows = cur.fetchall()

    contracts: list[OptionContractVol] = []
    snapshot_date = snapshot_time.date()

    def _as_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    for exp_date, strike_price, option_type, delta, iv, volume, open_interest in rows:
        if option_type is None or exp_date is None:
            continue
        dte = None
        if isinstance(exp_date, datetime):
            exp_date_val = exp_date.date()
        else:
            exp_date_val = exp_date
        if exp_date_val is not None:
            dte = max(0, (exp_date_val - snapshot_date).days)
        strike = _as_float(strike_price) or 0.0
        contract_type = "call" if str(option_type).upper().startswith("C") else "put"
        contracts.append(
            OptionContractVol(
                strike=strike,
                contract_type=contract_type,
                delta=_as_float(delta),
                iv=_as_float(iv),
                dte=dte,
                volume=int(volume) if volume is not None else 0,
                open_interest=int(open_interest) if open_interest is not None else 0,
            )
        )
    return contracts


def _load_average_iv_history(
    conn, *, ticker_id: str, snapshot_time: datetime, lookback: int = DEFAULT_HISTORY_LOOKBACK
) -> list[float]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT volatility_metrics_json
            FROM daily_snapshots
            WHERE ticker_id = %s AND time < %s
            ORDER BY time DESC
            LIMIT %s
            """,
            (ticker_id, snapshot_time, lookback),
        )
        rows = cur.fetchall()

    history: list[float] = []
    for (payload,) in rows:
        if not isinstance(payload, dict):
            continue
        metrics = payload.get("metrics")
        if not isinstance(metrics, dict):
            continue
        average_iv = metrics.get("average_iv")
        if average_iv is None:
            continue
        try:
            history.append(float(average_iv))
        except (TypeError, ValueError):
            continue
    return history


def _timestamp_to_iso(ts: Optional[datetime]) -> Optional[str]:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.isoformat()


def _build_metrics_payload(
    *,
    average_iv: Optional[float],
    iv_rank: Optional[float],
    put_call_ratio: Optional[float],
    oi_ratio: Optional[float],
    iv_skew: Optional[float],
    iv_term: Optional[float],
    options_snapshot_time: Optional[datetime],
) -> Tuple[Dict[str, Any], str]:
    metrics = {
        "average_iv": average_iv,
        "iv_rank": iv_rank,
        "put_call_ratio_oi": put_call_ratio,
        "oi_ratio": oi_ratio,
        "iv_skew": iv_skew,
        "iv_term_structure": iv_term,
    }
    if options_snapshot_time is None:
        status = "missing_options_data"
    elif any(value is None for value in metrics.values()):
        status = "partial_metrics"
    else:
        status = "ok"
    payload = {
        "status": status,
        "options_snapshot_time": _timestamp_to_iso(options_snapshot_time),
        "metrics": metrics,
    }
    return payload, status


def _upsert_volatility_metrics_json(
    conn, *, snapshot_time: datetime, ticker_id: str, metrics_json: Dict[str, Any]
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO daily_snapshots (time, ticker_id, volatility_metrics_json)
            VALUES (%s, %s, %s)
            ON CONFLICT (time, ticker_id)
            DO UPDATE SET volatility_metrics_json = EXCLUDED.volatility_metrics_json
            """,
            (
                snapshot_time,
                ticker_id,
                Json(metrics_json, dumps=_json_dumps_strict),
            ),
        )
    conn.commit()


def _should_emit_heartbeat(processed: int, heartbeat_every: int) -> bool:
    return heartbeat_every > 0 and processed > 0 and processed % heartbeat_every == 0


@dataclass
class A4BatchStats:
    dates: list[str]
    total_tickers: int
    processed: int = 0
    success: int = 0
    missing_options: int = 0
    partial_metrics: int = 0
    errors: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    def to_log_extra(self) -> Dict[str, Any]:
        return {
            "total_tickers": self.total_tickers,
            "processed": self.processed,
            "success": self.success,
            "missing_options": self.missing_options,
            "partial_metrics": self.partial_metrics,
            "errors": self.errors,
            "duration_sec": self.duration(),
        }

    def duration(self) -> float:
        return self.end_time - self.start_time


def run_volatility_metrics_job(
    conn,
    *,
    snapshot_dates: Sequence[date],
    fill_missing: bool = False,
    heartbeat_every: int = DEFAULT_HEARTBEAT_TICKERS,
    verbose: bool = False,
    debug: bool = False,
    log: Optional[logging.Logger] = None,
) -> A4BatchStats:
    log = log or logger
    snapshot_dates = sorted(snapshot_dates)
    if not snapshot_dates:
        return A4BatchStats(dates=[], total_tickers=0)

    stats = A4BatchStats(
        dates=[d.isoformat() for d in snapshot_dates],
        total_tickers=0,
    )
    stats.start_time = time.monotonic()
    _log_missing_watchlist_symbols(conn, log)
    watchlist = _fetch_watchlist_tickers(conn)
    symbol_map = {tid: symbol for tid, symbol in watchlist}

    ticker_plan: Dict[date, list[str]] = {}
    all_ticker_ids = [tid for tid, _ in watchlist]
    if fill_missing:
        for snapshot_date in snapshot_dates:
            snapshot_time = _snapshot_time_utc(snapshot_date)
            missing = _fetch_watchlist_tickers_missing_snapshot(conn, snapshot_time)
            sorted_missing = sorted(missing, key=lambda tid: symbol_map.get(tid, ""))
            ticker_plan[snapshot_date] = sorted_missing
    else:
        for snapshot_date in snapshot_dates:
            ticker_plan[snapshot_date] = all_ticker_ids.copy()

    stats.total_tickers = sum(len(ids) for ids in ticker_plan.values())
    date_desc = _describe_date_range(snapshot_dates)
    flags_desc = (
        f"debug={debug} verbose={verbose} heartbeat={heartbeat_every} fill_missing={fill_missing}"
    )
    log.info(
        "[A4] START date=%s tickers=%s flags=%s",
        date_desc,
        stats.total_tickers,
        flags_desc,
        extra={"a4_summary": True, "a4_stats": stats.to_log_extra()},
    )

    for snapshot_date in snapshot_dates:
        snapshot_time = _snapshot_time_utc(snapshot_date)
        ticker_ids = ticker_plan.get(snapshot_date, [])
        for ticker_id in ticker_ids:
            stats.processed += 1
            ticker_symbol = symbol_map.get(ticker_id, ticker_id)
            try:
                options_snapshot_time = _resolve_options_snapshot_time(conn, ticker_id, snapshot_time)
                contracts = _load_options_contracts(
                    conn,
                    ticker_id=ticker_id,
                    options_snapshot_time=options_snapshot_time,
                    snapshot_time=snapshot_time,
                )
                average_iv = calculate_average_iv(contracts)
                iv_rank = calculate_iv_rank(
                    average_iv,
                    _load_average_iv_history(conn, ticker_id=ticker_id, snapshot_time=snapshot_time),
                    min_history_points=DEFAULT_MIN_IV_HISTORY,
                )
                put_call_ratio = calculate_put_call_ratio(contracts)
                oi_ratio = calculate_oi_ratio(contracts)
                iv_skew = calculate_iv_skew(contracts)
                iv_term = calculate_iv_term_structure(contracts)
                payload, status = _build_metrics_payload(
                    average_iv=average_iv,
                    iv_rank=iv_rank,
                    put_call_ratio=put_call_ratio,
                    oi_ratio=oi_ratio,
                    iv_skew=iv_skew,
                    iv_term=iv_term,
                    options_snapshot_time=options_snapshot_time,
                )
                if status == "ok":
                    stats.success += 1
                elif status == "missing_options_data":
                    stats.missing_options += 1
                    log.info(
                        "[A4] missing options snapshot for %s at %s",
                        ticker_symbol,
                        snapshot_time.isoformat(),
                        extra={"a4_expected_gap": True},
                    )
                elif status == "partial_metrics":
                    stats.partial_metrics += 1
                    log.info(
                        "[A4] partial volatility metrics for %s; some values null",
                        ticker_symbol,
                        extra={"a4_expected_gap": True},
                    )
                if average_iv is not None and iv_rank is None:
                    log.info(
                        "[A4] insufficient iv history for %s (need %s points)",
                        ticker_symbol,
                        DEFAULT_MIN_IV_HISTORY,
                        extra={"a4_expected_gap": True},
                    )
                if verbose:
                    log.info(
                        "[A4] ticker=%s status=%s options_snapshot=%s",
                        ticker_symbol,
                        status,
                        _timestamp_to_iso(options_snapshot_time),
                    )
                if debug and options_snapshot_time is not None and contracts:
                    log.debug(
                        "[A4] metrics detail %s %s",
                        ticker_symbol,
                        payload["metrics"],
                        extra={"a4_metric_detail": True},
                    )
            except Exception as exc:
                stats.errors += 1
                payload = {
                    "status": "error",
                    "options_snapshot_time": _timestamp_to_iso(None),
                    "metrics": {
                        "average_iv": None,
                        "iv_rank": None,
                        "put_call_ratio_oi": None,
                        "oi_ratio": None,
                        "iv_skew": None,
                        "iv_term_structure": None,
                    },
                }
                log.warning(
                    "[A4] unexpected failure for %s: %s",
                    ticker_symbol,
                    exc,
                    exc_info=True,
                )
            _upsert_volatility_metrics_json(
                conn,
                snapshot_time=snapshot_time,
                ticker_id=ticker_id,
                metrics_json=payload,
            )
            if _should_emit_heartbeat(stats.processed, heartbeat_every):
                log.info(
                    "[A4] HEARTBEAT processed=%s/%s ticker=%s",
                    stats.processed,
                    stats.total_tickers,
                    ticker_symbol,
                    extra={"a4_heartbeat": True},
                )

    stats.end_time = time.monotonic()
    log.info(
        "[A4] END date=%s processed=%s success=%s missing=%s partial=%s errors=%s duration_sec=%.3f",
        date_desc,
        stats.processed,
        stats.success,
        stats.missing_options,
        stats.partial_metrics,
        stats.errors,
        stats.duration(),
        extra={"a4_summary": True, "a4_stats": stats.to_log_extra()},
    )
    return stats
