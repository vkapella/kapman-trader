import logging
import time as time_module
from datetime import date
from typing import Iterable, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.client import async_session
from core.db.options_upsert import upsert_option_chains
from core.pipeline.options_normalizer import normalize_contracts
from core.providers.market_data.polygon_options import PolygonOptionsProvider

logger = logging.getLogger(__name__)


async def _get_watchlist_symbols(session: AsyncSession) -> List[str]:
    result = await session.execute(
        text(
            """
            SELECT DISTINCT t.symbol
            FROM portfolio_tickers pt
            JOIN tickers t ON t.id = pt.ticker_id
            JOIN portfolios p ON p.id = pt.portfolio_id
            WHERE t.is_active IS TRUE
            """
        )
    )
    return sorted([row[0] for row in result.fetchall()])


async def ingest_symbol(
    symbol: str,
    provider: Optional[PolygonOptionsProvider] = None,
    as_of_date: Optional[date] = None,
    session: Optional[AsyncSession] = None,
) -> dict:
    provider = provider or PolygonOptionsProvider()
    as_of_date = as_of_date or date.today()
    owns_session = session is None
    if owns_session:
        session = async_session()

    assert session is not None

    start = time_module.time()
    try:
        raw_contracts = await provider.get_options_chain(symbol, as_of_date)
        normalized = normalize_contracts(raw_contracts, symbol, as_of_date)
        upsert_result = await upsert_option_chains(normalized, session=session)
        duration = time_module.time() - start
        logger.info(
            "Ingested options chain",
            extra={
                "stage": "runner",
                "symbol": symbol,
                "duration_ms": int(duration * 1000),
                "processed": len(normalized),
            },
        )
        return upsert_result
    except Exception as exc:
        duration = time_module.time() - start
        logger.error(
            "Failed to ingest options chain",
            extra={
                "stage": "runner",
                "symbol": symbol,
                "duration_ms": int(duration * 1000),
                "error": str(exc),
            },
        )
        raise
    finally:
        if owns_session:
            await session.close()


async def run_batch(
    symbols: Optional[Iterable[str]] = None,
    provider: Optional[PolygonOptionsProvider] = None,
    as_of_date: Optional[date] = None,
) -> dict:
    as_of_date = as_of_date or date.today()
    total_start = time_module.time()
    errors = 0
    processed_symbols: List[str] = []

    async with async_session() as session:
        if symbols is None:
            symbols = await _get_watchlist_symbols(session)
        sorted_symbols = sorted(set(symbols))

        for symbol in sorted_symbols:
            try:
                await ingest_symbol(
                    symbol,
                    provider=provider,
                    as_of_date=as_of_date,
                    session=session,
                )
                processed_symbols.append(symbol)
            except Exception:
                errors += 1
                continue

    total_duration = time_module.time() - total_start
    logger.info(
        "Completed options batch ingestion",
        extra={
            "stage": "runner",
            "duration_ms": int(total_duration * 1000),
            "symbols_processed": processed_symbols,
            "error_count": errors,
        },
    )
    return {
        "symbols_processed": processed_symbols,
        "error_count": errors,
        "duration_ms": int(total_duration * 1000),
    }


async def handle_symbol_event(event: dict, provider: Optional[PolygonOptionsProvider] = None) -> dict:
    """
    Minimal event entry point. Expects an event containing a symbol field.
    """
    symbol = event.get("symbol") or event.get("detail", {}).get("symbol")
    if not symbol:
        raise ValueError("Symbol missing from event")
    return await ingest_symbol(symbol, provider=provider)
