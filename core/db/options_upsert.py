import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.client import async_session

logger = logging.getLogger(__name__)


async def _get_or_create_ticker_id(session: AsyncSession, symbol: str) -> uuid.UUID:
    result = await session.execute(
        text("SELECT id FROM tickers WHERE symbol = :symbol"), {"symbol": symbol}
    )
    ticker_id = result.scalar_one_or_none()
    if ticker_id:
        return ticker_id

    new_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO tickers (id, symbol, created_at, updated_at)
            VALUES (:id, :symbol, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (symbol) DO NOTHING
            """
        ),
        {"id": new_id, "symbol": symbol},
    )
    # Fetch again to ensure we return the persisted id (handles race/conflict)
    result = await session.execute(
        text("SELECT id FROM tickers WHERE symbol = :symbol"), {"symbol": symbol}
    )
    ticker_id = result.scalar_one()
    return ticker_id


def _split_existing_flags(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    return [r for r in records if r.get("_exists")], [r for r in records if not r.get("_exists")]


async def _mark_existing(session: AsyncSession, records: List[Dict[str, Any]]) -> None:
    for record in records:
        result = await session.execute(
            text(
                """
                SELECT 1 FROM options_chains
                WHERE time = :time
                  AND symbol_id = :symbol_id
                  AND expiration_date = :expiration_date
                  AND strike_price = :strike_price
                  AND option_type = :option_type
                """
            ),
            {
                "time": record["time"],
                "symbol_id": record["symbol_id"],
                "expiration_date": record["expiration_date"],
                "strike_price": record["strike_price"],
                "option_type": record["option_type"],
            },
        )
        record["_exists"] = bool(result.first())


async def upsert_option_chains(
    records: List[Dict[str, Any]], session: Optional[AsyncSession] = None
) -> Dict[str, int]:
    """
    Idempotent upsert of normalized option chain rows.
    """
    if not records:
        return {"inserted": 0, "updated": 0, "skipped": 0, "total": 0}

    owns_session = session is None
    if owns_session:
        session = async_session()

    assert session is not None  # for type checkers

    try:
        prepared: List[Dict[str, Any]] = []
        for record in records:
            ticker_id = await _get_or_create_ticker_id(session, record["symbol"])
            row = dict(record)
            row["symbol_id"] = ticker_id
            prepared.append(row)

        await _mark_existing(session, prepared)

        existing, new = _split_existing_flags(prepared)

        insert_sql = text(
            """
            INSERT INTO options_chains (
                time, symbol_id, expiration_date, strike_price, option_type,
                bid, ask, last, volume, open_interest,
                implied_volatility, delta, gamma, theta, vega,
                oi_change, volume_oi_ratio, moneyness
            ) VALUES (
                :time, :symbol_id, :expiration_date, :strike_price, :option_type,
                :bid, :ask, :last, :volume, :open_interest,
                :implied_volatility, :delta, :gamma, :theta, :vega,
                :oi_change, :volume_oi_ratio, :moneyness
            )
            """
        )

        update_sql = text(
            """
            UPDATE options_chains
               SET bid = :bid,
                   ask = :ask,
                   last = :last,
                   volume = :volume,
                   open_interest = :open_interest,
                   implied_volatility = :implied_volatility,
                   delta = :delta,
                   gamma = :gamma,
                   theta = :theta,
                   vega = :vega,
                   oi_change = :oi_change,
                   volume_oi_ratio = :volume_oi_ratio,
                   moneyness = :moneyness
             WHERE time = :time
               AND symbol_id = :symbol_id
               AND expiration_date = :expiration_date
               AND strike_price = :strike_price
               AND option_type = :option_type
            """
        )

        inserted = updated = 0

        for row in new:
            await session.execute(insert_sql, row)
            inserted += 1

        for row in existing:
            await session.execute(update_sql, row)
            updated += 1

        await session.commit()

        logger.info(
            "Upserted option chains",
            extra={
                "stage": "upsert",
                "symbol": records[0]["symbol"],
                "inserted": inserted,
                "updated": updated,
                "skipped": 0,
                "total": len(records),
            },
        )
        return {
            "inserted": inserted,
            "updated": updated,
            "skipped": 0,
            "total": len(records),
        }
    except Exception:
        await session.rollback()
        raise
    finally:
        if owns_session:
            await session.close()
