from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import psycopg2
import pytest

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.metrics.b4_wyckoff_derived_job import run_wyckoff_derived_job


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


def _snapshot_time_for_date(snapshot_date: date) -> datetime:
    return datetime(
        snapshot_date.year,
        snapshot_date.month,
        snapshot_date.day,
        23,
        59,
        59,
        999999,
        tzinfo=timezone.utc,
    )


def _insert_ticker(conn, symbol: str) -> str:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tickers (symbol) VALUES (%s) RETURNING id::text", (symbol,))
        ticker_id = cur.fetchone()[0]
    conn.commit()
    return ticker_id


def _seed_daily_snapshot(conn, *, ticker_id: str, snapshot_date: date, regime: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO daily_snapshots (time, ticker_id, wyckoff_regime, created_at)
            VALUES (%s, %s, %s, %s)
            """,
            (
                _snapshot_time_for_date(snapshot_date),
                ticker_id,
                regime,
                _snapshot_time_for_date(snapshot_date),
            ),
        )
    conn.commit()


def _ensure_canonical_events_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS wyckoff_canonical_events (
                ticker_id UUID NOT NULL,
                event_date DATE NOT NULL,
                event_type VARCHAR(20) NOT NULL,
                event_order INTEGER NOT NULL DEFAULT 0
            )
            """
        )
    conn.commit()


def _seed_canonical_event(
    conn,
    *,
    ticker_id: str,
    event_date: date,
    event_type: str,
    event_order: int,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO wyckoff_canonical_events (ticker_id, event_date, event_type, event_order)
            VALUES (%s, %s, %s, %s)
            """,
            (ticker_id, event_date, event_type, event_order),
        )
    conn.commit()


def _count_rows(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0])


@pytest.mark.integration
@pytest.mark.db
def test_b4_end_to_end_and_idempotent() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    start_date = date(2025, 1, 1)
    dates = [start_date + timedelta(days=offset) for offset in range(6)]

    with psycopg2.connect(db_url) as conn:
        _ensure_canonical_events_table(conn)
        ticker_id = _insert_ticker(conn, "AAPL")

        for idx, snapshot_date in enumerate(dates):
            regime = "ACCUMULATION" if idx < 5 else "MARKUP"
            _seed_daily_snapshot(conn, ticker_id=ticker_id, snapshot_date=snapshot_date, regime=regime)

        _seed_canonical_event(conn, ticker_id=ticker_id, event_date=dates[0], event_type="SC", event_order=1)
        _seed_canonical_event(conn, ticker_id=ticker_id, event_date=dates[1], event_type="AR", event_order=2)
        _seed_canonical_event(conn, ticker_id=ticker_id, event_date=dates[2], event_type="SPRING", event_order=3)
        _seed_canonical_event(conn, ticker_id=ticker_id, event_date=dates[5], event_type="SOS", event_order=4)

        run_wyckoff_derived_job(conn, include_evidence=True)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT date, prior_regime, new_regime, duration_bars
                FROM wyckoff_regime_transitions
                WHERE ticker_id = %s
                """,
                (ticker_id,),
            )
            transition = cur.fetchone()
            assert transition is not None
            assert transition[0] == dates[5]
            assert transition[1] == "ACCUMULATION"
            assert transition[2] == "MARKUP"
            assert transition[3] == 5

            cur.execute(
                """
                SELECT sequence_id, start_date, completion_date, events_in_sequence
                FROM wyckoff_sequences
                WHERE ticker_id = %s
                """,
                (ticker_id,),
            )
            sequence = cur.fetchone()
            assert sequence is not None
            assert sequence[0] == "SEQ_ACCUM_BREAKOUT"
            assert sequence[1] == dates[0]
            assert sequence[2] == dates[5]
            assert isinstance(sequence[3], list)

            cur.execute(
                """
                SELECT event_date, event_type, prior_regime, context_label
                FROM wyckoff_context_events
                WHERE ticker_id = %s
                """,
                (ticker_id,),
            )
            context = cur.fetchone()
            assert context is not None
            assert context[0] == dates[5]
            assert context[1] == "SOS"
            assert context[2] == "ACCUMULATION"
            assert context[3] == "SOS_after_ACCUMULATION"

            cur.execute(
                """
                SELECT date, evidence_json
                FROM wyckoff_snapshot_evidence
                WHERE ticker_id = %s
                """,
                (ticker_id,),
            )
            evidence = cur.fetchone()
            assert evidence is not None
            assert evidence[0] == dates[5]
            evidence_payload = evidence[1] or {}
            assert "transitions" in evidence_payload
            assert "sequences" in evidence_payload
            assert "context_events" in evidence_payload

        run_wyckoff_derived_job(conn, include_evidence=True)
        assert _count_rows(conn, "wyckoff_regime_transitions") == 1
        assert _count_rows(conn, "wyckoff_sequences") == 1
        assert _count_rows(conn, "wyckoff_context_events") == 1
        assert _count_rows(conn, "wyckoff_snapshot_evidence") == 1
