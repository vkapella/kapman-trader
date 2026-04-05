from __future__ import annotations

import os
from datetime import date, datetime, timezone

import psycopg2
import pytest
from psycopg2.extras import Json

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.metrics.b4_1_wyckoff_sequences_job import run_b4_1_wyckoff_sequences_job
from core.metrics.c4_batch_ai_screening_job import (
    _load_wyckoff_sequence_events,
    _load_wyckoff_sequences,
)


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


def _seed_daily_snapshot(
    conn,
    *,
    ticker_id: str,
    snapshot_date: date,
    regime: str,
    events_detected: list[str],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO daily_snapshots (
                time,
                ticker_id,
                events_detected,
                wyckoff_regime,
                wyckoff_regime_confidence,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                _snapshot_time_for_date(snapshot_date),
                ticker_id,
                events_detected,
                regime,
                1.0,
                _snapshot_time_for_date(snapshot_date),
            ),
        )
    conn.commit()


def _seed_daily_snapshot_at_time(
    conn,
    *,
    ticker_id: str,
    snapshot_time: datetime,
    regime: str | None,
    events_detected: list[str],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO daily_snapshots (
                time,
                ticker_id,
                events_detected,
                wyckoff_regime,
                wyckoff_regime_confidence,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                snapshot_time,
                ticker_id,
                events_detected,
                regime,
                1.0 if regime is not None else None,
                snapshot_time,
            ),
        )
    conn.commit()


def _seed_transition(
    conn,
    *,
    ticker_id: str,
    transition_date: date,
    prior_regime: str,
    new_regime: str,
    duration_bars: int,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO wyckoff_regime_transitions (
                ticker_id,
                date,
                prior_regime,
                new_regime,
                duration_bars
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (ticker_id, transition_date, prior_regime, new_regime, duration_bars),
        )
    conn.commit()


def _count_rows(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0])


@pytest.mark.integration
@pytest.mark.db
def test_b4_1_end_to_end_uses_full_event_stream_and_is_idempotent() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    dates = [date(2025, 1, day) for day in range(1, 6)]

    with psycopg2.connect(db_url) as conn:
        ticker_id = _insert_ticker(conn, "AAPL")

        _seed_daily_snapshot(
            conn,
            ticker_id=ticker_id,
            snapshot_date=dates[0],
            regime="ACCUMULATION",
            events_detected=["SC"],
        )
        _seed_daily_snapshot(
            conn,
            ticker_id=ticker_id,
            snapshot_date=dates[1],
            regime="ACCUMULATION",
            events_detected=["AR"],
        )
        _seed_daily_snapshot(
            conn,
            ticker_id=ticker_id,
            snapshot_date=dates[2],
            regime="ACCUMULATION",
            events_detected=["SPRING"],
        )
        _seed_daily_snapshot(
            conn,
            ticker_id=ticker_id,
            snapshot_date=dates[3],
            regime="ACCUMULATION",
            events_detected=[],
        )
        _seed_daily_snapshot(
            conn,
            ticker_id=ticker_id,
            snapshot_date=dates[4],
            regime="MARKUP",
            events_detected=["SOS"],
        )
        _seed_transition(
            conn,
            ticker_id=ticker_id,
            transition_date=dates[4],
            prior_regime="ACCUMULATION",
            new_regime="MARKUP",
            duration_bars=4,
        )

        stats = run_b4_1_wyckoff_sequences_job(
            conn,
            start_date=dates[4],
            end_date=dates[4],
        )

        assert stats["sequences_written"] == 1
        assert stats["sequences_invalidated"] == 0

        with conn.cursor() as cur:
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
            assert sequence[0] == "ACCUMULATION_BREAKOUT"
            assert sequence[1] == dates[0]
            assert sequence[2] == dates[4]

            payload = sequence[3] or {}
            assert payload["prior_regime"] == "ACCUMULATION"
            assert payload["entry_regime"] == "ACCUMULATION"
            assert payload["post_terminal_regime"] == "MARKUP"
            assert payload["supporting_event_count"] == 3
            assert payload["invalidated"] is False

            cur.execute(
                """
                SELECT event_type, event_date, event_role, event_order
                FROM wyckoff_sequence_events
                WHERE ticker_id = %s
                ORDER BY event_order ASC
                """,
                (ticker_id,),
            )
            event_rows = cur.fetchall()
            assert [(row[0], row[1], row[2], row[3]) for row in event_rows] == [
                ("SC", dates[0], "SUPPORTING", 1),
                ("AR", dates[1], "SUPPORTING", 2),
                ("SPRING", dates[2], "SUPPORTING", 3),
                ("SOS", dates[4], "TERMINAL", 4),
            ]

        rerun_stats = run_b4_1_wyckoff_sequences_job(
            conn,
            start_date=dates[4],
            end_date=dates[4],
        )

        assert rerun_stats["sequences_written"] == 0
        assert _count_rows(conn, "wyckoff_sequences") == 1
        assert _count_rows(conn, "wyckoff_sequence_events") == 4


@pytest.mark.integration
@pytest.mark.db
def test_b4_1_dedupes_mixed_snapshot_timestamp_conventions_by_ny_trading_day() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    with psycopg2.connect(db_url) as conn:
        ticker_id = _insert_ticker(conn, "ROK")

        _seed_daily_snapshot_at_time(
            conn,
            ticker_id=ticker_id,
            snapshot_time=datetime(2026, 2, 6, 23, 59, 59, 999999, tzinfo=timezone.utc),
            regime="DISTRIBUTION",
            events_detected=["BC"],
        )
        _seed_daily_snapshot_at_time(
            conn,
            ticker_id=ticker_id,
            snapshot_time=datetime(2026, 2, 11, 23, 59, 59, 999999, tzinfo=timezone.utc),
            regime="DISTRIBUTION",
            events_detected=["AR_TOP"],
        )
        # Legacy ET-end-of-day row that maps to the same NY trading day as 2026-02-11.
        _seed_daily_snapshot_at_time(
            conn,
            ticker_id=ticker_id,
            snapshot_time=datetime(2026, 2, 12, 4, 59, 59, 999999, tzinfo=timezone.utc),
            regime=None,
            events_detected=[],
        )
        _seed_daily_snapshot_at_time(
            conn,
            ticker_id=ticker_id,
            snapshot_time=datetime(2026, 2, 12, 23, 59, 59, 999999, tzinfo=timezone.utc),
            regime="MARKDOWN",
            events_detected=["SOW"],
        )
        _seed_transition(
            conn,
            ticker_id=ticker_id,
            transition_date=date(2026, 2, 12),
            prior_regime="DISTRIBUTION",
            new_regime="MARKDOWN",
            duration_bars=6,
        )

        stats = run_b4_1_wyckoff_sequences_job(
            conn,
            start_date=date(2026, 2, 12),
            end_date=date(2026, 2, 12),
        )

        assert stats["sequences_written"] == 1
        assert stats["sequences_skipped"] == 0

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sequence_id, start_date, completion_date, events_in_sequence
                FROM wyckoff_sequences
                WHERE ticker_id = %s
                """,
                (ticker_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "DISTRIBUTION_BREAKDOWN"
            assert row[1] == date(2026, 2, 6)
            assert row[2] == date(2026, 2, 12)

            payload = row[3] or {}
            assert payload["prior_regime"] == "DISTRIBUTION"
            assert payload["entry_regime"] == "DISTRIBUTION"
            assert payload["post_terminal_regime"] == "MARKDOWN"
            assert payload["supporting_event_count"] == 2

            cur.execute(
                """
                SELECT event_type, event_date, event_role, event_order
                FROM wyckoff_sequence_events
                WHERE ticker_id = %s
                ORDER BY event_order ASC
                """,
                (ticker_id,),
            )
            assert cur.fetchall() == [
                ("BC", date(2026, 2, 6), "SUPPORTING", 1),
                ("AR_TOP", date(2026, 2, 11), "SUPPORTING", 2),
                ("SOW", date(2026, 2, 12), "TERMINAL", 3),
            ]


@pytest.mark.integration
@pytest.mark.db
def test_c4_loaders_only_return_canonical_b4_1_sequences() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    snapshot_date = date(2025, 2, 1)

    with psycopg2.connect(db_url) as conn:
        ticker_id = _insert_ticker(conn, "MSFT")

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO wyckoff_sequences (
                    ticker_id,
                    sequence_id,
                    start_date,
                    completion_date,
                    events_in_sequence
                )
                VALUES
                    (%s, %s, %s, %s, %s),
                    (%s, %s, %s, %s, %s)
                """,
                (
                    ticker_id,
                    "ACCUMULATION_BREAKOUT",
                    snapshot_date,
                    snapshot_date,
                    Json({"terminal_event": "SOS"}),
                    ticker_id,
                    "SEQ_ACCUM_BREAKOUT",
                    snapshot_date,
                    snapshot_date,
                    Json([{"event": "SOS", "date": snapshot_date.isoformat()}]),
                ),
            )
            cur.execute(
                """
                INSERT INTO wyckoff_sequence_events (
                    ticker_id,
                    sequence_id,
                    completion_date,
                    event_type,
                    event_date,
                    event_role,
                    event_order
                )
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s),
                    (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ticker_id,
                    "ACCUMULATION_BREAKOUT",
                    snapshot_date,
                    "SOS",
                    snapshot_date,
                    "TERMINAL",
                    1,
                    ticker_id,
                    "SEQ_ACCUM_BREAKOUT",
                    snapshot_date,
                    "SOS",
                    snapshot_date,
                    "TERMINAL",
                    1,
                ),
            )
        conn.commit()

        sequences = _load_wyckoff_sequences(conn, ticker_id=ticker_id, snapshot_date=snapshot_date)
        sequence_events = _load_wyckoff_sequence_events(
            conn,
            ticker_id=ticker_id,
            snapshot_date=snapshot_date,
        )

        assert [row["sequence_id"] for row in sequences] == ["ACCUMULATION_BREAKOUT"]
        assert [row["sequence_id"] for row in sequence_events] == ["ACCUMULATION_BREAKOUT"]
