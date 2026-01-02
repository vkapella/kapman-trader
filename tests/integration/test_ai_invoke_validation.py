from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal

import psycopg2
import pytest

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.providers.ai import invoke as invoke_module


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


def _seed_ticker(conn, symbol: str) -> str:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tickers (symbol) VALUES (%s) RETURNING id::text", (symbol,))
        ticker_id = cur.fetchone()[0]
    conn.commit()
    return ticker_id


def _seed_option_chain(
    conn,
    *,
    ticker_id: str,
    snapshot_time: datetime,
    expiration: date,
    strike: Decimal,
    option_type: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO options_chains (
                time,
                ticker_id,
                expiration_date,
                strike_price,
                option_type
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (snapshot_time, ticker_id, expiration, strike, option_type),
        )
    conn.commit()


def _raw_response(
    *,
    primary_strike: int,
    primary_expiration: str,
    primary_type: str,
    alt_strike: int,
    alt_expiration: str,
    alt_type: str,
) -> dict:
    return {
        "snapshot_metadata": {
            "ticker": "AAPL",
            "snapshot_time": "2026-01-10T00:00:00+00:00",
            "model_version": "test",
            "wyckoff_regime": "MARKUP",
            "wyckoff_primary_event": "SOS",
            "data_completeness_flags": {},
        },
        "primary_recommendation": {
            "action": "ENTER",
            "strategy_class": "LONG_CALL",
            "direction": "BULLISH",
            "confidence_score": 80,
            "time_horizon": "short",
            "rationale_summary": "Test rationale.",
            "option_strike": primary_strike,
            "option_expiration": primary_expiration,
            "option_type": primary_type,
        },
        "alternative_recommendations": [
            {
                "label": "Valid alt",
                "action": "WAIT",
                "strategy_class": "NONE",
                "direction": "NEUTRAL",
                "confidence_score": 60,
                "blocking_reason": "Blocked.",
                "promotion_conditions": "Clear veto.",
                "option_strike": alt_strike,
                "option_expiration": alt_expiration,
                "option_type": alt_type,
            }
        ],
        "reasoning_trace": {
            "fired_rules": [],
            "cluster_contributions": [{"cluster": "Meta", "impact": "TEST"}],
            "supporting_factors": [],
            "blocking_factors": [],
        },
        "confidence_summary": {
            "confidence_type": "RELATIVE",
            "ranking_basis": "Primary outranks alternatives by construction",
            "confidence_gap_notes": None,
        },
        "missing_data_declaration": [],
        "guardrails_and_disclaimers": ["Guardrail"],
    }


@pytest.mark.integration
@pytest.mark.db
def test_invoke_filters_invalid_contracts(monkeypatch: pytest.MonkeyPatch) -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_and_migrate(db_url, default_migrations_dir())

    snapshot_time = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
    expiration = date(2026, 1, 17)

    with psycopg2.connect(db_url) as conn:
        ticker_id = _seed_ticker(conn, "AAPL")
        _seed_option_chain(
            conn,
            ticker_id=ticker_id,
            snapshot_time=snapshot_time,
            expiration=expiration,
            strike=Decimal("150.0000"),
            option_type="C",
        )

    payload = _raw_response(
        primary_strike=150,
        primary_expiration="2026-01-17",
        primary_type="C",
        alt_strike=155,
        alt_expiration="2026-01-17",
        alt_type="C",
    )

    async def _fake_invoke(_provider_id: str, _model_id: str, _prompt_text: str) -> str:
        return json.dumps(payload)

    monkeypatch.setattr(invoke_module, "_invoke_provider", _fake_invoke)

    response = invoke_module.invoke_planning_agent(
        provider_id="anthropic",
        model_id="test-model",
        snapshot_payload={"symbol": "AAPL", "snapshot_time": snapshot_time.isoformat()},
        option_context={},
        authority_constraints={},
        instructions={},
        prompt_version="test",
        kapman_model_version="test",
        debug=False,
        dry_run=False,
    )

    assert response["primary_recommendation"]["option_strike"] == 150
    assert len(response["alternative_recommendations"]) == 0


@pytest.mark.integration
@pytest.mark.db
def test_invoke_fails_closed_without_options_chains(monkeypatch: pytest.MonkeyPatch) -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_and_migrate(db_url, default_migrations_dir())

    snapshot_time = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)

    with psycopg2.connect(db_url) as conn:
        _seed_ticker(conn, "AAPL")

    payload = _raw_response(
        primary_strike=150,
        primary_expiration="2026-01-17",
        primary_type="C",
        alt_strike=150,
        alt_expiration="2026-01-17",
        alt_type="C",
    )

    async def _fake_invoke(_provider_id: str, _model_id: str, _prompt_text: str) -> str:
        return json.dumps(payload)

    monkeypatch.setattr(invoke_module, "_invoke_provider", _fake_invoke)

    response = invoke_module.invoke_planning_agent(
        provider_id="anthropic",
        model_id="test-model",
        snapshot_payload={"symbol": "AAPL", "snapshot_time": snapshot_time.isoformat()},
        option_context={},
        authority_constraints={},
        instructions={},
        prompt_version="test",
        kapman_model_version="test",
        debug=False,
        dry_run=False,
    )

    assert response["snapshot_metadata"]["ticker"] == "UNKNOWN"
    assert "Option validation failed" in response["primary_recommendation"]["rationale_summary"]
