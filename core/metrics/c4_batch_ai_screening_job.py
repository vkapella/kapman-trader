from __future__ import annotations

import argparse
import hashlib
import json
import json
import logging
import os
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

import psycopg2
from psycopg2.extras import execute_values

from core.ingestion.options.db import default_db_url
from core.providers.ai.invoke import invoke_planning_agent

logger = logging.getLogger("kapman.c4")

ALLOWED_PROVIDERS = {"anthropic", "openai"}

DEFAULT_BATCH_SIZE = 5
DEFAULT_BATCH_WAIT_SECONDS = 1.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 1.0

DEFAULT_MIN_OPEN_INTEREST = 500
DEFAULT_MIN_VOLUME = 100
DEFAULT_EXPIRATION_BUCKETS = ("short", "medium")
DEFAULT_MONEYNESS_BANDS = ("ATM", "slightly_OTM")


@dataclass
class C4RunStats:
    total_tickers: int
    processed: int = 0
    success: int = 0
    skipped: int = 0
    failed: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    def duration_sec(self) -> float:
        return self.end_time - self.start_time

    def to_log_extra(self) -> dict[str, Any]:
        return {
            "total_tickers": self.total_tickers,
            "processed": self.processed,
            "success": self.success,
            "skipped": self.skipped,
            "failed": self.failed,
            "duration_sec": self.duration_sec(),
        }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _log_event(log: logging.Logger, event: str, payload: dict[str, Any]) -> None:
    entry = {"event": event}
    entry.update(payload)
    log.info(_canonical_json(entry))


def _git_revision() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[2]
        sha_bytes = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL
        )
        return sha_bytes.decode().strip()
    except Exception:
        return "unknown"


def _resolve_model_version() -> str:
    override = os.getenv("KAPMAN_C4_MODEL_VERSION")
    if override:
        return override
    sha = _git_revision()
    return f"c4-batch-ai-screening@{sha}"


MODEL_VERSION = _resolve_model_version()


def partition_batches(items: Sequence[Any], batch_size: int) -> list[list[Any]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    return [list(items[i : i + batch_size]) for i in range(0, len(items), batch_size)]


def compute_backoff_seconds(*, attempt: int, base_seconds: float) -> float:
    if attempt <= 0:
        raise ValueError("attempt must be >= 1")
    if base_seconds < 0:
        raise ValueError("base_seconds must be >= 0")
    return base_seconds * (2 ** (attempt - 1))


def sort_tickers(tickers: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    normalized = [(str(tid), str(sym).upper()) for tid, sym in tickers]
    return sorted(normalized, key=lambda row: (row[1], row[0]))


def _normalize_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return value


def _summary_computed(summary: Any) -> bool:
    if not isinstance(summary, dict):
        return False
    for value in summary.values():
        if value is not None:
            return True
    return False


def _resolve_snapshot_time(conn, provided: Optional[datetime]) -> Optional[datetime]:
    if provided is not None:
        if provided.tzinfo is None:
            return provided.replace(tzinfo=timezone.utc)
        return provided
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(time) FROM daily_snapshots")
        row = cur.fetchone()
    if not row or row[0] is None:
        return None
    snapshot_time = row[0]
    if snapshot_time.tzinfo is None:
        snapshot_time = snapshot_time.replace(tzinfo=timezone.utc)
    return snapshot_time


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
    return sort_tickers(rows)


def _load_daily_snapshot(conn, *, ticker_id: str, snapshot_time: datetime) -> Optional[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                wyckoff_regime,
                wyckoff_regime_confidence,
                events_detected,
                technical_indicators_json,
                volatility_metrics_json,
                dealer_metrics_json,
                price_metrics_json
            FROM daily_snapshots
            WHERE time = %s AND ticker_id = %s
            """,
            (snapshot_time, ticker_id),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "wyckoff_regime": row[0],
        "wyckoff_regime_confidence": row[1],
        "events_detected": row[2],
        "technical_summary": _normalize_json_value(row[3]),
        "volatility_summary": _normalize_json_value(row[4]),
        "dealer_summary": _normalize_json_value(row[5]),
        "price_summary": _normalize_json_value(row[6]),
    }


def _coerce_events(events: Any) -> list[str]:
    if events is None:
        return []
    if isinstance(events, list):
        return [str(event) for event in events if event is not None]
    return [str(events)]


def _try_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _first_float(mapping: Any, keys: Sequence[str]) -> Optional[float]:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        if key not in mapping:
            continue
        candidate = _try_float(mapping.get(key))
        if candidate is not None:
            return candidate
    return None


def _resolve_spot_price(*, dealer_summary: Any, price_summary: Any) -> Optional[float]:
    spot = _first_float(dealer_summary, ("spot_price", "spot", "price", "close"))
    if spot is not None:
        return spot
    return _first_float(price_summary, ("close", "spot", "price", "last"))


def _normalize_recommendation_direction(value: Any) -> str:
    if value is None:
        return "NEUTRAL"
    text = str(value).strip().upper()
    if text == "BULLISH":
        return "LONG"
    if text == "BEARISH":
        return "SHORT"
    if text == "NEUTRAL":
        return "NEUTRAL"
    return "NEUTRAL"


def _normalize_strategy_class(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _normalize_recommendation_action(action: Any, direction: str, strategy_class: Optional[str]) -> str:
    if action is None:
        return "HOLD"
    text = str(action).strip().upper()
    if text == "ENTER":
        if strategy_class == "HEDGE_OVERLAY":
            return "HEDGE"
        if direction == "SHORT":
            return "SELL"
        if direction == "LONG":
            return "BUY"
        return "HOLD"
    if text in {"WAIT", "DEFER", "NO_TRADE"}:
        return "HOLD"
    return "HOLD"


def _normalize_option_strategy(strategy_class: Optional[str]) -> Optional[str]:
    if not strategy_class:
        return None
    if strategy_class in {"LONG_CALL", "LONG_PUT", "CSP"}:
        return strategy_class
    if strategy_class in {"CALL_DEBIT_SPREAD", "PUT_DEBIT_SPREAD"}:
        return "VERTICAL_SPREAD"
    return None


def _normalize_confidence(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        score = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    normalized = score / Decimal("100")
    if normalized < 0 or normalized > 1:
        return None
    return normalized.quantize(Decimal("0.001"))


def _normalize_option_strike(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.0001"))
    except (InvalidOperation, ValueError):
        return None


def _normalize_option_expiration(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            if "T" in text:
                return datetime.fromisoformat(text).date()
            return date.fromisoformat(text)
        except ValueError:
            return None
    return None


def _normalize_option_type(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in {"C", "CALL"}:
        return "C"
    if text in {"P", "PUT"}:
        return "P"
    return None


def _format_decimal(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _recommendation_identity_payload(
    *,
    symbol: str,
    snapshot_time: datetime,
    provider_key: str,
    ai_model: str,
    action: str,
    direction: str,
    strategy_class: Optional[str],
    option_expiration: Optional[date],
    option_strike: Optional[Decimal],
    option_type: Optional[str],
) -> dict[str, Any]:
    return {
        "symbol": symbol.upper(),
        "snapshot_time": snapshot_time.isoformat(),
        "provider": provider_key,
        "model": ai_model,
        "action": action,
        "direction": direction,
        "strategy_class": strategy_class,
        "option_expiration": option_expiration.isoformat() if option_expiration else None,
        "option_strike": _format_decimal(option_strike),
        "option_type": option_type,
    }


def _deterministic_recommendation_id(payload: dict[str, Any]) -> str:
    identity = _canonical_json(payload)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def _build_recommendation_row(
    *,
    ticker_id: str,
    symbol: str,
    snapshot_time: datetime,
    provider_key: str,
    ai_model: str,
    response: dict[str, Any],
) -> Optional[tuple]:
    metadata = response.get("snapshot_metadata") or {}
    ticker = metadata.get("ticker")
    if not isinstance(ticker, str) or ticker.upper() == "UNKNOWN":
        if os.getenv("AI_DUMP") == "1":
            log = logging.getLogger("kapman.ai.c4")
            log.info(
                "[AI_DUMP] "
                + json.dumps(
                    {
                        "event": "recommendation_dropped",
                        "reason": "unknown_ticker",
                        "symbol": symbol,
                        "primary_recommendation": response.get("primary_recommendation"),
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )
            log.warning(
                "[AI_DUMP] "
                + json.dumps(
                    {
                        "event": "ai_zero_recommendations",
                        "ticker": symbol,
                        "model": ai_model,
                        "reason": "unknown_ticker",
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )
        return None
    primary = response.get("primary_recommendation")
    if not isinstance(primary, dict):
        if os.getenv("AI_DUMP") == "1":
            log = logging.getLogger("kapman.ai.c4")
            log.info(
                "[AI_DUMP] "
                + json.dumps(
                    {
                        "event": "recommendation_dropped",
                        "reason": "missing_primary_recommendation",
                        "symbol": symbol,
                        "primary_recommendation": primary,
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )
            log.warning(
                "[AI_DUMP] "
                + json.dumps(
                    {
                        "event": "ai_zero_recommendations",
                        "ticker": symbol,
                        "model": ai_model,
                        "reason": "missing_primary_recommendation",
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )
        return None

    strategy_class = _normalize_strategy_class(primary.get("strategy_class"))
    direction = _normalize_recommendation_direction(primary.get("direction"))
    action = _normalize_recommendation_action(primary.get("action"), direction, strategy_class)
    confidence = _normalize_confidence(primary.get("confidence_score"))
    rationale = primary.get("rationale_summary")
    justification = rationale if isinstance(rationale, str) else (None if rationale is None else str(rationale))
    option_strike = _normalize_option_strike(primary.get("option_strike"))
    option_expiration = _normalize_option_expiration(primary.get("option_expiration"))
    option_type = _normalize_option_type(primary.get("option_type"))
    option_strategy = _normalize_option_strategy(strategy_class)

    identity_payload = _recommendation_identity_payload(
        symbol=symbol,
        snapshot_time=snapshot_time,
        provider_key=provider_key,
        ai_model=ai_model,
        action=action,
        direction=direction,
        strategy_class=strategy_class,
        option_expiration=option_expiration,
        option_strike=option_strike,
        option_type=option_type,
    )
    recommendation_id = _deterministic_recommendation_id(identity_payload)
    model_version = metadata.get("model_version") or MODEL_VERSION
    created_at = datetime.now(timezone.utc)

    return (
        recommendation_id,
        snapshot_time,
        ticker_id,
        snapshot_time.date(),
        direction,
        action,
        confidence,
        justification,
        None,
        None,
        None,
        None,
        option_strike,
        option_expiration,
        option_type,
        option_strategy,
        "active",
        model_version,
        created_at,
    )


def _persist_recommendations(
    conn,
    *,
    rows: Sequence[tuple],
    dry_run: bool,
    batch_size: int = 200,
) -> int:
    if dry_run or not rows:
        return 0

    insert_sql = """
        INSERT INTO recommendations (
            id,
            snapshot_time,
            ticker_id,
            recommendation_date,
            direction,
            action,
            confidence,
            justification,
            entry_price_target,
            stop_loss,
            profit_target,
            risk_reward_ratio,
            option_strike,
            option_expiration,
            option_type,
            option_strategy,
            status,
            model_version,
            created_at
        )
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """

    total = 0
    try:
        with conn.cursor() as cur:
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                execute_values(cur, insert_sql, batch, page_size=len(batch))
                total += cur.rowcount if cur.rowcount is not None else 0
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return total


def _log_error(log: logging.Logger, event: str, payload: dict[str, Any]) -> None:
    entry = {"event": event}
    entry.update(payload)
    log.error(_canonical_json(entry))


def _data_completeness_flags(
    *,
    technical_summary: Any,
    volatility_summary: Any,
    dealer_summary: Any,
) -> dict[str, str]:
    return {
        "technical_summary": "COMPUTED" if _summary_computed(technical_summary) else "NOT COMPUTED",
        "volatility_summary": "COMPUTED" if _summary_computed(volatility_summary) else "NOT COMPUTED",
        "dealer_summary": "COMPUTED" if _summary_computed(dealer_summary) else "NOT COMPUTED",
    }


def _build_authority_constraints() -> dict[str, Any]:
    return {
        "wyckoff_veto": False,
        "iv_forbids_long_premium": False,
        "dealer_timing_veto": False,
    }


def _build_instructions() -> dict[str, Any]:
    return {
        "objective": "produce ranked trade recommendations",
        "forbidden_actions": [
            "assume strike existence",
            "assume expiration existence",
            "claim executability",
        ],
    }


def _invocation_id(
    *,
    symbol: str,
    snapshot_time: datetime,
    provider_id: str,
    model_id: str,
) -> str:
    seed = f"{provider_id}:{model_id}:{symbol}:{snapshot_time.isoformat()}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return digest[:12]


def _extract_failure_reason(response: dict[str, Any]) -> Optional[str]:
    snapshot_metadata = response.get("snapshot_metadata") or {}
    if snapshot_metadata.get("ticker") != "UNKNOWN":
        return None
    missing = response.get("missing_data_declaration")
    if isinstance(missing, list):
        for entry in missing:
            if isinstance(entry, str) and entry.startswith("Normalization failure: "):
                return entry[len("Normalization failure: ") :]
    primary = response.get("primary_recommendation") or {}
    reason = primary.get("rationale_summary")
    if isinstance(reason, str) and reason:
        return reason
    return None


def _is_rate_limit(reason: str) -> bool:
    lowered = reason.lower()
    return "429" in lowered or "rate limit" in lowered or "ratelimit" in lowered or "too many requests" in lowered


def _classify_failure(reason: str) -> str:
    if "Unknown provider" in reason or "Missing model_id" in reason:
        return "config_error"
    if "Provider invocation failed" in reason:
        if _is_rate_limit(reason):
            return "rate_limit"
        return "transient"
    return "malformed"


def run_batch_ai_screening(
    conn,
    *,
    snapshot_time: Optional[datetime],
    ai_provider: str,
    ai_model: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    batch_wait_seconds: float = DEFAULT_BATCH_WAIT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
    dry_run: bool = False,
    log: Optional[logging.Logger] = None,
) -> list[dict[str, Any]]:
    log = log or logger

    provider_key = str(ai_provider or "").lower()
    if provider_key not in ALLOWED_PROVIDERS:
        raise ValueError(f"Unknown ai_provider: {ai_provider}")
    if not ai_model:
        raise ValueError("ai_model is required")
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    if batch_wait_seconds < 0:
        raise ValueError("batch_wait_seconds must be >= 0")
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    if backoff_base_seconds < 0:
        raise ValueError("backoff_base_seconds must be >= 0")

    snapshot_ts = _resolve_snapshot_time(conn, snapshot_time)
    if snapshot_ts is None:
        _log_event(log, "run_empty", {"reason": "no_snapshot_time"})
        return []

    tickers = _fetch_watchlist_tickers(conn)
    if not tickers:
        _log_event(log, "run_empty", {"reason": "no_watchlist_tickers"})
        return []

    stats = C4RunStats(total_tickers=len(tickers), start_time=time.monotonic())
    responses: list[dict[str, Any]] = []

    _log_event(
        log,
        "run_start",
        {
            "snapshot_time": snapshot_ts.isoformat(),
            "ai_provider": provider_key,
            "ai_model": ai_model,
            "batch_size": batch_size,
            "batch_wait_seconds": batch_wait_seconds,
            "max_retries": max_retries,
            "backoff_base_seconds": backoff_base_seconds,
            "dry_run": dry_run,
            "model_version": MODEL_VERSION,
            "total_tickers": stats.total_tickers,
        },
    )

    batches = partition_batches(tickers, batch_size)
    total_batches = len(batches)

    for batch_index, batch in enumerate(batches, start=1):
        batch_rows: list[tuple] = []
        _log_event(
            log,
            "batch_start",
            {"batch_id": batch_index, "batch_size": len(batch), "batch_index": batch_index, "batch_total": total_batches},
        )
        for ticker_id, symbol in batch:
            snapshot_row = _load_daily_snapshot(conn, ticker_id=ticker_id, snapshot_time=snapshot_ts)
            if snapshot_row is None:
                stats.skipped += 1
                _log_event(
                    log,
                    "ticker_skip",
                    {
                        "ticker": symbol,
                        "batch_id": batch_index,
                        "reason": "missing_daily_snapshot",
                    },
                )
                continue

            technical_summary = snapshot_row.get("technical_summary")
            volatility_summary = snapshot_row.get("volatility_summary")
            dealer_summary = snapshot_row.get("dealer_summary")
            price_summary = snapshot_row.get("price_summary")

            missing_fields = []
            if not isinstance(technical_summary, dict):
                missing_fields.append("technical_indicators_json")
            if not isinstance(volatility_summary, dict):
                missing_fields.append("volatility_metrics_json")
            if not isinstance(dealer_summary, dict):
                missing_fields.append("dealer_metrics_json")
            if missing_fields:
                stats.skipped += 1
                _log_event(
                    log,
                    "ticker_skip",
                    {
                        "ticker": symbol,
                        "batch_id": batch_index,
                        "reason": "missing_snapshot_fields",
                        "missing_fields": missing_fields,
                    },
                )
                continue

            spot_price = _resolve_spot_price(dealer_summary=dealer_summary, price_summary=price_summary)
            if spot_price is None:
                stats.skipped += 1
                _log_event(
                    log,
                    "ticker_skip",
                    {
                        "ticker": symbol,
                        "batch_id": batch_index,
                        "reason": "missing_spot_price",
                    },
                )
                continue

            data_flags = _data_completeness_flags(
                technical_summary=technical_summary,
                volatility_summary=volatility_summary,
                dealer_summary=dealer_summary,
            )

            snapshot_payload = {
                "symbol": symbol,
                "snapshot_time": snapshot_ts.isoformat(),
                "market_structure": {
                    "wyckoff_regime": snapshot_row.get("wyckoff_regime") or "UNKNOWN",
                    "wyckoff_events": _coerce_events(snapshot_row.get("events_detected")),
                    "regime_confidence": _try_float(snapshot_row.get("wyckoff_regime_confidence")) or 0.0,
                },
                "technical_summary": technical_summary,
                "volatility_summary": volatility_summary,
                "dealer_summary": dealer_summary,
                "data_completeness_flags": data_flags,
            }

            option_context = {
                "spot_price": spot_price,
                "expiration_buckets": list(DEFAULT_EXPIRATION_BUCKETS),
                "moneyness_bands": list(DEFAULT_MONEYNESS_BANDS),
                "liquidity_constraints": {
                    "min_open_interest": DEFAULT_MIN_OPEN_INTEREST,
                    "min_volume": DEFAULT_MIN_VOLUME,
                },
                "volatility_regime_summary": volatility_summary,
            }

            invocation_id = _invocation_id(
                symbol=symbol,
                snapshot_time=snapshot_ts,
                provider_id=provider_key,
                model_id=ai_model,
            )

            attempt = 0
            while True:
                attempt += 1
                _log_event(
                    log,
                    "ticker_invocation",
                    {
                        "invocation_id": invocation_id,
                        "ticker": symbol,
                        "batch_id": batch_index,
                        "ai_provider": provider_key,
                        "ai_model": ai_model,
                        "attempt": attempt,
                    },
                )

                response = invoke_planning_agent(
                    provider_id=provider_key,
                    model_id=ai_model,
                    snapshot_payload=snapshot_payload,
                    option_context=option_context,
                    authority_constraints=_build_authority_constraints(),
                    instructions=_build_instructions(),
                    prompt_version=MODEL_VERSION,
                    kapman_model_version=MODEL_VERSION,
                    debug=False,
                    dry_run=dry_run,
                )

                if not dry_run:
                    row = _build_recommendation_row(
                        ticker_id=ticker_id,
                        symbol=symbol,
                        snapshot_time=snapshot_ts,
                        provider_key=provider_key,
                        ai_model=ai_model,
                        response=response,
                    )
                    if row is not None:
                        batch_rows.append(row)

                reason = _extract_failure_reason(response)
                if reason:
                    classification = _classify_failure(reason)
                    if classification == "config_error":
                        raise ValueError(reason)
                    if classification in {"rate_limit", "transient"} and attempt <= max_retries:
                        backoff_seconds = compute_backoff_seconds(
                            attempt=attempt,
                            base_seconds=backoff_base_seconds,
                        )
                        _log_event(
                            log,
                            "ticker_retry",
                            {
                                "invocation_id": invocation_id,
                                "ticker": symbol,
                                "batch_id": batch_index,
                                "attempt": attempt,
                                "reason": reason,
                                "backoff_seconds": backoff_seconds,
                            },
                        )
                        if backoff_seconds > 0:
                            time.sleep(backoff_seconds)
                        continue

                record = {
                    "ticker": symbol,
                    "snapshot_time": snapshot_ts.isoformat(),
                    "ai_provider": provider_key,
                    "ai_model": ai_model,
                    "raw_normalized_response": response,
                }
                responses.append(record)
                stats.processed += 1

                if reason and _classify_failure(reason) in {"rate_limit", "transient"}:
                    stats.failed += 1
                    _log_event(
                        log,
                        "ticker_failure",
                        {
                            "invocation_id": invocation_id,
                            "ticker": symbol,
                            "batch_id": batch_index,
                            "reason": reason,
                        },
                    )
                else:
                    stats.success += 1
                    _log_event(
                        log,
                        "ticker_success",
                        {
                            "invocation_id": invocation_id,
                            "ticker": symbol,
                            "batch_id": batch_index,
                        },
                    )
                break

        if not dry_run:
            try:
                persisted = _persist_recommendations(conn, rows=batch_rows, dry_run=False)
            except Exception as exc:
                _log_error(
                    log,
                    "batch_persist_error",
                    {
                        "batch_id": batch_index,
                        "batch_index": batch_index,
                        "batch_total": total_batches,
                        "error": str(exc),
                    },
                )
                raise
            _log_event(
                log,
                "batch_persisted",
                {
                    "batch_id": batch_index,
                    "batch_index": batch_index,
                    "batch_total": total_batches,
                    "persisted_recommendations": persisted,
                },
            )

        _log_event(
            log,
            "batch_end",
            {"batch_id": batch_index, "batch_index": batch_index, "batch_total": total_batches},
        )

        if batch_wait_seconds > 0 and batch_index < total_batches:
            _log_event(
                log,
                "batch_wait",
                {
                    "batch_id": batch_index,
                    "wait_seconds": batch_wait_seconds,
                },
            )
            time.sleep(batch_wait_seconds)

    stats.end_time = time.monotonic()
    _log_event(
        log,
        "run_summary",
        {
            "snapshot_time": snapshot_ts.isoformat(),
            "ai_provider": provider_key,
            "ai_model": ai_model,
            **stats.to_log_extra(),
        },
    )
    return responses


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid datetime: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _configure_logging(level: str) -> logging.Logger:
    log = logging.getLogger("kapman.c4")
    log.handlers.clear()
    log.propagate = False

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.setLevel(level)

    log.addHandler(handler)
    log.setLevel(level)
    return log


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KapMan C4: Batch AI screening execution"
    )
    parser.add_argument("--db-url", type=str, default=None, help="Override DATABASE_URL")
    parser.add_argument("--snapshot-time", type=_parse_datetime, default=None, help="Snapshot time (ISO 8601)")
    parser.add_argument("--provider", choices=sorted(ALLOWED_PROVIDERS), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--batch-wait-seconds", type=float, default=DEFAULT_BATCH_WAIT_SECONDS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--backoff-base-seconds", type=float, default=DEFAULT_BACKOFF_BASE_SECONDS)
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log = _configure_logging(args.log_level)
    db_url = args.db_url or default_db_url()

    with psycopg2.connect(db_url) as conn:
        run_batch_ai_screening(
            conn,
            snapshot_time=args.snapshot_time,
            ai_provider=args.provider,
            ai_model=args.model,
            batch_size=int(args.batch_size),
            batch_wait_seconds=float(args.batch_wait_seconds),
            max_retries=int(args.max_retries),
            backoff_base_seconds=float(args.backoff_base_seconds),
            dry_run=bool(args.dry_run),
            log=log,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
