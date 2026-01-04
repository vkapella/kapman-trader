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

logger = logging.getLogger("kapman.b4")

ALLOWED_TRANSITIONS = {
    (REGIME_ACCUMULATION, REGIME_MARKUP),
    (REGIME_MARKUP, REGIME_DISTRIBUTION),
    (REGIME_DISTRIBUTION, REGIME_MARKDOWN),
    (REGIME_MARKDOWN, REGIME_ACCUMULATION),
}

NON_UNKNOWN_REGIMES = {
    REGIME_ACCUMULATION,
    REGIME_MARKUP,
    REGIME_DISTRIBUTION,
    REGIME_MARKDOWN,
}

CONTEXT_EVENT_TYPES = {"SOS", "SOW", "BC", "SPRING"}

SEQUENCE_MAX_DAYS = 30
SEQUENCE_PATTERNS = {
    "SEQ_ACCUM_BREAKOUT": ["SC", "AR", "SPRING", "SOS"],
    "SEQ_DISTRIBUTION_TOP": ["BC", "AR_TOP"],
    "SEQ_MARKDOWN_START": ["BC", "AR_TOP", "SOW"],
    "SEQ_RECOVERY": ["SOW", "SC"],
}

FAILED_ACCUM_SEQUENCE_ID = "SEQ_FAILED_ACCUM"
FAILED_ACCUM_PATTERN = ["SC", "AR", "SPRING"]


@dataclass(frozen=True)
class CanonicalEvent:
    event_date: date
    event_type: str
    event_order: int


@dataclass
class B4BatchStats:
    total_tickers: int
    processed: int = 0
    transitions_written: int = 0
    sequences_written: int = 0
    context_events_written: int = 0
    evidence_written: int = 0
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
            "transitions_written": self.transitions_written,
            "sequences_written": self.sequences_written,
            "context_events_written": self.context_events_written,
            "evidence_written": self.evidence_written,
            "missing_history": self.missing_history,
            "errors": self.errors,
            "duration_sec": self.duration(),
        }


def _json_dumps_strict(value: Any) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _normalize_regime(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = str(value).upper()
    if normalized in NON_UNKNOWN_REGIMES or normalized == REGIME_UNKNOWN:
        return normalized
    return None


def _normalize_event_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = str(value).upper().strip()
    return normalized or None


def _fetch_active_tickers(conn) -> list[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, UPPER(symbol)
            FROM tickers
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
            FROM watchlists w
            JOIN tickers t ON UPPER(t.symbol) = UPPER(w.symbol)
            WHERE w.active = TRUE
            ORDER BY UPPER(t.symbol), t.id::text
            """
        )
        rows = cur.fetchall()
    return [(str(tid), str(symbol)) for tid, symbol in rows]


def _fetch_tickers_for_symbols(conn, symbols: Iterable[str]) -> tuple[list[tuple[str, str]], list[str]]:
    normalized = sorted({str(sym).upper() for sym in symbols if str(sym).strip()})
    if not normalized:
        return [], []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT UPPER(symbol), id::text FROM tickers WHERE UPPER(symbol) = ANY(%s) ORDER BY UPPER(symbol)",
            (normalized,),
        )
        rows = cur.fetchall()
    found = {str(symbol): str(ticker_id) for symbol, ticker_id in rows}
    missing = [sym for sym in normalized if sym not in found]
    return [(ticker_id, symbol) for symbol, ticker_id in rows], missing


def _fetch_daily_regimes(
    conn,
    *,
    ticker_id: str,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[tuple[date, Optional[str]]]:
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
            SELECT time::date, wyckoff_regime
            FROM daily_snapshots
            WHERE ticker_id = %s AND {where_clause}
            ORDER BY time ASC
            """,
            params,
        )
        rows = cur.fetchall()
    return [(row[0], row[1]) for row in rows]


def _resolve_event_order_column(conn) -> Optional[str]:
    candidates = ["event_order", "event_rank", "sequence_index", "event_sequence"]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'wyckoff_context_events'
              AND column_name = ANY(%s)
            """,
            (candidates,),
        )
        rows = [row[0] for row in cur.fetchall()]
    for name in candidates:
        if name in rows:
            return name
    return None


def _fetch_canonical_events(
    conn,
    *,
    ticker_id: str,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[CanonicalEvent]:
    if start_date and end_date:
        where_clause = "event_date >= %s AND event_date <= %s"
        params = (ticker_id, start_date, end_date)
    elif start_date:
        where_clause = "event_date >= %s"
        params = (ticker_id, start_date)
    elif end_date:
        where_clause = "event_date <= %s"
        params = (ticker_id, end_date)
    else:
        where_clause = "TRUE"
        params = (ticker_id,)

    order_column = _resolve_event_order_column(conn)
    if order_column:
        select_order = f", {order_column}"
        order_clause = f"event_date ASC, {order_column} ASC, event_type ASC"
    else:
        select_order = ""
        order_clause = "event_date ASC, event_type ASC"

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT event_date, event_type{select_order}
            FROM public.wyckoff_context_events
            WHERE ticker_id = %s AND {where_clause}
            ORDER BY {order_clause}
            """,
            params,
        )
        rows = cur.fetchall()

    events: list[CanonicalEvent] = []
    for idx, row in enumerate(rows):
        event_date = row[0]
        event_type = _normalize_event_type(row[1])
        if not event_date or not event_type:
            continue
        if order_column:
            order_value = int(row[2]) if row[2] is not None else idx
        else:
            order_value = idx
        events.append(CanonicalEvent(event_date=event_date, event_type=event_type, event_order=order_value))
    return events


def _derive_regime_transitions(
    snapshot_rows: Sequence[tuple[date, Optional[str]]],
) -> list[dict[str, Any]]:
    transitions: list[dict[str, Any]] = []
    prior_regime: Optional[str] = None
    prior_duration = 0

    for snapshot_date, regime in snapshot_rows:
        normalized = _normalize_regime(regime)
        if normalized is None:
            prior_regime = None
            prior_duration = 0
            continue

        if prior_regime is None:
            prior_regime = normalized
            prior_duration = 1
            continue

        if normalized == prior_regime:
            prior_duration += 1
            continue

        if (
            prior_regime in NON_UNKNOWN_REGIMES
            and normalized in NON_UNKNOWN_REGIMES
            and (prior_regime, normalized) in ALLOWED_TRANSITIONS
            and prior_duration >= 5
        ):
            transitions.append(
                {
                    "date": snapshot_date,
                    "prior_regime": prior_regime,
                    "new_regime": normalized,
                    "duration_bars": prior_duration,
                }
            )

        prior_regime = normalized
        prior_duration = 1

    return transitions


def _find_sequence_completions(
    events: Sequence[CanonicalEvent],
    pattern: Sequence[str],
    max_days: int,
) -> list[list[CanonicalEvent]]:
    completions: list[list[CanonicalEvent]] = []
    idx = 0
    total = len(events)

    while idx < total:
        start_event = events[idx]
        if start_event.event_type != pattern[0]:
            idx += 1
            continue
        start_date = start_event.event_date
        current_idx = idx
        matched = [start_event]
        for next_event in pattern[1:]:
            found = False
            search_idx = current_idx + 1
            while search_idx < total:
                candidate = events[search_idx]
                if (candidate.event_date - start_date).days > max_days:
                    break
                if candidate.event_type == next_event:
                    matched.append(candidate)
                    current_idx = search_idx
                    found = True
                    break
                search_idx += 1
            if not found:
                matched = []
                break
        if matched:
            completions.append(matched)
            idx = current_idx + 1
        else:
            idx += 1

    return completions


def _find_failed_accum_sequences(events: Sequence[CanonicalEvent], max_days: int) -> list[list[CanonicalEvent]]:
    completions: list[list[CanonicalEvent]] = []
    idx = 0
    total = len(events)

    while idx < total:
        start_event = events[idx]
        if start_event.event_type != FAILED_ACCUM_PATTERN[0]:
            idx += 1
            continue
        start_date = start_event.event_date
        current_idx = idx
        matched = [start_event]
        for next_event in FAILED_ACCUM_PATTERN[1:]:
            found = False
            search_idx = current_idx + 1
            while search_idx < total:
                candidate = events[search_idx]
                if (candidate.event_date - start_date).days > max_days:
                    break
                if candidate.event_type == next_event:
                    matched.append(candidate)
                    current_idx = search_idx
                    found = True
                    break
                search_idx += 1
            if not found:
                matched = []
                break

        if not matched:
            idx += 1
            continue

        sos_found = False
        search_idx = idx + 1
        while search_idx < total:
            candidate = events[search_idx]
            if (candidate.event_date - start_date).days > max_days:
                break
            if candidate.event_type == "SOS":
                sos_found = True
                break
            search_idx += 1

        if sos_found:
            idx += 1
            continue

        completions.append(matched)
        idx = current_idx + 1

    return completions


def _events_payload(events: Sequence[CanonicalEvent]) -> list[dict[str, str]]:
    return [
        {"event": ev.event_type, "date": ev.event_date.isoformat()}
        for ev in events
    ]


def _derive_sequences(events: Sequence[CanonicalEvent]) -> list[dict[str, Any]]:
    sequences: list[dict[str, Any]] = []

    for sequence_id, pattern in SEQUENCE_PATTERNS.items():
        completions = _find_sequence_completions(events, pattern, SEQUENCE_MAX_DAYS)
        for matched in completions:
            sequences.append(
                {
                    "sequence_id": sequence_id,
                    "start_date": matched[0].event_date,
                    "completion_date": matched[-1].event_date,
                    "events": _events_payload(matched),
                }
            )

    failed = _find_failed_accum_sequences(events, SEQUENCE_MAX_DAYS)
    for matched in failed:
        sequences.append(
            {
                "sequence_id": FAILED_ACCUM_SEQUENCE_ID,
                "start_date": matched[0].event_date,
                "completion_date": matched[-1].event_date,
                "events": _events_payload(matched),
            }
        )

    sequences.sort(key=lambda item: (item["completion_date"], item["sequence_id"]))
    return sequences


def _build_prior_regime_map(snapshot_rows: Sequence[tuple[date, Optional[str]]]) -> dict[date, Optional[str]]:
    prior_by_date: dict[date, Optional[str]] = {}
    prior_regime: Optional[str] = None
    for snapshot_date, regime in snapshot_rows:
        prior_by_date[snapshot_date] = prior_regime
        prior_regime = _normalize_regime(regime)
    return prior_by_date


def _derive_context_events(
    events: Sequence[CanonicalEvent],
    snapshot_rows: Sequence[tuple[date, Optional[str]]],
) -> list[dict[str, Any]]:
    prior_by_date = _build_prior_regime_map(snapshot_rows)
    context_events: list[dict[str, Any]] = []

    for ev in events:
        if ev.event_type not in CONTEXT_EVENT_TYPES:
            continue
        prior_regime = prior_by_date.get(ev.event_date)
        if prior_regime not in NON_UNKNOWN_REGIMES:
            continue
        context_label = f"{ev.event_type}_after_{prior_regime}"
        context_events.append(
            {
                "event_date": ev.event_date,
                "event_type": ev.event_type,
                "prior_regime": prior_regime,
                "context_label": context_label,
            }
        )

    return context_events


def _build_snapshot_evidence(
    *,
    transitions: Sequence[dict[str, Any]],
    sequences: Sequence[dict[str, Any]],
    context_events: Sequence[dict[str, Any]],
) -> list[tuple[date, Json]]:
    evidence_by_date: dict[date, dict[str, Any]] = {}

    for transition in transitions:
        entry = evidence_by_date.setdefault(transition["date"], {})
        entry.setdefault("transitions", []).append(
            {
                "prior_regime": transition["prior_regime"],
                "new_regime": transition["new_regime"],
                "duration_bars": transition["duration_bars"],
            }
        )

    for sequence in sequences:
        entry = evidence_by_date.setdefault(sequence["completion_date"], {})
        entry.setdefault("sequences", []).append(
            {
                "sequence_id": sequence["sequence_id"],
                "start_date": sequence["start_date"].isoformat(),
                "completion_date": sequence["completion_date"].isoformat(),
                "events": sequence["events"],
            }
        )

    for context in context_events:
        entry = evidence_by_date.setdefault(context["event_date"], {})
        entry.setdefault("context_events", []).append(
            {
                "event_type": context["event_type"],
                "prior_regime": context["prior_regime"],
                "context_label": context["context_label"],
            }
        )

    evidence_rows: list[tuple[date, Json]] = []
    for evidence_date, payload in evidence_by_date.items():
        for key in ("transitions", "sequences", "context_events"):
            if key in payload:
                payload[key] = sorted(payload[key], key=lambda item: json.dumps(item, sort_keys=True))
        payload = {key: payload[key] for key in sorted(payload.keys())}
        evidence_rows.append((evidence_date, Json(payload, dumps=_json_dumps_strict)))

    evidence_rows.sort(key=lambda row: row[0])
    return evidence_rows


def _should_emit_heartbeat(processed: int, heartbeat_every: int) -> bool:
    return heartbeat_every > 0 and processed > 0 and processed % heartbeat_every == 0


def run_wyckoff_derived_job(
    conn,
    *,
    symbols: Optional[Iterable[str]] = None,
    use_watchlist: bool = False,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    heartbeat_every: int = 0,
    verbose: bool = False,
    include_evidence: bool = False,
    log: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    log = log or logger
    t0 = time.monotonic()

    if symbols is not None and use_watchlist:
        raise ValueError("symbols and use_watchlist are mutually exclusive")

    if symbols is not None:
        tickers, missing = _fetch_tickers_for_symbols(conn, symbols)
        if missing:
            log.warning("[B4] Symbols missing ticker_id: %s", ", ".join(missing))
    elif use_watchlist:
        tickers = _fetch_watchlist_tickers(conn)
    else:
        tickers = _fetch_active_tickers(conn)

    total_tickers = len(tickers)
    stats = B4BatchStats(total_tickers=total_tickers, start_time=t0)
    if total_tickers == 0:
        log.warning("[B4] No tickers resolved; nothing to compute")
        stats.end_time = time.monotonic()
        return stats.to_log_extra()

    if verbose:
        log.info(
            "[B4] RUN HEADER tickers=%s start_date=%s end_date=%s heartbeat_every=%s evidence=%s deterministic=true",
            total_tickers,
            start_date.isoformat() if start_date else "none",
            end_date.isoformat() if end_date else "none",
            heartbeat_every,
            include_evidence,
        )

    for ticker_id, symbol in tickers:
        try:
            snapshot_rows = _fetch_daily_regimes(
                conn,
                ticker_id=ticker_id,
                start_date=start_date,
                end_date=end_date,
            )
            if not snapshot_rows:
                stats.missing_history += 1
                log.debug("[B4] Symbol %s (%s) missing daily_snapshots; skipping transitions/context", symbol, ticker_id)

            events = _fetch_canonical_events(
                conn,
                ticker_id=ticker_id,
                start_date=start_date,
                end_date=end_date,
            )
            if not events:
                log.debug("[B4] Symbol %s (%s) missing canonical events; skipping sequences/context", symbol, ticker_id)

            transitions = _derive_regime_transitions(snapshot_rows) if snapshot_rows else []
            sequences = _derive_sequences(events) if events else []
            context_events = _derive_context_events(events, snapshot_rows) if events and snapshot_rows else []
            evidence_rows = (
                _build_snapshot_evidence(
                    transitions=transitions,
                    sequences=sequences,
                    context_events=context_events,
                )
                if include_evidence
                else []
            )

            with conn.cursor() as cur:
                if transitions:
                    execute_values(
                        cur,
                        """
                        INSERT INTO wyckoff_regime_transitions (
                            ticker_id,
                            date,
                            prior_regime,
                            new_regime,
                            duration_bars
                        )
                        VALUES %s
                        ON CONFLICT (ticker_id, date, new_regime)
                        DO NOTHING
                        """,
                        [
                            (
                                ticker_id,
                                row["date"],
                                row["prior_regime"],
                                row["new_regime"],
                                row["duration_bars"],
                            )
                            for row in transitions
                        ],
                    )

                if sequences:
                    execute_values(
                        cur,
                        """
                        INSERT INTO wyckoff_sequences (
                            ticker_id,
                            sequence_id,
                            start_date,
                            completion_date,
                            events_in_sequence
                        )
                        VALUES %s
                        ON CONFLICT (ticker_id, sequence_id, completion_date)
                        DO NOTHING
                        """,
                        [
                            (
                                ticker_id,
                                row["sequence_id"],
                                row["start_date"],
                                row["completion_date"],
                                Json(row["events"], dumps=_json_dumps_strict),
                            )
                            for row in sequences
                        ],
                    )

                if context_events:
                    execute_values(
                        cur,
                        """
                        INSERT INTO wyckoff_context_events (
                            ticker_id,
                            event_date,
                            event_type,
                            prior_regime,
                            context_label
                        )
                        VALUES %s
                        ON CONFLICT (ticker_id, event_date, event_type, prior_regime)
                        DO NOTHING
                        """,
                        [
                            (
                                ticker_id,
                                row["event_date"],
                                row["event_type"],
                                row["prior_regime"],
                                row["context_label"],
                            )
                            for row in context_events
                        ],
                    )

                if evidence_rows:
                    execute_values(
                        cur,
                        """
                        INSERT INTO wyckoff_snapshot_evidence (
                            ticker_id,
                            date,
                            evidence_json
                        )
                        VALUES %s
                        ON CONFLICT (ticker_id, date)
                        DO NOTHING
                        """,
                        [
                            (ticker_id, evidence_date, evidence_json)
                            for evidence_date, evidence_json in evidence_rows
                        ],
                    )

            conn.commit()
            stats.transitions_written += len(transitions)
            stats.sequences_written += len(sequences)
            stats.context_events_written += len(context_events)
            stats.evidence_written += len(evidence_rows)
            stats.processed += 1

            if _should_emit_heartbeat(stats.processed, heartbeat_every):
                log.info(
                    "[B4] Heartbeat processed=%s total=%s transitions=%s sequences=%s context=%s evidence=%s",
                    stats.processed,
                    stats.total_tickers,
                    stats.transitions_written,
                    stats.sequences_written,
                    stats.context_events_written,
                    stats.evidence_written,
                )
        except Exception:
            stats.errors += 1
            conn.rollback()
            log.exception("[B4] Failed symbol %s (%s)", symbol, ticker_id)

    stats.end_time = time.monotonic()
    log.info("[B4] RUN SUMMARY %s", stats.to_log_extra())
    return stats.to_log_extra()
