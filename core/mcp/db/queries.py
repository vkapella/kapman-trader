from __future__ import annotations

from datetime import date
from typing import Any, Optional


def resolve_ticker(conn, symbol: str) -> Optional[dict[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, UPPER(symbol)
            FROM public.tickers
            WHERE UPPER(symbol) = UPPER(%s)
            """,
            (symbol,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {"ticker_id": row[0], "symbol": row[1]}


def has_active_watchlist_membership(conn, symbol: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM public.watchlists
            WHERE UPPER(symbol) = UPPER(%s) AND active = TRUE
            LIMIT 1
            """,
            (symbol,),
        )
        return cur.fetchone() is not None


def latest_snapshot_for_symbol(conn, *, ticker_id: str, as_of_date: Optional[date]) -> Optional[dict[str, Any]]:
    params: list[Any] = [ticker_id]
    where_date = ""
    if as_of_date:
        where_date = "AND ny_date <= %s"
        params.append(as_of_date)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH ranked AS (
                SELECT
                    ds.*,
                    (ds.time AT TIME ZONE 'America/New_York')::date AS ny_date,
                    ROW_NUMBER() OVER (
                        PARTITION BY (ds.time AT TIME ZONE 'America/New_York')::date
                        ORDER BY
                            CASE WHEN ds.wyckoff_regime IS NULL THEN 1 ELSE 0 END ASC,
                            ds.time DESC
                    ) AS row_rank,
                    COUNT(*) OVER (PARTITION BY (ds.time AT TIME ZONE 'America/New_York')::date) AS dup_count
                FROM public.daily_snapshots ds
                WHERE ds.ticker_id = %s
            ), dedup AS (
                SELECT *
                FROM ranked
                WHERE row_rank = 1
                {where_date}
            )
            SELECT
                time,
                ny_date,
                dup_count,
                wyckoff_phase,
                phase_confidence,
                wyckoff_regime,
                wyckoff_regime_confidence,
                wyckoff_regime_set_by_event,
                primary_event,
                events_detected,
                events_json,
                technical_indicators_json,
                dealer_metrics_json,
                volatility_metrics_json,
                price_metrics_json
            FROM dedup
            ORDER BY ny_date DESC, time DESC
            LIMIT 1
            """,
            tuple(params),
        )
        row = cur.fetchone()

    if not row:
        return None

    return {
        "time": row[0],
        "ny_date": row[1],
        "dup_count": int(row[2] or 0),
        "wyckoff_phase": row[3],
        "phase_confidence": float(row[4]) if row[4] is not None else None,
        "wyckoff_regime": row[5],
        "wyckoff_regime_confidence": float(row[6]) if row[6] is not None else None,
        "wyckoff_regime_set_by_event": row[7],
        "primary_event": row[8],
        "events_detected": row[9] or [],
        "events_json": row[10],
        "technical_indicators_json": row[11],
        "dealer_metrics_json": row[12],
        "volatility_metrics_json": row[13],
        "price_metrics_json": row[14],
    }


def fetch_ohlcv_window(conn, *, ticker_id: str, start_date: date, end_date: date) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT date, open, high, low, close, volume
            FROM public.ohlcv
            WHERE ticker_id = %s AND date >= %s AND date <= %s
            ORDER BY date ASC
            """,
            (ticker_id, start_date, end_date),
        )
        rows = cur.fetchall()
    return [
        {
            "date": row[0].isoformat(),
            "open": float(row[1]) if row[1] is not None else None,
            "high": float(row[2]) if row[2] is not None else None,
            "low": float(row[3]) if row[3] is not None else None,
            "close": float(row[4]) if row[4] is not None else None,
            "volume": int(row[5]) if row[5] is not None else None,
        }
        for row in rows
    ]


def fetch_regime_transitions(conn, *, ticker_id: str, end_date: date, limit: int = 20) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT date, prior_regime, new_regime, duration_bars
            FROM public.wyckoff_regime_transitions
            WHERE ticker_id = %s AND date <= %s
            ORDER BY date DESC, new_regime ASC
            LIMIT %s
            """,
            (ticker_id, end_date, limit),
        )
        rows = cur.fetchall()
    return [
        {"date": row[0].isoformat(), "prior_regime": row[1], "new_regime": row[2], "duration_bars": row[3]}
        for row in rows
    ]


def fetch_sequences(conn, *, ticker_id: str, end_date: date, limit: int = 20) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT sequence_id, start_date, completion_date, events_in_sequence
            FROM public.wyckoff_sequences
            WHERE ticker_id = %s AND completion_date <= %s
            ORDER BY completion_date DESC, sequence_id ASC
            LIMIT %s
            """,
            (ticker_id, end_date, limit),
        )
        rows = cur.fetchall()
    return [
        {
            "sequence_id": row[0],
            "start_date": row[1].isoformat(),
            "completion_date": row[2].isoformat(),
            "events_in_sequence": row[3],
        }
        for row in rows
    ]


def fetch_sequence_events(conn, *, ticker_id: str, end_date: date, limit: int = 50) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT sequence_id, completion_date, event_type, event_date, event_role, event_order
            FROM public.wyckoff_sequence_events
            WHERE ticker_id = %s AND completion_date <= %s
            ORDER BY completion_date DESC, event_order ASC
            LIMIT %s
            """,
            (ticker_id, end_date, limit),
        )
        rows = cur.fetchall()
    return [
        {
            "sequence_id": row[0],
            "completion_date": row[1].isoformat(),
            "event_type": row[2],
            "event_date": row[3].isoformat(),
            "event_role": row[4],
            "event_order": row[5],
        }
        for row in rows
    ]


def fetch_context_events(conn, *, ticker_id: str, end_date: date, limit: int = 50) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT event_date, event_type, prior_regime, context_label
            FROM public.wyckoff_context_events
            WHERE ticker_id = %s AND event_date <= %s
            ORDER BY event_date DESC, event_type ASC
            LIMIT %s
            """,
            (ticker_id, end_date, limit),
        )
        rows = cur.fetchall()
    return [
        {
            "event_date": row[0].isoformat(),
            "event_type": row[1],
            "prior_regime": row[2],
            "context_label": row[3],
        }
        for row in rows
    ]


def fetch_snapshot_evidence(conn, *, ticker_id: str, end_date: date, limit: int = 20) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT date, evidence_json
            FROM public.wyckoff_snapshot_evidence
            WHERE ticker_id = %s AND date <= %s
            ORDER BY date DESC
            LIMIT %s
            """,
            (ticker_id, end_date, limit),
        )
        rows = cur.fetchall()
    return [{"date": row[0].isoformat(), "evidence_json": row[1]} for row in rows]


def screen_rows(conn, *, as_of_date: Optional[date]) -> list[dict[str, Any]]:
    params: list[Any] = []
    as_of_filter = ""
    if as_of_date:
        as_of_filter = "AND d.ny_date <= %s"
        params.append(as_of_date)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH w AS (
                SELECT DISTINCT UPPER(symbol) AS symbol
                FROM public.watchlists
                WHERE active = TRUE
            ), t AS (
                SELECT id::text AS ticker_id, UPPER(symbol) AS symbol
                FROM public.tickers
            ), d AS (
                SELECT
                    ds.ticker_id::text AS ticker_id,
                    (ds.time AT TIME ZONE 'America/New_York')::date AS ny_date,
                    ds.time,
                    ds.wyckoff_regime,
                    ds.primary_event,
                    ds.dealer_metrics_json,
                    ds.volatility_metrics_json,
                    ds.price_metrics_json,
                    ROW_NUMBER() OVER (
                        PARTITION BY ds.ticker_id
                        ORDER BY (ds.time AT TIME ZONE 'America/New_York')::date DESC, ds.time DESC
                    ) AS rn
                FROM public.daily_snapshots ds
            )
            SELECT
                t.symbol,
                t.ticker_id,
                d.ny_date,
                d.wyckoff_regime,
                d.primary_event,
                d.dealer_metrics_json,
                d.volatility_metrics_json,
                d.price_metrics_json
            FROM w
            JOIN t ON t.symbol = w.symbol
            LEFT JOIN d ON d.ticker_id = t.ticker_id AND d.rn = 1 {as_of_filter}
            ORDER BY t.symbol ASC
            """,
            tuple(params),
        )
        rows = cur.fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        dealer = row[5] or {}
        vol = row[6] or {}
        price = row[7] or {}
        result.append(
            {
                "symbol": row[0],
                "ticker_id": row[1],
                "snapshot_date": row[2].isoformat() if row[2] else None,
                "regime": row[3],
                "primary_event": row[4],
                "dgpi": dealer.get("dgpi"),
                "iv_rank": vol.get("iv_rank"),
                "rvol": price.get("rvol"),
                "has_snapshot": row[2] is not None,
            }
        )
    return result


def screen_rows_for_symbols(conn, *, symbols: list[str], as_of_date: date) -> list[dict[str, Any]]:
    if not symbols:
        return []

    with conn.cursor() as cur:
        cur.execute(
            """
            WITH requested AS (
                SELECT DISTINCT UPPER(symbol) AS symbol
                FROM unnest(%s::text[]) AS supplied(symbol)
            ), t AS (
                SELECT id::text AS ticker_id, UPPER(symbol) AS symbol
                FROM public.tickers
                WHERE UPPER(symbol) = ANY(%s)
            ), d AS (
                SELECT
                    ranked.ticker_id,
                    ranked.ny_date,
                    ranked.time,
                    ranked.wyckoff_regime,
                    ranked.primary_event,
                    ranked.dealer_metrics_json,
                    ranked.volatility_metrics_json,
                    ranked.price_metrics_json
                FROM (
                    SELECT
                        ds.ticker_id::text AS ticker_id,
                        (ds.time AT TIME ZONE 'America/New_York')::date AS ny_date,
                        ds.time,
                        ds.wyckoff_regime,
                        ds.primary_event,
                        ds.dealer_metrics_json,
                        ds.volatility_metrics_json,
                        ds.price_metrics_json,
                        ROW_NUMBER() OVER (
                            PARTITION BY ds.ticker_id
                            ORDER BY (ds.time AT TIME ZONE 'America/New_York')::date DESC, ds.time DESC
                        ) AS rn
                    FROM public.daily_snapshots ds
                    WHERE (ds.time AT TIME ZONE 'America/New_York')::date <= %s
                ) ranked
                WHERE ranked.rn = 1
            )
            SELECT
                t.symbol,
                t.ticker_id,
                d.ny_date,
                d.wyckoff_regime,
                d.primary_event,
                d.dealer_metrics_json,
                d.volatility_metrics_json,
                d.price_metrics_json
            FROM requested r
            JOIN t ON t.symbol = r.symbol
            LEFT JOIN d ON d.ticker_id = t.ticker_id
            ORDER BY t.symbol ASC
            """,
            (symbols, symbols, as_of_date),
        )
        rows = cur.fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        dealer = row[5] or {}
        vol = row[6] or {}
        price = row[7] or {}
        result.append(
            {
                "symbol": row[0],
                "ticker_id": row[1],
                "snapshot_date": row[2].isoformat() if row[2] else None,
                "regime": row[3],
                "primary_event": row[4],
                "dgpi": dealer.get("dgpi"),
                "iv_rank": vol.get("iv_rank"),
                "rvol": price.get("rvol"),
                "has_snapshot": row[2] is not None,
            }
        )
    return result
