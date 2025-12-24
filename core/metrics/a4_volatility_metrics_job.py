from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import psycopg2
from psycopg2.extras import Json

from core.metrics.volatility_metrics import (
    DEFAULT_MIN_HISTORY_POINTS,
    OptionContractVol,
    VolatilityMetricsCounts,
    VOLATILITY_METRIC_KEYS,
    compute_volatility_metrics,
)

DEFAULT_HISTORY_LOOKBACK = 252
DEFAULT_HEARTBEAT_TICKERS = 50

logger = logging.getLogger("kapman.a4")


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
    override = os.getenv("KAPMAN_A4_MODEL_VERSION")
    if override:
        return override
    sha = _git_revision()
    return f"a4-volatility-metrics@{sha}"


MODEL_VERSION = _resolve_model_version()
EMPTY_METRICS_TEMPLATE = {key: None for key in VOLATILITY_METRIC_KEYS}
EMPTY_COUNTS = VolatilityMetricsCounts.from_contracts([])


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
        average_iv = metrics.get("average_iv") or metrics.get("avg_iv")
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


def _build_volatility_payload(
    *,
    ticker_id: str,
    ticker_symbol: str,
    snapshot_date: date,
    options_snapshot_time: Optional[datetime],
    metrics: Dict[str, Optional[float]],
    counts: VolatilityMetricsCounts,
    processing_status: str,
    confidence: str,
    diagnostics: list[str],
) -> Dict[str, Any]:
    return {
        "processing_status": processing_status,
        "confidence": confidence,
        "diagnostics": diagnostics,
        "options_snapshot_time": _timestamp_to_iso(options_snapshot_time),
        "metrics": metrics,
        "metadata": {
            "ticker_id": ticker_id,
            "symbol": ticker_symbol,
            "snapshot_date": snapshot_date.isoformat(),
            "effective_options_time": _timestamp_to_iso(options_snapshot_time),
            "counts": counts.to_dict(),
            "processing_status": processing_status,
        },
    }


def _determine_processing_status(
    *,
    metrics: Dict[str, Optional[float]],
    contracts: Sequence[OptionContractVol],
    options_snapshot_time: Optional[datetime],
    history_points: int,
) -> Tuple[str, list[str]]:
    diagnostics: list[str] = []
    if options_snapshot_time is None or not contracts:
        diagnostics.append("missing_options_data")
        return "MISSING_OPTIONS", diagnostics

    if metrics.get("avg_iv") is None:
        diagnostics.append("missing_average_iv")
        if "partial_metrics" not in diagnostics:
            diagnostics.append("partial_metrics")
        return "PARTIAL", diagnostics

    if history_points < DEFAULT_MIN_HISTORY_POINTS:
        diagnostics.append("insufficient_iv_history")

    return "SUCCESS", diagnostics


def _determine_confidence(
    counts: VolatilityMetricsCounts, processing_status: str
) -> str:
    normalized = processing_status.upper()
    if normalized != "SUCCESS":
        return "low"
    if (
        counts.contracts_with_iv >= 40
        and counts.front_month_contracts >= 5
        and counts.back_month_contracts >= 5
    ):
        return "high"
    if counts.contracts_with_iv >= 20:
        return "medium"
    return "low"


def _upsert_volatility_metrics_json(
    conn, *, snapshot_time: datetime, ticker_id: str, metrics_json: Dict[str, Any], model_version: str
) -> None:
    _json_dumps_strict(metrics_json)
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO daily_snapshots (
              time,
              ticker_id,
              volatility_metrics_json,
              model_version,
              created_at
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (time, ticker_id)
            DO UPDATE SET
              volatility_metrics_json = EXCLUDED.volatility_metrics_json,
              model_version = EXCLUDED.model_version,
              created_at = EXCLUDED.created_at
            """,
            (
                snapshot_time,
                ticker_id,
                Json(metrics_json, dumps=_json_dumps_strict),
                model_version,
                now,
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
    model_version: Optional[str] = None,
) -> A4BatchStats:
    log = log or logger
    snapshot_dates = sorted(snapshot_dates)
    if not snapshot_dates:
        return A4BatchStats(dates=[], total_tickers=0)

    stats = A4BatchStats(dates=[d.isoformat() for d in snapshot_dates], total_tickers=0)
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
    flags_desc = f"debug={debug} verbose={verbose} heartbeat={heartbeat_every} fill_missing={fill_missing}"
    log.info(
        "[A4] START date=%s tickers=%s flags=%s",
        date_desc,
        stats.total_tickers,
        flags_desc,
        extra={"a4_summary": True, "a4_stats": stats.to_log_extra()},
    )

    effective_model_version = model_version or MODEL_VERSION

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
                history = _load_average_iv_history(conn, ticker_id=ticker_id, snapshot_time=snapshot_time)
                history_points = len(history)

                metrics, counts = compute_volatility_metrics(
                    contracts=contracts,
                    history=history,
                    min_history_points=DEFAULT_MIN_HISTORY_POINTS,
                )

                processing_status, diagnostics = _determine_processing_status(
                    metrics=metrics,
                    contracts=contracts,
                    options_snapshot_time=options_snapshot_time,
                    history_points=history_points,
                )

                if processing_status == "SUCCESS":
                    stats.success += 1
                elif processing_status == "MISSING_OPTIONS":
                    stats.missing_options += 1
                    log.info(
                        "[A4] missing options snapshot for %s at %s",
                        ticker_symbol,
                        snapshot_time.isoformat(),
                        extra={"a4_expected_gap": True},
                    )
                elif processing_status == "PARTIAL":
                    stats.partial_metrics += 1
                    log.info(
                        "[A4] partial volatility metrics for %s; some values null",
                        ticker_symbol,
                        extra={"a4_expected_gap": True},
                    )
                confidence = _determine_confidence(counts, processing_status)
                payload = _build_volatility_payload(
                    ticker_id=ticker_id,
                    ticker_symbol=ticker_symbol,
                    snapshot_date=snapshot_date,
                    options_snapshot_time=options_snapshot_time,
                    metrics=metrics,
                    counts=counts,
                    processing_status=processing_status,
                    confidence=confidence,
                    diagnostics=diagnostics,
                )
                if contracts and history_points < DEFAULT_MIN_HISTORY_POINTS:
                    log.info(
                        "[A4] insufficient iv history for %s (need %s points)",
                        ticker_symbol,
                        DEFAULT_MIN_HISTORY_POINTS,
                        extra={"a4_expected_gap": True},
                    )
                if verbose:
                    log.info(
                        "[A4] ticker=%s status=%s options_snapshot=%s",
                        ticker_symbol,
                        processing_status,
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
                processing_status = "ERROR"
                diagnostics = ["exception"]
                confidence = "low"
                payload = _build_volatility_payload(
                    ticker_id=ticker_id,
                    ticker_symbol=ticker_symbol,
                    snapshot_date=snapshot_date,
                    options_snapshot_time=None,
                    metrics=EMPTY_METRICS_TEMPLATE.copy(),
                    counts=EMPTY_COUNTS,
                    processing_status=processing_status,
                    confidence=confidence,
                    diagnostics=diagnostics,
                )
                log.warning(
                    "[A4] unexpected failure for %s: %s",
                    ticker_symbol,
                    exc,
                    exc_info=True,
                )
            _upsert_volatility_metrics_json(
                conn=conn,
                snapshot_time=snapshot_time,
                ticker_id=ticker_id,
                metrics_json=payload,
                model_version=effective_model_version,
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
