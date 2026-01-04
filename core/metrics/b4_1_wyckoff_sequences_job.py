from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, Optional, Sequence

from psycopg2.extras import Json, execute_values

from core.metrics.b1_wyckoff_regime_job import (
    REGIME_ACCUMULATION,
    REGIME_DISTRIBUTION,
    REGIME_MARKDOWN,
    REGIME_MARKUP,
    REGIME_UNKNOWN,
)


DEFAULT_HEARTBEAT_TICKERS = 50

logger = logging.getLogger("kapman.b4_1")

TERMINAL_EVENT_SOS = "SOS"
TERMINAL_EVENT_SOW = "SOW"

SEQUENCE_TYPE_ACCUM_BREAKOUT = "ACCUMULATION_BREAKOUT"
SEQUENCE_TYPE_DISTRIBUTION_BREAKDOWN = "DISTRIBUTION_BREAKDOWN"

SUPPORTING_EVENTS = {
    TERMINAL_EVENT_SOS: ["SC", "AR", "SPRING"],
    TERMINAL_EVENT_SOW: ["BC", "AR_TOP", "UT"],
}

ELIGIBLE_REGIMES = {
    TERMINAL_EVENT_SOS: {REGIME_ACCUMULATION, REGIME_MARKDOWN},
    TERMINAL_EVENT_SOW: {REGIME_DISTRIBUTION, REGIME_MARKUP},
}

INVALIDATING_REGIMES = {
    TERMINAL_EVENT_SOS: {REGIME_DISTRIBUTION, REGIME_MARKUP},
    TERMINAL_EVENT_SOW: {REGIME_ACCUMULATION, REGIME_MARKDOWN},
}

SEQUENCE_TYPES = {
    TERMINAL_EVENT_SOS: SEQUENCE_TYPE_ACCUM_BREAKOUT,
    TERMINAL_EVENT_SOW: SEQUENCE_TYPE_DISTRIBUTION_BREAKDOWN,
}


@dataclass(frozen=True)
class StructuralEvent:
    event_date: date
    event_type: str


@dataclass(frozen=True)
class SequenceEvent:
    event_type: str
    event_date: date
    event_role: str
    event_order: int


@dataclass(frozen=True)
class SequenceRecord:
    sequence_type: str
    terminal_event: str
    start_date: date
    terminal_date: date
    prior_regime: str
    confidence: float
    invalidated: bool
    invalidated_reason: Optional[str]
    events: tuple[SequenceEvent, ...]


@dataclass
class B41BatchStats:
    total_tickers: int
    processed: int = 0
    sequences_written: int = 0
    sequences_invalidated: int = 0
    sequences_skipped: int = 0
    missing_history: int = 0
    errors: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    def duration(self) -> float:
        return self.end_time - self.start_time

    def to_log_extra(self) -> Dict[str, Any]:
        return {
            "total_tickers": self.total_tickers,
            "processed": self.processed,
            "sequences_written": self.sequences_written,
            "sequences_invalidated": self.sequences_invalidated,
            "sequences_skipped": self.sequences_skipped,
            "missing_history": self.missing_history,
            "errors": self.errors,
            "duration_sec": self.duration(),
        }


def _normalize_regime(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = str(value).upper()
    if normalized in {
        REGIME_ACCUMULATION,
        REGIME_DISTRIBUTION,
        REGIME_MARKDOWN,
        REGIME_MARKUP,
        REGIME_UNKNOWN,
    }:
        return normalized
    return None


def _normalize_event_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = str(value).upper().strip()
    return normalized or None


def _json_dumps_strict(value: Any) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _fetch_active_tickers(conn) -> list[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, UPPER(symbol)
            FROM public.tickers
            WHERE is_active = TRUE
            ORDER BY UPPER(symbol), id::text
            """
        )
        rows = cur.fetchall()
    return [(str(tid), str(symbol)) for tid, symbol in rows]


def _fetch_watchlist_tickers(conn) -> list[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT t.id::text, UPPER(t.symbol)
            FROM public.watchlists w
            JOIN public.tickers t ON UPPER(t.symbol) = UPPER(w.symbol)
            WHERE w.active = TRUE
            ORDER BY UPPER(t.symbol), t.id::text
            """
        )
        rows = cur.fetchall()
    return [(str(tid), str(symbol)) for tid, symbol in rows]


def _fetch_structural_events(
    conn,
    *,
    ticker_id: str,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[StructuralEvent]:
    if start_date and end_date:
        where_clause = "ds.time::date >= %s AND ds.time::date <= %s"
        params = (ticker_id, start_date, end_date)
    elif start_date:
        where_clause = "ds.time::date >= %s"
        params = (ticker_id, start_date)
    elif end_date:
        where_clause = "ds.time::date <= %s"
        params = (ticker_id, end_date)
    else:
        where_clause = "TRUE"
        params = (ticker_id,)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT ds.time::date, ev.event_code
            FROM public.daily_snapshots ds
            CROSS JOIN LATERAL unnest(ds.events_detected) AS ev(event_code)
            WHERE ds.ticker_id = %s
              AND {where_clause}
              AND ev.event_code IN ('SOS', 'SOW')
            ORDER BY ds.time::date ASC, ev.event_code ASC
            """,
            params,
        )
        rows = cur.fetchall()

    events: list[StructuralEvent] = []
    for event_date, event_type in rows:
        normalized = _normalize_event_type(event_type)
        if not event_date or not normalized:
            continue
        events.append(StructuralEvent(event_date=event_date, event_type=normalized))
    return events


def _fetch_daily_regimes(
    conn,
    *,
    ticker_id: str,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[tuple[date, Optional[str], Optional[float]]]:
    if start_date and end_date:
        where_clause = "time::date >= %s AND time::date <= %s"
        params = (ticker_id, start_date, end_date)
    elif start_date:
        where_clause = "time::date >= %s"
        params = (ticker_id, start_date)
    elif end_date:
        where_clause = "time::date <= %s"
        params = (ticker_id, end_date)
    else:
        where_clause = "TRUE"
        params = (ticker_id,)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT time::date, wyckoff_regime, wyckoff_regime_confidence
            FROM public.daily_snapshots
            WHERE ticker_id = %s AND {where_clause}
            ORDER BY time ASC
            """,
            params,
        )
        rows = cur.fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def _fetch_regime_transitions(
    conn,
    *,
    ticker_id: str,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[dict[str, Any]]:
    if start_date and end_date:
        where_clause = "date >= %s AND date <= %s"
        params = (ticker_id, start_date, end_date)
    elif start_date:
        where_clause = "date >= %s"
        params = (ticker_id, start_date)
    elif end_date:
        where_clause = "date <= %s"
        params = (ticker_id, end_date)
    else:
        where_clause = "TRUE"
        params = (ticker_id,)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT date, prior_regime, new_regime, duration_bars
            FROM public.wyckoff_regime_transitions
            WHERE ticker_id = %s AND {where_clause}
            ORDER BY date ASC
            """,
            params,
        )
        rows = cur.fetchall()

    transitions: list[dict[str, Any]] = []
    for row in rows:
        transitions.append(
            {
                "date": row[0],
                "prior_regime": _normalize_regime(row[1]),
                "new_regime": _normalize_regime(row[2]),
                "duration_bars": row[3],
            }
        )
    return transitions


def _regime_by_date(
    snapshot_rows: Sequence[tuple[date, Optional[str], Optional[float]]]
) -> dict[date, Optional[str]]:
    regimes: dict[date, Optional[str]] = {}
    for snapshot_date, regime, _confidence in snapshot_rows:
        regimes[snapshot_date] = _normalize_regime(regime)
    return regimes


def _find_latest_event(
    events: Sequence[StructuralEvent],
    *,
    event_type: str,
    cutoff: date,
) -> Optional[StructuralEvent]:
    for ev in reversed(events):
        if ev.event_date > cutoff:
            continue
        if ev.event_type == event_type:
            return ev
    return None


def _assemble_supporting_events(
    events: Sequence[StructuralEvent],
    *,
    terminal_date: date,
    supporting_types: Sequence[str],
) -> list[StructuralEvent]:
    supporting: list[StructuralEvent] = []
    cutoff = terminal_date
    for event_type in reversed(supporting_types):
        found = _find_latest_event(events, event_type=event_type, cutoff=cutoff)
        if found:
            supporting.append(found)
            cutoff = found.event_date
    supporting.reverse()
    return supporting


def _invalidation_reason(
    transitions: Sequence[dict[str, Any]],
    *,
    start_date: date,
    terminal_date: date,
    terminal_event: str,
) -> Optional[str]:
    invalid_regimes = INVALIDATING_REGIMES.get(terminal_event, set())
    for transition in transitions:
        transition_date = transition.get("date")
        new_regime = transition.get("new_regime")
        if not transition_date or not new_regime:
            continue
        if transition_date < start_date or transition_date > terminal_date:
            continue
        if new_regime in invalid_regimes:
            return f"transition_to_{new_regime}_on_{transition_date.isoformat()}"
    return None


def _compute_confidence(supporting_count: int) -> float:
    base = 0.6
    confidence = base + 0.1 * max(0, supporting_count)
    return min(1.0, round(confidence, 4))


def _sequence_payload(sequence: SequenceRecord) -> dict[str, Any]:
    return {
        "sequence_type": sequence.sequence_type,
        "terminal_event": sequence.terminal_event,
        "prior_regime": sequence.prior_regime,
        "confidence": sequence.confidence,
        "invalidated": sequence.invalidated,
        "invalidated_reason": sequence.invalidated_reason,
        "events": [
            {
                "event_type": ev.event_type,
                "event_date": ev.event_date.isoformat(),
                "event_role": ev.event_role,
                "event_order": ev.event_order,
            }
            for ev in sequence.events
        ],
    }


def _assert_required_tables(conn) -> None:
    required = {
        "daily_snapshots",
        "daily_snapshots",
        "wyckoff_regime_transitions",
        "wyckoff_sequences",
        "wyckoff_sequence_events",
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            """,
            (sorted(required),),
        )
        found = {row[0] for row in cur.fetchall()}
    missing = sorted(required - found)
    if missing:
        raise RuntimeError(f"Missing required public tables: {', '.join(missing)}")


def _derive_sequences_for_events(
    *,
    events: Sequence[StructuralEvent],
    regimes_by_date: dict[date, Optional[str]],
    transitions: Sequence[dict[str, Any]],
) -> list[SequenceRecord]:
    ordered_events = sorted(events, key=lambda ev: (ev.event_date, ev.event_type))
    sequences: list[SequenceRecord] = []

    for terminal in ordered_events:
        if terminal.event_type not in (TERMINAL_EVENT_SOS, TERMINAL_EVENT_SOW):
            continue

        prior_regime = regimes_by_date.get(terminal.event_date)
        if prior_regime not in ELIGIBLE_REGIMES.get(terminal.event_type, set()):
            continue

        supporting_types = SUPPORTING_EVENTS.get(terminal.event_type, [])
        supporting = _assemble_supporting_events(
            ordered_events,
            terminal_date=terminal.event_date,
            supporting_types=supporting_types,
        )
        start_date = supporting[0].event_date if supporting else terminal.event_date
        reason = _invalidation_reason(
            transitions,
            start_date=start_date,
            terminal_date=terminal.event_date,
            terminal_event=terminal.event_type,
        )
        invalidated = reason is not None
        confidence = _compute_confidence(len(supporting))

        sequence_events: list[SequenceEvent] = []
        order = 1
        for ev in supporting:
            sequence_events.append(
                SequenceEvent(
                    event_type=ev.event_type,
                    event_date=ev.event_date,
                    event_role="SUPPORTING",
                    event_order=order,
                )
            )
            order += 1
        sequence_events.append(
            SequenceEvent(
                event_type=terminal.event_type,
                event_date=terminal.event_date,
                event_role="TERMINAL",
                event_order=order,
            )
        )

        sequences.append(
            SequenceRecord(
                sequence_type=SEQUENCE_TYPES[terminal.event_type],
                terminal_event=terminal.event_type,
                start_date=start_date,
                terminal_date=terminal.event_date,
                prior_regime=prior_regime,
                confidence=confidence,
                invalidated=invalidated,
                invalidated_reason=reason,
                events=tuple(sequence_events),
            )
        )

    sequences.sort(key=lambda seq: (seq.terminal_date, seq.sequence_type, seq.start_date))
    return sequences


def _should_emit_heartbeat(processed: int, heartbeat_every: int) -> bool:
    return heartbeat_every > 0 and processed > 0 and processed % heartbeat_every == 0


def run_b4_1_wyckoff_sequences_job(
    conn,
    *,
    use_watchlist: bool = False,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    heartbeat_every: int = 0,
    verbose: bool = False,
    log: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    log = log or logger
    t0 = time.monotonic()

    _assert_required_tables(conn)

    tickers = _fetch_watchlist_tickers(conn) if use_watchlist else _fetch_active_tickers(conn)
    total_tickers = len(tickers)
    stats = B41BatchStats(total_tickers=total_tickers, start_time=t0)

    if total_tickers == 0:
        log.warning("[B4.1] No tickers resolved; nothing to compute")
        stats.end_time = time.monotonic()
        return stats.to_log_extra()

    if verbose:
        log.info(
            "[B4.1] RUN HEADER tickers=%s start_date=%s end_date=%s heartbeat_every=%s deterministic=true",
            total_tickers,
            start_date.isoformat() if start_date else "none",
            end_date.isoformat() if end_date else "none",
            heartbeat_every,
        )

    for ticker_id, symbol in tickers:
        try:
            events = _fetch_structural_events(
                conn,
                ticker_id=ticker_id,
                start_date=start_date,
                end_date=end_date,
            )
            if not events:
                stats.missing_history += 1
                log.debug("[B4.1] Symbol %s (%s) missing structural events", symbol, ticker_id)

            snapshot_rows = _fetch_daily_regimes(
                conn,
                ticker_id=ticker_id,
                start_date=start_date,
                end_date=end_date,
            )
            if not snapshot_rows:
                stats.missing_history += 1
                log.debug("[B4.1] Symbol %s (%s) missing daily_snapshots", symbol, ticker_id)

            transitions = _fetch_regime_transitions(
                conn,
                ticker_id=ticker_id,
                start_date=start_date,
                end_date=end_date,
            )

            regimes_by_date = _regime_by_date(snapshot_rows)
            terminal_events = [ev for ev in events if ev.event_type in (TERMINAL_EVENT_SOS, TERMINAL_EVENT_SOW)]
            for terminal in terminal_events:
                prior_regime = regimes_by_date.get(terminal.event_date)
                if prior_regime is None:
                    stats.sequences_skipped += 1
                    log.info(
                        "[B4.1] Missing regime at terminal date; skipping ticker=%s terminal_date=%s",
                        ticker_id,
                        terminal.event_date.isoformat(),
                    )
                    continue
                eligible = ELIGIBLE_REGIMES.get(terminal.event_type, set())
                if prior_regime not in eligible:
                    stats.sequences_skipped += 1
                    log.debug(
                        "[B4.1] Regime mismatch; skipping ticker=%s terminal_date=%s terminal_event=%s prior_regime=%s",
                        ticker_id,
                        terminal.event_date.isoformat(),
                        terminal.event_type,
                        prior_regime,
                    )

            sequences = _derive_sequences_for_events(
                events=events,
                regimes_by_date=regimes_by_date,
                transitions=transitions,
            )

            for sequence in sequences:
                terminal_date = sequence.terminal_date
                if sequence.invalidated and sequence.invalidated_reason:
                    log.debug(
                        "[B4.1] Invalidation detected ticker=%s terminal_date=%s sequence_type=%s reason=%s",
                        ticker_id,
                        terminal_date.isoformat(),
                        sequence.sequence_type,
                        sequence.invalidated_reason,
                    )

                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.wyckoff_sequences (
                            ticker_id,
                            sequence_id,
                            start_date,
                            completion_date,
                            events_in_sequence
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (ticker_id, sequence_id, completion_date)
                        DO NOTHING
                        """,
                        (
                            ticker_id,
                            sequence.sequence_type,
                            sequence.start_date,
                            sequence.terminal_date,
                            Json(_sequence_payload(sequence), dumps=_json_dumps_strict),
                        ),
                    )
                    if cur.rowcount == 0:
                        conn.rollback()
                        stats.sequences_skipped += 1
                        log.debug(
                            "[B4.1] Duplicate skip ticker=%s terminal_date=%s sequence_type=%s",
                            ticker_id,
                            terminal_date.isoformat(),
                            sequence.sequence_type,
                        )
                        continue

                    event_rows = [
                        (
                            ticker_id,
                            sequence.sequence_type,
                            sequence.terminal_date,
                            ev.event_type,
                            ev.event_date,
                            ev.event_role,
                            ev.event_order,
                        )
                        for ev in sequence.events
                    ]
                    execute_values(
                        cur,
                        """
                        INSERT INTO public.wyckoff_sequence_events (
                            ticker_id,
                            sequence_id,
                            completion_date,
                            event_type,
                            event_date,
                            event_role,
                            event_order
                        )
                        VALUES %s
                        ON CONFLICT DO NOTHING
                        """,
                        event_rows,
                    )
                    conn.commit()

                    stats.sequences_written += 1
                    if sequence.invalidated:
                        stats.sequences_invalidated += 1

            stats.processed += 1

            if _should_emit_heartbeat(stats.processed, heartbeat_every):
                log.info(
                    "[B4.1] Heartbeat processed=%s total=%s sequences=%s invalidated=%s skipped=%s",
                    stats.processed,
                    stats.total_tickers,
                    stats.sequences_written,
                    stats.sequences_invalidated,
                    stats.sequences_skipped,
                )
        except Exception:
            stats.errors += 1
            conn.rollback()
            log.exception("[B4.1] Failed symbol %s (%s)", symbol, ticker_id)

    stats.end_time = time.monotonic()
    log.info("[B4.1] RUN SUMMARY %s", stats.to_log_extra())
    return stats.to_log_extra()
