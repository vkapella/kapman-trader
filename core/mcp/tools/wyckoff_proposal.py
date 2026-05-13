from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from core.mcp.db.connection import readonly_connection
from core.mcp.db import queries
from core.mcp.schema import CONFIRMATION_STATUS_UNCONFIRMED


def _parse_date(value: Optional[str]) -> Optional[date]:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("as_of_date must be YYYY-MM-DD") from exc


def _extract_metrics(snapshot: dict[str, Any]) -> dict[str, Any]:
    p = snapshot.get("price_metrics_json") or {}
    t = snapshot.get("technical_indicators_json") or {}
    v = snapshot.get("volatility_metrics_json") or {}
    d = snapshot.get("dealer_metrics_json") or {}
    return {
        "price_metrics": {"rvol": p.get("rvol"), "vsi": p.get("vsi"), "hv": p.get("hv")},
        "technical_metrics": {
            "rsi": t.get("rsi"),
            "macd": t.get("macd"),
            "adx": t.get("adx"),
            "obv": t.get("obv"),
            "sma": t.get("sma"),
            "ema": t.get("ema"),
        },
        "volatility_summary": {
            "average_iv": v.get("average_iv"),
            "iv_rank": v.get("iv_rank"),
            "iv_percentile": v.get("iv_percentile"),
            "iv_skew": v.get("iv_skew"),
            "term_structure": v.get("term_structure"),
            "put_call_ratio": v.get("put_call_ratio"),
        },
        "dealer_summary": {
            "dgpi": d.get("dgpi"),
            "net_gex": d.get("net_gex"),
            "total_gex": d.get("total_gex"),
            "gamma_flip": d.get("gamma_flip"),
            "call_wall": d.get("call_wall"),
            "put_wall": d.get("put_wall"),
            "dealer_position": d.get("dealer_position"),
        },
    }


def get_wyckoff_proposal_context(symbol: str, as_of_date: Optional[str] = None, lookback_days: int = 90) -> dict[str, Any]:
    if not symbol or not symbol.strip():
        raise ValueError("symbol is required")
    if lookback_days <= 0:
        raise ValueError("lookback_days must be > 0")
    parsed_date = _parse_date(as_of_date)

    with readonly_connection() as conn:
        ticker = queries.resolve_ticker(conn, symbol)
        if not ticker:
            raise ValueError(f"unknown symbol: {symbol}")

        snap = queries.latest_snapshot_for_symbol(conn, ticker_id=ticker["ticker_id"], as_of_date=parsed_date)
        membership = queries.has_active_watchlist_membership(conn, ticker["symbol"])

        if not snap:
            return {
                "symbol": ticker["symbol"],
                "ticker_id": ticker["ticker_id"],
                "effective_as_of_date": parsed_date.isoformat() if parsed_date else None,
                "latest_eligible_snapshot_date": None,
                "pipeline_reading": {
                    "regime": None,
                    "regime_confidence": None,
                    "regime_setting_event": None,
                    "primary_event": None,
                    "events_detected": [],
                    "confirmation_status": CONFIRMATION_STATUS_UNCONFIRMED,
                },
                "recent_events": [],
                "ohlcv": [],
                "price_metrics": {"rvol": None, "vsi": None, "hv": None},
                "technical_metrics": {"rsi": None, "macd": None, "adx": None, "obv": None, "sma": None, "ema": None},
                "volatility_summary": {"average_iv": None, "iv_rank": None, "iv_percentile": None, "iv_skew": None, "term_structure": None, "put_call_ratio": None},
                "dealer_summary": {"dgpi": None, "net_gex": None, "total_gex": None, "gamma_flip": None, "call_wall": None, "put_wall": None, "dealer_position": None},
                "regime_transitions": [],
                "wyckoff_context_events": [],
                "canonical_sequences": [],
                "sequence_events": [],
                "snapshot_evidence": [],
                "structural_levels": {"support_candidates": [], "resistance_candidates": []},
                "data_quality_flags": {
                    "missing_snapshot": True,
                    "stale_snapshot": False,
                    "missing_ohlcv": True,
                    "missing_metric_category": True,
                    "duplicate_same_day_snapshots": False,
                    "missing_watchlist_membership": not membership,
                },
            }

        snapshot_date = snap["ny_date"]
        start_date = snapshot_date - timedelta(days=lookback_days)
        ohlcv = queries.fetch_ohlcv_window(conn, ticker_id=ticker["ticker_id"], start_date=start_date, end_date=snapshot_date)
        transitions = queries.fetch_regime_transitions(conn, ticker_id=ticker["ticker_id"], end_date=snapshot_date)
        context_events = queries.fetch_context_events(conn, ticker_id=ticker["ticker_id"], end_date=snapshot_date)
        sequences = queries.fetch_sequences(conn, ticker_id=ticker["ticker_id"], end_date=snapshot_date)
        sequence_events = queries.fetch_sequence_events(conn, ticker_id=ticker["ticker_id"], end_date=snapshot_date)
        evidence = queries.fetch_snapshot_evidence(conn, ticker_id=ticker["ticker_id"], end_date=snapshot_date)

    metrics = _extract_metrics(snap)
    support = [bar["low"] for bar in ohlcv[-20:] if bar.get("low") is not None][-3:]
    resistance = [bar["high"] for bar in ohlcv[-20:] if bar.get("high") is not None][-3:]
    missing_metric_category = any(v is None for category in metrics.values() for v in category.values())

    return {
        "symbol": ticker["symbol"],
        "ticker_id": ticker["ticker_id"],
        "effective_as_of_date": (parsed_date or snapshot_date).isoformat(),
        "latest_eligible_snapshot_date": snapshot_date.isoformat(),
        "pipeline_reading": {
            "regime": snap.get("wyckoff_regime"),
            "regime_confidence": snap.get("wyckoff_regime_confidence"),
            "regime_setting_event": snap.get("wyckoff_regime_set_by_event"),
            "primary_event": snap.get("primary_event"),
            "events_detected": snap.get("events_detected") or [],
            "confirmation_status": CONFIRMATION_STATUS_UNCONFIRMED,
        },
        "recent_events": {
            "primary_event": snap.get("primary_event"),
            "events_detected": snap.get("events_detected") or [],
            "events_json": snap.get("events_json"),
        },
        "ohlcv": ohlcv,
        "price_metrics": metrics["price_metrics"],
        "technical_metrics": metrics["technical_metrics"],
        "volatility_summary": metrics["volatility_summary"],
        "dealer_summary": metrics["dealer_summary"],
        "regime_transitions": transitions,
        "wyckoff_context_events": context_events,
        "canonical_sequences": sequences,
        "sequence_events": sequence_events,
        "snapshot_evidence": evidence,
        "structural_levels": {
            "support_candidates": support,
            "resistance_candidates": resistance,
        },
        "data_quality_flags": {
            "missing_snapshot": False,
            "stale_snapshot": bool(parsed_date and snapshot_date < parsed_date),
            "missing_ohlcv": len(ohlcv) == 0,
            "missing_metric_category": missing_metric_category,
            "duplicate_same_day_snapshots": snap.get("dup_count", 0) > 1,
            "missing_watchlist_membership": not membership,
        },
    }
