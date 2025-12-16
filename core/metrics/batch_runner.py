import logging
import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from core.metrics.computations import (
    MetricResult,
    compute_all_metrics,
    MACD_SLOW,
    SMA50_WINDOW,
    RVOL_WINDOW,
)


logger = logging.getLogger(__name__)


@dataclass
class BatchConfig:
    target_date: Optional[date] = None
    symbols: Optional[List[str]] = None
    lookback_days: int = 60


class MetricsBatchRunner:
    """
    Batch job for computing technical indicators and persisting into daily_snapshots.
    """

    def __init__(self, engine: Optional[Engine] = None):
        db_url = os.getenv("DATABASE_URL")
        self.engine = engine or create_engine(db_url, future=True)

    def resolve_target_date(self, target_date: Optional[date]) -> Optional[date]:
        if target_date:
            return target_date
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT MAX(DATE(time)) FROM ohlcv_daily")).scalar()
            if row is None:
                return None
            if isinstance(row, datetime):
                return row.date()
            if isinstance(row, str):
                return datetime.fromisoformat(row).date()
            return row

    def _fetch_watchlist_symbols(self) -> List[str]:
        watchlist_queries = [
            "SELECT symbol FROM v_watchlist_tickers",
            """
            SELECT t.symbol
              FROM portfolio_tickers pt
              JOIN tickers t ON pt.ticker_id = t.id
            """,
        ]
        with self.engine.connect() as conn:
            for query in watchlist_queries:
                try:
                    rows = conn.execute(text(query)).scalars().all()
                    if rows:
                        return [str(sym) for sym in rows]
                except Exception:
                    continue
        return []

    def resolve_symbols(self, symbols: Optional[Sequence[str]]) -> List[str]:
        if symbols:
            return list(dict.fromkeys([s.strip().upper() for s in symbols if s]))
        watchlist = self._fetch_watchlist_symbols()
        return list(dict.fromkeys([s.strip().upper() for s in watchlist if s]))

    def _get_or_create_symbol_id(self, conn, symbol: str) -> uuid.UUID:
        row = conn.execute(text("SELECT id FROM tickers WHERE symbol = :symbol"), {"symbol": symbol}).scalar_one_or_none()
        if row:
            return row
        new_id = uuid.uuid4()
        conn.execute(
            text(
                """
                INSERT INTO tickers (id, symbol, created_at, updated_at)
                VALUES (:id, :symbol, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (symbol) DO NOTHING
                """
            ),
            {"id": new_id, "symbol": symbol},
        )
        row = conn.execute(text("SELECT id FROM tickers WHERE symbol = :symbol"), {"symbol": symbol}).scalar_one()
        return row

    def _fetch_ohlcv_slice(self, symbol: str, target_date: date, lookback_days: int) -> pd.DataFrame:
        start_date = target_date - timedelta(days=lookback_days)
        with self.engine.connect() as conn:
            query = text(
                """
                SELECT DATE(o.time) AS date,
                       o.open,
                       o.high,
                       o.low,
                       o.close,
                       o.volume
                  FROM ohlcv_daily o
                  JOIN tickers t ON o.symbol_id = t.id
                 WHERE t.symbol = :symbol
                   AND DATE(o.time) BETWEEN :start_date AND :target_date
                 ORDER BY date ASC
                """
            )
            df = pd.read_sql(query, conn, params={"symbol": symbol, "start_date": start_date, "target_date": target_date})
        return df

    def _upsert_snapshot(self, conn, symbol: str, target_date: date, metrics: MetricResult) -> None:
        symbol_id = self._get_or_create_symbol_id(conn, symbol)
        payload = {
            "time": datetime.combine(target_date, datetime.min.time()),
            "symbol_id": symbol_id,
            "rsi_14": metrics.rsi_14,
            "macd_line": metrics.macd_line,
            "macd_signal": metrics.macd_signal,
            "macd_histogram": metrics.macd_histogram,
            "sma_20": metrics.sma_20,
            "sma_50": metrics.sma_50,
            "ema_12": metrics.ema_12,
            "ema_26": metrics.ema_26,
            "rvol": metrics.rvol,
            "vsi": metrics.vsi,
            "hv_20": metrics.hv_20,
        }

        insert_sql = text(
            """
            INSERT INTO daily_snapshots (
                time, symbol_id, rsi_14, macd_line, macd_signal, macd_histogram,
                sma_20, sma_50, ema_12, ema_26, rvol, vsi, hv_20
            ) VALUES (
                :time, :symbol_id, :rsi_14, :macd_line, :macd_signal, :macd_histogram,
                :sma_20, :sma_50, :ema_12, :ema_26, :rvol, :vsi, :hv_20
            )
            ON CONFLICT (time, symbol_id) DO UPDATE SET
                rsi_14 = EXCLUDED.rsi_14,
                macd_line = EXCLUDED.macd_line,
                macd_signal = EXCLUDED.macd_signal,
                macd_histogram = EXCLUDED.macd_histogram,
                sma_20 = EXCLUDED.sma_20,
                sma_50 = EXCLUDED.sma_50,
                ema_12 = EXCLUDED.ema_12,
                ema_26 = EXCLUDED.ema_26,
                rvol = EXCLUDED.rvol,
                vsi = EXCLUDED.vsi,
                hv_20 = EXCLUDED.hv_20
            """
        )
        conn.execute(insert_sql, payload)

    def run(self, config: BatchConfig) -> Dict[str, Dict[str, Optional[float]]]:
        target_date = self.resolve_target_date(config.target_date)
        if target_date is None:
            raise RuntimeError("Unable to resolve target date from ohlcv_daily and none provided.")

        symbols = self.resolve_symbols(config.symbols)
        if not symbols:
            raise RuntimeError("No symbols provided or discovered via watchlist.")

        results: Dict[str, Dict[str, Optional[float]]] = {}
        with self.engine.begin() as conn:
            for symbol in symbols:
                try:
                    df = self._fetch_ohlcv_slice(symbol, target_date, config.lookback_days)
                    if df.empty or target_date not in set(df["date"]):
                        logger.warning("Missing OHLCV for symbol on target date", extra={"symbol": symbol, "date": target_date})
                        continue

                    metrics = compute_all_metrics(df, target_date)
                    # If insufficient history, metrics will be None where applicable
                    if len(df) < max(SMA50_WINDOW, MACD_SLOW, RVOL_WINDOW):
                        logger.warning(
                            "Insufficient lookback for full metrics",
                            extra={"symbol": symbol, "rows": len(df), "date": target_date},
                        )

                    self._upsert_snapshot(conn, symbol, target_date, metrics)
                    results[symbol] = metrics.__dict__
                except Exception as exc:
                    logger.error("Failed to process symbol", extra={"symbol": symbol, "error": str(exc)})
                    continue
        return results
