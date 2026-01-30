from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from psycopg2.extras import Json

from core.metrics.dealer_metrics_calc import (
    DEFAULT_GEX_SLOPE_RANGE_PCT,
    DEFAULT_MAX_MONEYNESS,
    DEFAULT_WALLS_TOP_N,
    DealerComputationResult,
    build_option_contract,
    calculate_metrics,
    sanitize_for_json,
)


DEFAULT_MODEL_VERSION = "A3-dealer-metrics-v2"
DEFAULT_MAX_DTE_DAYS = 90
DEFAULT_MIN_OPEN_INTEREST = 100
DEFAULT_MIN_VOLUME = 1
DEFAULT_HEARTBEAT_TICKERS = 50

logger = logging.getLogger("kapman.a3")


@dataclass
class FilterStats:
    total: int = 0
    expired: int = 0
    dte_exceeded: int = 0
    missing_gamma: int = 0
    low_open_interest: int = 0
    low_volume: int = 0
    other: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "total": self.total,
            "expired": self.expired,
            "dte_exceeded": self.dte_exceeded,
            "missing_gamma": self.missing_gamma,
            "low_open_interest": self.low_open_interest,
            "low_volume": self.low_volume,
            "other": self.other,
        }


def _json_dumps_strict(value: Any) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _persist_walls_with_distance(
    walls: Sequence[Dict[str, Any]],
    spot_price: Optional[float],
) -> List[Dict[str, Any]]:
    """
    Return wall data with normalized absolute distances from spot for persistence.
    """
    spot_value = _safe_float(spot_price)
    persisted: List[Dict[str, Any]] = []
    for wall in walls:
        wall_copy = dict(wall)
        distance = None
        if spot_value is not None:
            strike = _safe_float(wall_copy.get("strike"))
            if strike is not None:
                distance = round(abs(strike - spot_value), 6)
        wall_copy["distance_from_spot"] = distance
        persisted.append(wall_copy)
    return persisted


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


def _snapshot_time_utc(snapshot_date: date) -> datetime:
    ny_tz = ZoneInfo("America/New_York")
    local = datetime(
        year=snapshot_date.year,
        month=snapshot_date.month,
        day=snapshot_date.day,
        hour=23,
        minute=59,
        second=59,
        microsecond=999999,
        tzinfo=ny_tz,
    )
    return local.astimezone(timezone.utc)


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


def _fetch_watchlist_tickers_with_dealer_metrics(conn, snapshot_time: datetime) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT t.id::text
            FROM watchlists w
            JOIN tickers t ON UPPER(t.symbol) = UPPER(w.symbol)
            WHERE w.active = TRUE
              AND EXISTS (
                  SELECT 1
                  FROM daily_snapshots s
                  WHERE s.time = %s
                    AND s.ticker_id = t.id
                    AND s.dealer_metrics_json IS NOT NULL
              )
            """,
            (snapshot_time,),
        )
        rows = cur.fetchall()
    return {str(row[0]) for row in rows}


def _fetch_watchlist_tickers_missing_dealer_metrics(conn, snapshot_time: datetime) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT t.id::text
            FROM watchlists w
            JOIN tickers t ON UPPER(t.symbol) = UPPER(w.symbol)
            WHERE w.active = TRUE
              AND NOT EXISTS (
                  SELECT 1
                  FROM daily_snapshots s
                  WHERE s.time = %s
                    AND s.ticker_id = t.id
                    AND s.dealer_metrics_json IS NOT NULL
              )
            """,
            (snapshot_time,),
        )
        rows = cur.fetchall()
    return [str(row[0]) for row in rows]


def _describe_date_range(snapshot_dates: Sequence[date]) -> str:
    if not snapshot_dates:
        return "none"
    if len(snapshot_dates) == 1:
        return snapshot_dates[0].isoformat()
    return f"{snapshot_dates[0].isoformat()}..{snapshot_dates[-1].isoformat()}"


def _should_process_ticker(ticker_id: str, existing_metrics: set[str]) -> bool:
    return ticker_id not in existing_metrics

def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
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
    max_moneyness: float,
) -> Dict[str, Any]:
    persisted_call_walls = _persist_walls_with_distance(computation.call_walls, spot)
    persisted_put_walls = _persist_walls_with_distance(computation.put_walls, spot)
    primary_call_wall = dict(persisted_call_walls[0]) if persisted_call_walls else None
    primary_put_wall = dict(persisted_put_walls[0]) if persisted_put_walls else None

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
        "call_walls": persisted_call_walls,
        "put_walls": persisted_put_walls,
        "primary_call_wall": primary_call_wall,
        "primary_put_wall": primary_put_wall,
        "wall_config": {
            "max_moneyness": max_moneyness,
            "walls_top_n": params.get("walls_top_n"),
            "max_dte_days": params.get("max_dte_days"),
        },
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


def _should_emit_heartbeat(processed: int, heartbeat_every: int) -> bool:
    return heartbeat_every > 0 and processed > 0 and processed % heartbeat_every == 0


def run_dealer_metrics_job(
    conn,
    *,
    snapshot_dates: Sequence[date],
    fill_missing: bool = False,
    heartbeat_every: int = DEFAULT_HEARTBEAT_TICKERS,
    verbose: bool = False,
    debug: bool = False,
    max_dte_days: int = DEFAULT_MAX_DTE_DAYS,
    min_open_interest: int = DEFAULT_MIN_OPEN_INTEREST,
    min_volume: int = DEFAULT_MIN_VOLUME,
    walls_top_n: int = DEFAULT_WALLS_TOP_N,
    gex_slope_range_pct: float = DEFAULT_GEX_SLOPE_RANGE_PCT,
    max_moneyness: float = DEFAULT_MAX_MONEYNESS,
    spot_override: Optional[float] = None,
    model_version: str = DEFAULT_MODEL_VERSION,
    log: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    log = log or logger
    t_start = time.monotonic()
    MIN_ELIGIBLE_THRESHOLD = 5

    snapshot_dates = sorted(snapshot_dates)
    if not snapshot_dates:
        return {
            "dates": [],
            "total_tickers": 0,
            "processed": 0,
            "skipped": 0,
            "rows_written": 0,
            "success": 0,
            "failed": 0,
            "duration_sec": 0.0,
        }

    tickers = _fetch_watchlist_tickers(conn)
    total_watchlist = len(tickers)
    if total_watchlist == 0:
        log.warning("[A3] No active watchlist tickers resolved; nothing to compute")
        return {
            "dates": [d.isoformat() for d in snapshot_dates],
            "total_tickers": 0,
            "processed": 0,
            "skipped": 0,
            "rows_written": 0,
            "success": 0,
            "failed": 0,
            "duration_sec": 0.0,
        }

    symbol_map = {tid: symbol for tid, symbol in tickers}
    all_ticker_ids = [tid for tid, _ in tickers]

    ticker_plan: Dict[date, List[str]] = {}
    if fill_missing:
        for snapshot_date in snapshot_dates:
            snapshot_time = _snapshot_time_utc(snapshot_date)
            missing = _fetch_watchlist_tickers_missing_dealer_metrics(conn, snapshot_time)
            ticker_plan[snapshot_date] = sorted(missing, key=lambda tid: symbol_map.get(tid, ""))
    else:
        for snapshot_date in snapshot_dates:
            ticker_plan[snapshot_date] = all_ticker_ids.copy()

    total_planned = sum(len(ids) for ids in ticker_plan.values())
    date_desc = _describe_date_range(snapshot_dates)
    flags_desc = (
        f"debug={debug} verbose={verbose} heartbeat={heartbeat_every} fill_missing={fill_missing}"
    )
    log.info(
        "[A3] START date=%s tickers=%s flags=%s",
        date_desc,
        total_planned,
        flags_desc,
        extra={"a3_summary": True},
    )

    params = {
        "max_dte_days": max_dte_days,
        "min_open_interest": min_open_interest,
        "min_volume": min_volume,
        "walls_top_n": walls_top_n,
        "gex_slope_range_pct": gex_slope_range_pct,
        "max_moneyness": max_moneyness,
    }

    processed = 0
    skipped = 0
    rows_written = 0
    success = 0
    failed = 0
    scanned = 0
    cumulative_durations: List[float] = []

    for snapshot_date in snapshot_dates:
        snapshot_time = _snapshot_time_utc(snapshot_date)
        existing_metrics = _fetch_watchlist_tickers_with_dealer_metrics(conn, snapshot_time)
        ticker_ids = ticker_plan.get(snapshot_date, [])

        day_processed = 0
        day_skipped = 0
        day_rows_written = 0

        for ticker_id in ticker_ids:
            scanned += 1
            symbol = symbol_map.get(ticker_id, ticker_id)
            if not _should_process_ticker(ticker_id, existing_metrics):
                skipped += 1
                day_skipped += 1
                if verbose:
                    log.info(
                        "[A3] skip existing dealer metrics ticker=%s date=%s",
                        symbol,
                        snapshot_date.isoformat(),
                    )
                if _should_emit_heartbeat(scanned, heartbeat_every):
                    log.info(
                        "[A3] HEARTBEAT processed=%s/%s ticker=%s",
                        scanned,
                        total_planned,
                        symbol,
                    )
                continue

            t0 = time.monotonic()
            diagnostics: List[str] = []
            attempted_spot_sources: List[str] = []
            spot_resolution_strategy: Optional[str] = None
            effective_options_date = snapshot_date
            effective_options_time = resolve_effective_options_time(conn, ticker_id, snapshot_time)
            options_time_resolution_strategy = "max_leq_snapshot"
            if effective_options_time is None:
                diagnostics.append(
                    "no_options_before_snapshot:"
                    f"snapshot_time={snapshot_time.isoformat()},"
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
                    conn, ticker_id=ticker_id, snapshot_time=snapshot_time
                )
                if spot is not None and price_source is not None:
                    spot_source = price_source
                    spot_resolution_strategy = "price_metrics"
                else:
                    attempted_spot_sources.append("ohlcv")
                    spot = _load_spot_price(
                        conn, ticker_id=ticker_id, snapshot_date=effective_options_date
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
                )

                eligible_options = len(contracts)
                total_options = filter_stats.total
                if total_options > 0 and eligible_options == 0:
                    diagnostics.append(
                        "no_eligible_options:"
                        f"effective_options_date={effective_options_date.isoformat()},"
                        f"max_dte_days={max_dte_days},"
                        f"dte_exceeded={filter_stats.dte_exceeded},"
                        f"low_open_interest={filter_stats.low_open_interest},"
                        f"low_volume={filter_stats.low_volume}"
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
                        diagnostics.append(
                            f"spot_resolution_failed:snapshot_time={snapshot_time.isoformat()},"
                            f"effective_trading_date={effective_options_date.isoformat()},"
                            f"attempted_sources=[{attempted}]"
                        )
                else:
                    computation = calculate_metrics(
                        contracts,
                        spot=spot,
                        walls_top_n=walls_top_n,
                        gex_slope_range_pct=gex_slope_range_pct,
                        max_moneyness=max_moneyness,
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
                    snapshot_time=snapshot_time,
                    snapshot_date=snapshot_date,
                    ticker_id=ticker_id,
                    symbol=symbol,
                    spot=spot,
                    spot_source=spot_source,
                    spot_resolution_strategy=spot_resolution_strategy,
                    effective_options_time=effective_options_time,
                    options_time_resolution_strategy=options_time_resolution_strategy,
                    effective_trading_date=snapshot_date,
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
                    max_moneyness=max_moneyness,
                )

                metadata_status = _determine_metadata_status(
                    eligible_options=eligible_options,
                    diagnostics=diagnostics,
                    processing_status=status,
                    confidence=computation.confidence,
                    min_eligible_threshold=MIN_ELIGIBLE_THRESHOLD,
                )
                payload["metadata"]["status"] = metadata_status
            except Exception:
                status = "COMPUTATION_ERROR"
                failure_reason = "exception"
                diagnostics.append("exception")
                log.exception("[A3] ticker=%s failed", symbol)
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
                    snapshot_time=snapshot_time,
                    snapshot_date=snapshot_date,
                    ticker_id=ticker_id,
                    symbol=symbol,
                    spot=spot,
                    spot_source=spot_source,
                    spot_resolution_strategy=spot_resolution_strategy,
                    effective_options_time=effective_options_time,
                    options_time_resolution_strategy=options_time_resolution_strategy,
                    effective_trading_date=snapshot_date,
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
                    max_moneyness=max_moneyness,
                )
                payload["metadata"]["status"] = _determine_metadata_status(
                    eligible_options=0,
                    diagnostics=diagnostics,
                    processing_status=status,
                    confidence="invalid",
                    min_eligible_threshold=MIN_ELIGIBLE_THRESHOLD,
                )

            try:
                retries = 0
                while True:
                    try:
                        _upsert_dealer_metrics(
                            conn,
                            snapshot_time=snapshot_time,
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
            except Exception:
                log.exception("[A3] database write failed ticker=%s date=%s", symbol, snapshot_date)
                raise

            processed += 1
            day_processed += 1
            rows_written += 1
            day_rows_written += 1

            if status == "SUCCESS":
                success += 1
            else:
                failed += 1
                log.warning(
                    "[A3] %s for %s on %s (reason=%s)",
                    status,
                    symbol,
                    snapshot_date.isoformat(),
                    failure_reason,
                )

            if verbose:
                log.info(
                    "[A3] ticker=%s status=%s options_snapshot=%s",
                    symbol,
                    status,
                    effective_options_time.isoformat() if effective_options_time else None,
                )
            if debug:
                log.debug(
                    "[A3] metrics detail %s %s",
                    symbol,
                    payload,
                )

            elapsed = time.monotonic() - t0
            cumulative_durations.append(elapsed)

            if _should_emit_heartbeat(scanned, heartbeat_every):
                log.info(
                    "[A3] HEARTBEAT processed=%s/%s ticker=%s",
                    scanned,
                    total_planned,
                    symbol,
                )

        if fill_missing:
            day_skipped = len(existing_metrics)
            skipped += day_skipped
        log.info(
            "[A3] SUMMARY date=%s processed=%s skipped=%s rows_written=%s",
            snapshot_date.isoformat(),
            day_processed,
            day_skipped,
            day_rows_written,
            extra={"a3_summary": True},
        )

    duration = time.monotonic() - t_start
    avg = sum(cumulative_durations) / len(cumulative_durations) if cumulative_durations else 0.0

    log.info(
        "[A3] END date=%s processed=%s skipped=%s rows_written=%s success=%s failed=%s "
        "avg_sec_per_ticker=%.6f duration_sec=%.3f",
        date_desc,
        processed,
        skipped,
        rows_written,
        success,
        failed,
        avg,
        duration,
        extra={"a3_summary": True},
    )

    return {
        "dates": [d.isoformat() for d in snapshot_dates],
        "total_tickers": total_planned,
        "processed": processed,
        "skipped": skipped,
        "rows_written": rows_written,
        "success": success,
        "failed": failed,
        "avg_sec_per_ticker": avg,
        "duration_sec": duration,
    }
