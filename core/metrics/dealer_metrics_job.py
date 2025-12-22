from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import psycopg2
from psycopg2.extras import Json

from core.ingestion.options import db as options_db
from core.metrics.dealer_metrics_calc import (
    DEFAULT_GEX_SLOPE_RANGE_PCT,
    DEFAULT_WALLS_TOP_N,
    DealerComputationResult,
    build_option_contract,
    calculate_metrics,
    sanitize_for_json,
)


DEFAULT_MODEL_VERSION = "A3-dealer-metrics-v1"
DEFAULT_MAX_DTE_DAYS = 90
DEFAULT_MIN_OPEN_INTEREST = 100
DEFAULT_MIN_VOLUME = 1
DEFAULT_MAX_SPREAD_PCT = 10.0
DEFAULT_HEARTBEAT_SECONDS = 60
DEFAULT_HEARTBEAT_TICKERS = 25

logger = logging.getLogger("kapman.a3")


@dataclass
class FilterStats:
    total: int = 0
    expired: int = 0
    dte_exceeded: int = 0
    missing_gamma: int = 0
    low_open_interest: int = 0
    low_volume: int = 0
    wide_spread: int = 0
    other: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "total": self.total,
            "expired": self.expired,
            "dte_exceeded": self.dte_exceeded,
            "missing_gamma": self.missing_gamma,
            "low_open_interest": self.low_open_interest,
            "low_volume": self.low_volume,
            "wide_spread": self.wide_spread,
            "other": self.other,
        }


def _json_dumps_strict(value: Any) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def classify_dealer_status(
    eligible_options: int,
    gex_total: Any,
    gex_net: Any,
    position: Optional[str],
    confidence: Optional[str],
    diagnostics: Sequence[str],
) -> Tuple[str, str]:
    confidence_norm = (confidence or "").lower()
    position_norm = (position or "").lower()
    diag_set = set(diagnostics)
    gex_total_f = _safe_float(gex_total)
    gex_net_f = _safe_float(gex_net)

    full_conditions = (
        eligible_options >= 25,
        gex_total_f is not None,
        gex_net_f is not None,
        gex_total_f is not None and abs(gex_total_f) > 0,
        position_norm != "unknown",
        confidence_norm in ("high", "medium"),
    )
    if all(full_conditions):
        return "FULL", "full_thresholds_met"

    limited_conditions = (
        eligible_options >= 1,
        gex_total_f is not None,
        gex_net_f is not None,
        gex_total_f is not None and abs(gex_total_f) > 0,
        position_norm in ("long_gamma", "short_gamma", "neutral"),
        confidence_norm in ("medium", "invalid"),
    )
    if all(limited_conditions):
        return "LIMITED", "limited_thresholds_met"

    if eligible_options == 0:
        return "INVALID", "no_eligible_options"
    if gex_total_f is None:
        return "INVALID", "missing_gex_total"
    if gex_net_f is None:
        return "INVALID", "missing_gex_net"
    if "missing_spot_price" in diag_set or "spot_resolution_failed" in diag_set:
        return "INVALID", "missing_spot"
    if "all_contracts_filtered" in diag_set:
        return "INVALID", "all_contracts_filtered"
    if "no_options_available" in diag_set:
        return "INVALID", "no_options_available"

    return "INVALID", "criteria_not_met"


def _resolve_snapshot_time(conn, provided: Optional[datetime]) -> Optional[datetime]:
    if provided is not None:
        if provided.tzinfo is None:
            provided = provided.replace(tzinfo=timezone.utc)
        return provided

    with conn.cursor() as cur:
        cur.execute("SELECT MAX(time) FROM options_chains")
        row = cur.fetchone()
    if not row or row[0] is None:
        return None
    ts: datetime = row[0]
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def resolve_effective_trading_date(conn, snapshot_time: datetime) -> Optional[date]:
    snapshot_date = snapshot_time.date()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT MAX(date)
            FROM ohlcv
            WHERE date <= %s
            """,
            (snapshot_date,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return row[0]


def resolve_effective_options_time(conn, ticker_id: str, snapshot_time: datetime) -> Optional[datetime]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT MAX(time)
            FROM options_chains
            WHERE ticker_id = %s
              AND time <= %s
            """,
            (ticker_id, snapshot_time),
        )
        row = cur.fetchone()
    if not row:
        return None
    return row[0]


def _fetch_watchlist_tickers(conn) -> List[Tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT t.id::text, t.symbol
            FROM watchlists w
            JOIN tickers t ON UPPER(t.symbol) = UPPER(w.symbol)
            WHERE w.active = TRUE
            ORDER BY t.symbol
            """
        )
        rows = cur.fetchall()
    return [(str(tid), str(sym).upper()) for tid, sym in rows]


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
    except Exception:
        return None


def _bid_ask_spread_pct(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
    if bid is None or ask is None:
        return None
    try:
        if bid <= 0 or ask <= 0 or ask < bid:
            return None
        mid = 0.5 * (ask + bid)
        if mid <= 0:
            return None
        return ((ask - bid) / mid) * 100.0
    except Exception:
        return None


def _load_spot_price(conn, *, ticker_id: str, snapshot_date: date) -> Optional[float]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT close FROM ohlcv WHERE ticker_id = %s AND date = %s",
            (ticker_id, snapshot_date),
        )
        row = cur.fetchone()
    if not row:
        return None
    return _safe_float(row[0])


def _load_price_metrics_spot(
    conn,
    *,
    ticker_id: str,
    snapshot_time: datetime,
) -> tuple[Optional[float], Optional[str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT price_metrics_json
            FROM daily_snapshots
            WHERE time = %s AND ticker_id = %s
            """,
            (snapshot_time, ticker_id),
        )
        row = cur.fetchone()
    if not row or not row[0]:
        return None, None
    metrics = row[0]
    if not isinstance(metrics, dict):
        return None, None

    def _try_value(value: Any) -> Optional[float]:
        if isinstance(value, dict):
            for nested_key in ("close", "price", "spot"):
                nested = value.get(nested_key)
                cand = _safe_float(nested)
                if cand is not None:
                    return cand
            return None
        return _safe_float(value)

    for key in ("close", "spot", "price", "last"):
        candidate = metrics.get(key)
        spot_value = _try_value(candidate)
        if spot_value is not None:
            return spot_value, f"price_metrics.{key}"
    return None, None


def _load_option_contracts(
    conn,
    *,
    ticker_id: str,
    effective_options_time: Optional[datetime],
    effective_options_date: Optional[date],
    max_dte_days: int,
    min_open_interest: int,
    min_volume: int,
    max_spread_pct: float,
) -> Tuple[List[Any], FilterStats]:
    if effective_options_date is None or effective_options_time is None:
        return [], FilterStats()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT expiration_date,
                   strike_price,
                   option_type,
                   bid,
                   ask,
                   volume,
                   open_interest,
                   implied_volatility,
                   delta,
                   gamma
            FROM options_chains
            WHERE ticker_id = %s
              AND time = %s
              AND expiration_date IS NOT NULL
              AND strike_price IS NOT NULL
            """,
            (ticker_id, effective_options_time),
        )
        rows = cur.fetchall()

    stats = FilterStats()
    contracts: List[Any] = []
    max_dte = int(max_dte_days)

    for (
        expiration_date,
        strike_price,
        option_type,
        bid,
        ask,
        volume,
        open_interest,
        implied_volatility,
        delta,
        gamma,
    ) in rows:
        stats.total += 1

        if expiration_date is None or strike_price is None:
            stats.other += 1
            continue

        if isinstance(expiration_date, datetime):
            expiration_date = expiration_date.date()

        dte = (expiration_date - effective_options_date).days
        if dte < 0:
            stats.expired += 1
            continue
        if dte > max_dte:
            stats.dte_exceeded += 1
            continue

        gamma_f = _safe_float(gamma)
        if gamma_f is None:
            stats.missing_gamma += 1
            continue

        oi = _safe_float(open_interest)
        if oi is None or oi <= 0 or oi < min_open_interest:
            stats.low_open_interest += 1
            continue

        vol = _safe_float(volume)
        if vol is None or vol < min_volume:
            stats.low_volume += 1
            continue

        spread_pct = _bid_ask_spread_pct(_safe_float(bid), _safe_float(ask))
        if spread_pct is None or spread_pct > max_spread_pct:
            stats.wide_spread += 1
            continue

        try:
            option_type_norm = str(option_type).upper()
            opt_type = "call" if option_type_norm == "C" else "put"
            contract = build_option_contract(
                strike=_safe_float(strike_price) or 0.0,
                option_type=opt_type,
                gamma=gamma_f,
                delta=_safe_float(delta),
                open_interest=int(oi),
                volume=int(vol),
                iv=_safe_float(implied_volatility),
                dte=dte,
            )
            contracts.append(contract)
        except Exception:
            stats.other += 1

    return contracts, stats


def _upsert_dealer_metrics(
    conn,
    *,
    snapshot_time: datetime,
    ticker_id: str,
    payload: Dict[str, Any],
    model_version: str,
) -> None:
    sanitized = sanitize_for_json(payload)
    _json_dumps_strict(sanitized)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO daily_snapshots (
              time,
              ticker_id,
              dealer_metrics_json,
              model_version,
              created_at
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (time, ticker_id)
            DO UPDATE SET
              dealer_metrics_json = EXCLUDED.dealer_metrics_json,
              model_version = EXCLUDED.model_version,
              created_at = EXCLUDED.created_at
            """,
            (
                snapshot_time,
                ticker_id,
                Json(sanitized, dumps=_json_dumps_strict),
                model_version,
                datetime.now(timezone.utc),
            ),
        )


def _build_payload(
    *,
    computation: DealerComputationResult,
    snapshot_time: datetime,
    snapshot_date: date,
    ticker_id: str,
    symbol: str,
    spot: Optional[float],
    spot_source: Optional[str],
    spot_resolution_strategy: Optional[str],
    effective_options_time: Optional[datetime],
    options_time_resolution_strategy: Optional[str],
    effective_trading_date: Optional[date],
    attempted_spot_sources: Sequence[str],
    filter_stats: FilterStats,
    params: Dict[str, Any],
    diagnostics: List[str],
    contracts_used: int,
    processing_status: str,
    failure_reason: Optional[str],
    quality_status: str,
    status_reason: str,
    eligible_options: int,
    total_options: int,
) -> Dict[str, Any]:
    return {
        "status": quality_status,
        "failure_reason": failure_reason,
        "spot_price": spot,
        "spot_price_source": spot_source,
        "eligible_options_count": eligible_options,
        "total_options_count": total_options,
        "gex_total": computation.gex_total,
        "gex_net": computation.gex_net,
        "gamma_flip": computation.gamma_flip,
        "call_walls": computation.call_walls,
        "put_walls": computation.put_walls,
        "gex_slope": computation.gex_slope,
        "dgpi": computation.dgpi,
        "position": computation.position,
        "confidence": computation.confidence,
        "metadata": {
            "snapshot_time": snapshot_time.isoformat(),
            "snapshot_date": snapshot_date.isoformat(),
            "ticker_id": ticker_id,
            "symbol": symbol,
            "processing_status": processing_status,
            "spot": spot,
            "spot_source": spot_source,
            "spot_resolution_strategy": spot_resolution_strategy,
            "effective_options_time": effective_options_time.isoformat()
            if effective_options_time
            else None,
            "options_time_resolution_strategy": options_time_resolution_strategy,
            "effective_trading_date": effective_trading_date.isoformat()
            if effective_trading_date
            else None,
            "spot_attempted_sources": list(attempted_spot_sources),
            "eligible_options": eligible_options,
            "total_options": total_options,
            "confidence": computation.confidence,
            "status_reason": status_reason,
            "filters": params,
            "filter_stats": filter_stats.to_dict(),
            "contracts_total": filter_stats.total,
            "contracts_used": contracts_used,
            "diagnostics": diagnostics,
        },
    }


def _determine_metadata_status(
    *,
    eligible_options: int,
    diagnostics: Sequence[str],
    processing_status: str,
    confidence: Optional[str],
    min_eligible_threshold: int,
) -> str:
    diag_set = set(diagnostics)
    confidence_norm = (confidence or "").lower()
    if (
        eligible_options == 0
        or "all_contracts_filtered" in diag_set
        or processing_status != "SUCCESS"
    ):
        return "INVALID"
    if eligible_options >= min_eligible_threshold and confidence_norm == "high":
        return "FULL"
    if confidence_norm == "medium" or (
        eligible_options > 0 and eligible_options < min_eligible_threshold
    ):
        return "LIMITED"
    return "INVALID"


def run_dealer_metrics_job(
    conn,
    *,
    snapshot_time: Optional[datetime] = None,
    max_dte_days: int = DEFAULT_MAX_DTE_DAYS,
    min_open_interest: int = DEFAULT_MIN_OPEN_INTEREST,
    min_volume: int = DEFAULT_MIN_VOLUME,
    max_spread_pct: float = DEFAULT_MAX_SPREAD_PCT,
    walls_top_n: int = DEFAULT_WALLS_TOP_N,
    gex_slope_range_pct: float = DEFAULT_GEX_SLOPE_RANGE_PCT,
    spot_override: Optional[float] = None,
    heartbeat_seconds: int = DEFAULT_HEARTBEAT_SECONDS,
    heartbeat_tickers: int = DEFAULT_HEARTBEAT_TICKERS,
    model_version: str = DEFAULT_MODEL_VERSION,
    log: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    log = log or logger
    t_start = time.monotonic()
    MIN_ELIGIBLE_THRESHOLD = 5

    snapshot_ts = _resolve_snapshot_time(conn, snapshot_time)
    if snapshot_ts is None:
        log.warning("[A3] No options_chains snapshots found; nothing to compute")
        return {"tickers": 0, "processed": 0, "success": 0, "failed": 0, "duration_sec": 0.0}
    snapshot_date = snapshot_ts.date()

    tickers = _fetch_watchlist_tickers(conn)
    total_tickers = len(tickers)
    if total_tickers == 0:
        log.warning("[A3] No active watchlist tickers resolved; nothing to compute")
        return {"tickers": 0, "processed": 0, "success": 0, "failed": 0, "duration_sec": 0.0}

    log.info(
        "[A3] RUN HEADER snapshot_time=%s max_dte_days=%s min_open_interest=%s "
        "min_volume=%s max_spread_pct=%.4f walls_top_n=%s gex_slope_range_pct=%.4f "
        "spot_override=%s tickers=%s heartbeat_seconds=%s heartbeat_tickers=%s deterministic=true",
        snapshot_ts.isoformat(),
        max_dte_days,
        min_open_interest,
        min_volume,
        max_spread_pct,
        walls_top_n,
        gex_slope_range_pct,
        spot_override,
        total_tickers,
        heartbeat_seconds,
        heartbeat_tickers,
    )

    params = {
        "max_dte_days": max_dte_days,
        "min_open_interest": min_open_interest,
        "min_volume": min_volume,
        "max_spread_pct": max_spread_pct,
        "walls_top_n": walls_top_n,
        "gex_slope_range_pct": gex_slope_range_pct,
    }

    processed = 0
    success = 0
    failed = 0
    cumulative_durations: List[float] = []
    last_heartbeat = time.monotonic()

    effective_trading_date = resolve_effective_trading_date(conn, snapshot_ts)
    if effective_trading_date is None:
        log.error(
            "[A3] Unable to resolve effective_trading_date for snapshot_time=%s",
            snapshot_ts.isoformat(),
        )

    for ticker_id, symbol in tickers:
        t0 = time.monotonic()
        diagnostics: List[str] = []
        attempted_spot_sources: List[str] = []
        spot_resolution_strategy: Optional[str] = None
        effective_options_date = effective_trading_date
        effective_options_time = resolve_effective_options_time(conn, ticker_id, snapshot_ts)
        options_time_resolution_strategy = "max_leq_snapshot"
        if effective_options_time is None:
            diagnostics.append(
                "no_options_before_snapshot:"
                f"snapshot_time={snapshot_ts.isoformat()},"
                "attempted_resolution=max(options_chains.time <= snapshot_time)"
            )
        spot = spot_override
        if spot is not None:
            spot_source = "override"
            spot_resolution_strategy = "override"
            attempted_spot_sources.append("override")
        else:
            attempted_spot_sources.append("price_metrics")
            spot, price_source = _load_price_metrics_spot(
                conn, ticker_id=ticker_id, snapshot_time=snapshot_ts
            )
            if spot is not None and price_source is not None:
                spot_source = price_source
                spot_resolution_strategy = "price_metrics"
            else:
                attempted_spot_sources.append("ohlcv")
                if effective_trading_date is None:
                    diagnostics.append("no_effective_trading_date")
                else:
                    spot = _load_spot_price(
                        conn, ticker_id=ticker_id, snapshot_date=effective_trading_date
                    )
                if spot is not None:
                    spot_source = "ohlcv"
                    spot_resolution_strategy = "ohlcv_fallback"
                else:
                    spot_source = None

        try:
            contracts, filter_stats = _load_option_contracts(
                conn,
                ticker_id=ticker_id,
                effective_options_time=effective_options_time,
                effective_options_date=effective_options_date,
                max_dte_days=max_dte_days,
                min_open_interest=min_open_interest,
                min_volume=min_volume,
                max_spread_pct=max_spread_pct,
            )

            eligible_options = len(contracts)
            total_options = filter_stats.total
            if total_options > 0 and eligible_options == 0:
                diagnostics.append(
                    "no_eligible_options:"
                    f"effective_options_date={effective_options_date.isoformat() if effective_options_date else 'none'},"
                    f"max_dte_days={max_dte_days},"
                    f"dte_exceeded={filter_stats.dte_exceeded},"
                    f"low_open_interest={filter_stats.low_open_interest},"
                    f"low_volume={filter_stats.low_volume},"
                    f"wide_spread={filter_stats.wide_spread}"
                )
            if spot is None:
                diagnostics.append("missing_spot_price")
                computation = DealerComputationResult(
                    gex_total=None,
                    gex_net=None,
                    gamma_flip=None,
                    call_walls=[],
                    put_walls=[],
                    gex_slope=None,
                    dgpi=None,
                    position="unknown",
                    confidence="invalid",
                    strike_gex={},
                )
                status = "FAIL_MISSING_SPOT"
                failure_reason = "missing_spot_price"
                if total_options > 0 and eligible_options > 0:
                    status = "FAIL_SPOT_RESOLUTION"
                    failure_reason = "spot_resolution_failed"
                    attempted = ",".join(attempted_spot_sources) if attempted_spot_sources else "none"
                    diag_effective_date = (
                        effective_trading_date.isoformat() if effective_trading_date else "none"
                    )
                    diagnostics.append(
                        f"spot_resolution_failed:snapshot_time={snapshot_ts.isoformat()},"
                        f"effective_trading_date={diag_effective_date},"
                        f"attempted_sources=[{attempted}]"
                    )
            else:
                computation = calculate_metrics(
                    contracts,
                    spot=spot,
                    walls_top_n=walls_top_n,
                    gex_slope_range_pct=gex_slope_range_pct,
                )
                status = "SUCCESS"
                failure_reason = None

            if status == "SUCCESS":
                if total_options == 0:
                    status = "FAIL_NO_OPTIONS"
                    failure_reason = "no_options_available"
                    diagnostics.append("no_options_available")
                elif eligible_options == 0:
                    status = "FAIL_NO_ELIGIBLE_OPTIONS"
                    failure_reason = "all_contracts_filtered"
                    diagnostics.append("all_contracts_filtered")

            quality_status, status_reason = classify_dealer_status(
                eligible_options=eligible_options,
                gex_total=computation.gex_total,
                gex_net=computation.gex_net,
                position=computation.position,
                confidence=computation.confidence,
                diagnostics=diagnostics,
            )

            payload = _build_payload(
                computation=computation,
                snapshot_time=snapshot_ts,
                snapshot_date=snapshot_date,
                ticker_id=ticker_id,
                symbol=symbol,
                spot=spot,
                spot_source=spot_source,
                spot_resolution_strategy=spot_resolution_strategy,
                effective_options_time=effective_options_time,
                options_time_resolution_strategy=options_time_resolution_strategy,
                effective_trading_date=effective_trading_date,
                attempted_spot_sources=attempted_spot_sources,
                filter_stats=filter_stats,
                params=params,
                diagnostics=diagnostics,
                contracts_used=len(contracts),
                processing_status=status,
                failure_reason=failure_reason,
                quality_status=quality_status,
                status_reason=status_reason,
                eligible_options=eligible_options,
                total_options=total_options,
            )

            metadata_status = _determine_metadata_status(
                eligible_options=eligible_options,
                diagnostics=diagnostics,
                processing_status=status,
                confidence=computation.confidence,
                min_eligible_threshold=MIN_ELIGIBLE_THRESHOLD,
            )
            payload["metadata"]["status"] = metadata_status

            retries = 0
            while True:
                try:
                    _upsert_dealer_metrics(
                        conn,
                        snapshot_time=snapshot_ts,
                        ticker_id=ticker_id,
                        payload=payload,
                        model_version=model_version,
                    )
                    conn.commit()
                    break
                except Exception:
                    conn.rollback()
                    retries += 1
                    if retries >= 3:
                        raise
                    time.sleep(0.25 * retries)

            if status == "SUCCESS":
                success += 1
            else:
                failed += 1

            if log.isEnabledFor(logging.DEBUG):
                log_diagnostics = diagnostics if quality_status != "FULL" else []
                log.debug(
                    "[A3] ticker=%s snapshot_time=%s effective_trading_date=%s "
                    "effective_options_time=%s effective_options_date=%s "
                    "spot_source=%s spot=%s total_options=%s eligible_options=%s "
                    "confidence=%s status=%s "
                    "gex_total=%s gex_net=%s gamma_flip=%s walls_top_n=%s position=%s "
                    "confidence=%s filters=%s diagnostics=%s",
                    symbol,
                    snapshot_ts.isoformat(),
                    effective_trading_date.isoformat() if effective_trading_date else None,
                    effective_options_time.isoformat() if effective_options_time else None,
                    effective_options_date.isoformat() if effective_options_date else None,
                    spot_source,
                    spot,
                    total_options,
                    eligible_options,
                    computation.confidence,
                    quality_status,
                    computation.gex_total,
                    computation.gex_net,
                    computation.gamma_flip,
                    walls_top_n,
                    computation.position,
                    computation.confidence,
                    filter_stats.to_dict(),
                    log_diagnostics,
                )
        except Exception:
            status = "COMPUTATION_ERROR"
            failure_reason = "exception"
            failed += 1
            diagnostics.append("exception")
            log.exception("[A3] ticker=%s failed", symbol)
            try:
                payload = _build_payload(
                    computation=DealerComputationResult(
                        gex_total=None,
                        gex_net=None,
                        gamma_flip=None,
                        call_walls=[],
                        put_walls=[],
                        gex_slope=None,
                        dgpi=None,
                        position="unknown",
                        confidence="invalid",
                        strike_gex={},
                    ),
                    snapshot_time=snapshot_ts,
                    snapshot_date=snapshot_date,
                    ticker_id=ticker_id,
                    symbol=symbol,
                    spot=spot,
                    spot_source=spot_source,
                    spot_resolution_strategy=spot_resolution_strategy,
                    effective_options_time=effective_options_time,
                    options_time_resolution_strategy=options_time_resolution_strategy,
                    effective_trading_date=effective_trading_date,
                    attempted_spot_sources=attempted_spot_sources,
                    filter_stats=FilterStats(total=1, other=1),
                    params=params,
                    diagnostics=diagnostics,
                    contracts_used=0,
                    processing_status=status,
                    failure_reason=failure_reason,
                    quality_status="INVALID",
                    status_reason="exception",
                    eligible_options=0,
                    total_options=0,
                )
                metadata_status = _determine_metadata_status(
                    eligible_options=0,
                    diagnostics=diagnostics,
                    processing_status=status,
                    confidence="invalid",
                    min_eligible_threshold=MIN_ELIGIBLE_THRESHOLD,
                )
                payload["metadata"]["status"] = metadata_status
                _upsert_dealer_metrics(
                    conn,
                    snapshot_time=snapshot_ts,
                    ticker_id=ticker_id,
                    payload=payload,
                    model_version=model_version,
                )
                conn.commit()
            except Exception:
                conn.rollback()
        finally:
            processed += 1
            elapsed = time.monotonic() - t0
            cumulative_durations.append(elapsed)

            now = time.monotonic()
            count_trigger = heartbeat_tickers > 0 and processed % heartbeat_tickers == 0
            time_trigger = heartbeat_seconds > 0 and (now - last_heartbeat) >= heartbeat_seconds
            if count_trigger or time_trigger:
                percent = (processed / total_tickers) * 100.0
                log.info(
                    "[A3] HEARTBEAT processed=%s/%s (%.2f%%)",
                    processed,
                    total_tickers,
                    percent,
                )
                last_heartbeat = now

    duration = time.monotonic() - t_start
    avg = sum(cumulative_durations) / len(cumulative_durations) if cumulative_durations else 0.0

    log.info(
        "[A3] SUMMARY snapshot_time=%s total_tickers=%s success=%s soft_fail=%s "
        "avg_sec_per_ticker=%.6f duration_sec=%.3f",
        snapshot_ts.isoformat(),
        total_tickers,
        success,
        failed,
        avg,
        duration,
    )

    return {
        "tickers": total_tickers,
        "processed": processed,
        "success": success,
        "failed": failed,
        "avg_sec_per_ticker": avg,
        "duration_sec": duration,
    }


def _parse_snapshot_time(value: str) -> datetime:
    try:
        ts = datetime.fromisoformat(value)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except Exception as exc:
        raise argparse.ArgumentTypeError(f"Invalid snapshot time: {value}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KapMan A3: Compute dealer metrics into daily_snapshots"
    )
    parser.add_argument("--db-url", type=str, default=None, help="Override DATABASE_URL")
    parser.add_argument("--snapshot-time", type=_parse_snapshot_time, default=None, help="Snapshot time (ISO 8601)")
    parser.add_argument("--max-dte-days", type=int, default=DEFAULT_MAX_DTE_DAYS, help="Max DTE days (default 90)")
    parser.add_argument(
        "--min-open-interest",
        type=int,
        default=DEFAULT_MIN_OPEN_INTEREST,
        help="Min open interest per contract (default 100)",
    )
    parser.add_argument(
        "--min-volume",
        type=int,
        default=DEFAULT_MIN_VOLUME,
        help="Min volume per contract (default 1)",
    )
    parser.add_argument(
        "--max-spread-pct",
        type=float,
        default=DEFAULT_MAX_SPREAD_PCT,
        help="Max bid-ask spread percentage (default 10.0)",
    )
    parser.add_argument(
        "--walls-top-n",
        type=int,
        default=DEFAULT_WALLS_TOP_N,
        help="Number of call/put walls to retain (default 3)",
    )
    parser.add_argument(
        "--gex-slope-range-pct",
        type=float,
        default=DEFAULT_GEX_SLOPE_RANGE_PCT,
        help="Price window percentage for GEX slope (default 0.02)",
    )
    parser.add_argument(
        "--spot-override",
        type=float,
        default=None,
        help="Override spot price for all tickers (diagnostics only)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING"],
        default="INFO",
        help="Log level (default INFO)",
    )
    return parser


def _configure_logging(level: str) -> logging.Logger:
    log_level = getattr(logging, level.upper(), logging.INFO)
    log = logging.getLogger("kapman.a3")
    log.handlers.clear()
    log.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    handler.setLevel(log_level)
    log.addHandler(handler)
    log.setLevel(log_level)
    return log


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log = _configure_logging(args.log_level)
    db_url = args.db_url or options_db.default_db_url()

    with psycopg2.connect(db_url) as conn:
        run_dealer_metrics_job(
            conn,
            snapshot_time=args.snapshot_time,
            max_dte_days=args.max_dte_days,
            min_open_interest=args.min_open_interest,
            min_volume=args.min_volume,
            max_spread_pct=args.max_spread_pct,
            walls_top_n=args.walls_top_n,
            gex_slope_range_pct=args.gex_slope_range_pct,
            spot_override=args.spot_override,
            log=log,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
