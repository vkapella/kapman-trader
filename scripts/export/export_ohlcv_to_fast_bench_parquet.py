from __future__ import annotations

import logging
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import sqlalchemy as sa

DEFAULT_DAYS = 730
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "fast_bench" / "ohlcv_parquet"


@dataclass(frozen=True)
class SourceConfig:
    table: str
    date_column: str
    symbol_column: str | None  # symbol column on the source table (None if join is required)
    join_key: str | None  # FK on source table to tickers.id when a join is needed


def _configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("export_ohlcv_to_fast_bench")


def _make_engine() -> sa.Engine:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is required to export OHLCV.")
    return sa.create_engine(db_url)


def _resolve_source(conn: sa.Connection) -> SourceConfig:
    tables = set(
        conn.execute(
            sa.text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('ohlcv', 'ohlcv_daily')
                """
            )
        ).scalars()
    )
    if "ohlcv" in tables:
        return SourceConfig(table="ohlcv", date_column="date", symbol_column=None, join_key="ticker_id")

    if "ohlcv_daily" in tables:
        cols = set(
            conn.execute(
                sa.text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'ohlcv_daily'
                    """
                )
            ).scalars()
        )
        date_column = "date" if "date" in cols else "time" if "time" in cols else None
        if date_column is None:
            raise RuntimeError("ohlcv_daily is missing a date/time column.")

        if "symbol" in cols:
            return SourceConfig(table="ohlcv_daily", date_column=date_column, symbol_column="symbol", join_key=None)
        if "ticker_id" in cols:
            return SourceConfig(table="ohlcv_daily", date_column=date_column, symbol_column=None, join_key="ticker_id")
        if "symbol_id" in cols:
            return SourceConfig(table="ohlcv_daily", date_column=date_column, symbol_column=None, join_key="symbol_id")

        raise RuntimeError("ohlcv_daily lacks symbol identifiers required for export.")

    raise RuntimeError("No supported OHLCV table found (expected ohlcv or ohlcv_daily).")


def _date_bounds(conn: sa.Connection, source: SourceConfig) -> tuple[pd.Timestamp, pd.Timestamp]:
    max_value = conn.execute(sa.text(f"SELECT max({source.date_column}) FROM {source.table}")).scalar()
    if max_value is None:
        raise RuntimeError(f"{source.table} is empty; nothing to export.")
    end_ts = pd.to_datetime(max_value)
    start_ts = end_ts - pd.Timedelta(days=DEFAULT_DAYS)
    return start_ts, end_ts


def _load_dataframe(conn: sa.Connection, source: SourceConfig, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
    if source.symbol_column:
        query = sa.text(
            f"""
            SELECT
              o.{source.symbol_column} AS symbol,
              o.{source.date_column}::date AS date,
              o.open,
              o.high,
              o.low,
              o.close,
              o.volume
            FROM {source.table} o
            WHERE o.{source.date_column} >= :start_ts
              AND o.{source.date_column} <= :end_ts
            ORDER BY o.{source.symbol_column}, o.{source.date_column}
            """
        )
        params = {"start_ts": start_ts, "end_ts": end_ts}
    else:
        query = sa.text(
            f"""
            SELECT
              t.symbol AS symbol,
              o.{source.date_column}::date AS date,
              o.open,
              o.high,
              o.low,
              o.close,
              o.volume
            FROM {source.table} o
            JOIN tickers t ON o.{source.join_key} = t.id
            WHERE o.{source.date_column} >= :start_ts
              AND o.{source.date_column} <= :end_ts
            ORDER BY t.symbol, o.{source.date_column}
            """
        )
        params = {"start_ts": start_ts, "end_ts": end_ts}

    df = pd.read_sql(query, conn, params=params)
    if df.empty:
        raise RuntimeError("No OHLCV rows returned for the requested window.")
    return df


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[["symbol", "date", "open", "high", "low", "close", "volume"]]
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    return df


def _write_parquet(df: pd.DataFrame, output_dir: Path, logger: logging.Logger) -> None:
    if output_dir.exists():
        logger.info("Removing existing output directory: %s", output_dir)
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Writing Parquet partitions to %s", output_dir)
    df.to_parquet(output_dir, engine="pyarrow", index=False, partition_cols=["symbol"])


def _verify_partition(output_dir: Path, sample_symbol: str, logger: logging.Logger) -> None:
    sample_df = pd.read_parquet(
        output_dir,
        engine="pyarrow",
        filters=[("symbol", "==", sample_symbol)],
    )
    if sample_df.empty:
        raise RuntimeError(f"Verification failed: no rows found for symbol {sample_symbol}.")

    sample_df["date"] = pd.to_datetime(sample_df["date"]).dt.date
    min_date = sample_df["date"].min()
    max_date = sample_df["date"].max()
    logger.info(
        "Verification: symbol=%s rows=%s date_range=%s → %s columns=%s",
        sample_symbol,
        len(sample_df),
        min_date,
        max_date,
        list(sample_df.columns),
    )


def main() -> int:
    logger = _configure_logging()
    engine: sa.Engine | None = None
    try:
        engine = _make_engine()
        with engine.connect() as conn:
            source = _resolve_source(conn)
            logger.info(
                "Using source table %s (date column: %s, symbol via %s)",
                source.table,
                source.date_column,
                source.symbol_column or f"tickers join on {source.join_key}",
            )

            start_ts, end_ts = _date_bounds(conn, source)
            logger.info(
                "Export window: %s → %s (%s days back)",
                start_ts.date(),
                end_ts.date(),
                DEFAULT_DAYS,
            )

            df_raw = _load_dataframe(conn, source, start_ts, end_ts)
    except Exception as exc:  # pragma: no cover - script guard
        logger.error("Export failed: %s", exc)
        return 1

    df = _prepare_dataframe(df_raw)
    row_count = len(df)
    symbol_count = df["symbol"].nunique()
    min_date = min(df["date"])
    max_date = max(df["date"])
    logger.info(
        "Loaded %s rows across %s symbols (%s → %s).",
        row_count,
        symbol_count,
        min_date,
        max_date,
    )

    if row_count == 0:
        logger.error("Aborting: zero rows loaded.")
        return 1

    try:
        _write_parquet(df, OUTPUT_DIR, logger)
        first_symbol = df["symbol"].iloc[0]
        _verify_partition(OUTPUT_DIR, first_symbol, logger)
        logger.info("Export complete. Output directory: %s", OUTPUT_DIR)
        logger.info("Example filter: pandas.read_parquet('%s', filters=[[('symbol', '==', '%s')]])", OUTPUT_DIR, first_symbol)
    except Exception as exc:  # pragma: no cover - script guard
        logger.error("Failed while writing/verifying Parquet: %s", exc)
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    return 0


if __name__ == "__main__":
    sys.exit(main())
