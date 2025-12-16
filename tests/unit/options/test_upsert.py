from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from core.db.options_upsert import upsert_option_chains


def _sample_records():
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "symbol": "TEST_OPT_A",
            "time": ts,
            "expiration_date": ts.date(),
            "strike_price": 150,
            "option_type": "CALL",
            "bid": 1.0,
            "ask": 1.5,
            "last": 1.25,
            "volume": 10,
            "open_interest": 20,
            "implied_volatility": 0.2,
            "delta": 0.5,
            "gamma": 0.1,
            "theta": -0.05,
            "vega": 0.12,
            "oi_change": 1,
            "volume_oi_ratio": 0.5,
            "moneyness": None,
        }
    ]


def _session_mock():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_insert_first_run():
    session = _session_mock()

    async def mark_new(_session, records):
        for r in records:
            r["_exists"] = False

    with patch("core.db.options_upsert._get_or_create_ticker_id", new=AsyncMock(return_value="ID")), patch(
        "core.db.options_upsert._mark_existing", new=mark_new
    ):
        result = await upsert_option_chains(_sample_records(), session=session)

    assert result["inserted"] == 1
    assert session.execute.call_count == 1


@pytest.mark.asyncio
async def test_idempotent_second_run():
    session = _session_mock()

    async def mark_existing(_session, records):
        for r in records:
            r["_exists"] = True

    with patch("core.db.options_upsert._get_or_create_ticker_id", new=AsyncMock(return_value="ID")), patch(
        "core.db.options_upsert._mark_existing", new=mark_existing
    ):
        result = await upsert_option_chains(_sample_records(), session=session)

    assert result["inserted"] == 0
    assert result["updated"] == 1
    assert session.execute.call_count == 1


@pytest.mark.asyncio
async def test_updates_on_change():
    session = _session_mock()

    async def mark_existing(_session, records):
        for r in records:
            r["_exists"] = True

    with patch("core.db.options_upsert._get_or_create_ticker_id", new=AsyncMock(return_value="ID")), patch(
        "core.db.options_upsert._mark_existing", new=mark_existing
    ):
        records = _sample_records()
        records[0]["volume"] = 999
        result = await upsert_option_chains(records, session=session)

    assert result["updated"] == 1
    assert session.execute.call_count == 1
