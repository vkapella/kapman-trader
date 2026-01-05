from __future__ import annotations

import argparse
import json
import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

_SUMMARY_MODES = {"summary", "full"}
_FULL_MODES = {"full"}
_PERSISTENCE_COLUMNS = [
    "id",
    "snapshot_time",
    "ticker_id",
    "recommendation_date",
    "direction",
    "action",
    "confidence",
    "justification",
    "entry_price_target",
    "stop_loss",
    "profit_target",
    "risk_reward_ratio",
    "option_strike",
    "option_expiration",
    "option_type",
    "option_strategy",
    "status",
    "model_version",
    "created_at",
]


@dataclass(frozen=True)
class LLMTraceConfig:
    mode: str
    trace_dir: Path
    run_id: str

    @property
    def enabled(self) -> bool:
        return self.mode in _SUMMARY_MODES


@dataclass(frozen=True)
class LLMTraceContext:
    symbol: str
    provider_id: str


class LLMTraceWriter:
    def __init__(self, config: LLMTraceConfig) -> None:
        self._config = config
        self._stack: list[LLMTraceContext] = []

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def push_context(self, symbol: str, provider_id: str) -> None:
        self._stack.append(
            LLMTraceContext(
                symbol=self._normalize_symbol(symbol),
                provider_id=self._normalize_provider(provider_id),
            )
        )

    def pop_context(self) -> None:
        if self._stack:
            self._stack.pop()

    def current_context(self) -> Optional[LLMTraceContext]:
        return self._stack[-1] if self._stack else None

    def write_prompt(self, symbol: str, provider_id: str, prompt_text: str) -> None:
        self._write_text(symbol, provider_id, "01", "prompt.md", prompt_text, _SUMMARY_MODES)

    def write_payload(self, symbol: str, provider_id: str, payload: Any) -> None:
        self._write_json(symbol, provider_id, "02", "payload.json", payload, _SUMMARY_MODES)

    def write_raw_response(self, symbol: str, provider_id: str, raw_response: Any) -> None:
        if isinstance(raw_response, (bytes, bytearray)):
            raw_response = raw_response.decode("utf-8", errors="replace")
        if isinstance(raw_response, str):
            try:
                raw_response = json.loads(raw_response)
            except Exception:
                pass
        self._write_json(symbol, provider_id, "03", "raw_response.json", raw_response, _SUMMARY_MODES)

    def write_extracted_text(self, symbol: str, provider_id: str, text: str) -> None:
        self._write_text(symbol, provider_id, "04", "extracted_text.txt", text, _FULL_MODES)

    def write_parsed_recommendation(self, symbol: str, provider_id: str, recommendation: Any) -> None:
        self._write_json(
            symbol,
            provider_id,
            "05",
            "parsed_recommendation.json",
            recommendation,
            _SUMMARY_MODES,
        )

    def write_persistence_payload(self, symbol: str, provider_id: str, payload: Any) -> None:
        self._write_json(
            symbol,
            provider_id,
            "06",
            "persistence_payload.json",
            payload,
            _FULL_MODES,
        )

    def _write_text(
        self,
        symbol: str,
        provider_id: str,
        order: str,
        name: str,
        text: str,
        modes: set[str],
    ) -> None:
        if not self._config.mode or self._config.mode not in modes:
            return
        if text is None:
            return
        path = self._artifact_path(symbol, provider_id, order, name)
        self._write_file(path, str(text))

    def _write_json(
        self,
        symbol: str,
        provider_id: str,
        order: str,
        name: str,
        payload: Any,
        modes: set[str],
    ) -> None:
        if not self._config.mode or self._config.mode not in modes:
            return
        path = self._artifact_path(symbol, provider_id, order, name)
        try:
            rendered = json.dumps(
                payload,
                sort_keys=True,
                indent=2,
                ensure_ascii=True,
                default=self._json_default,
            )
        except Exception:
            return
        self._write_file(path, f"{rendered}\n")

    def _write_file(self, path: Path, content: str) -> None:
        try:
            if path.exists():
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except Exception:
            return

    def _artifact_path(self, symbol: str, provider_id: str, order: str, name: str) -> Path:
        trace_dir = self._config.trace_dir
        run_id = self._config.run_id
        symbol_segment = self._normalize_symbol(symbol)
        provider_segment = self._normalize_provider(provider_id)
        filename = f"{order}_{provider_segment}_{name}"
        return trace_dir / run_id / symbol_segment / filename

    def _normalize_symbol(self, symbol: str) -> str:
        text = str(symbol).strip() if symbol is not None else "UNKNOWN"
        normalized = text.upper() if text else "UNKNOWN"
        return self._safe_segment(normalized)

    def _normalize_provider(self, provider_id: str) -> str:
        text = str(provider_id).strip().lower() if provider_id is not None else "unknown"
        normalized = text if text else "unknown"
        return self._safe_segment(normalized)

    def _safe_segment(self, value: str) -> str:
        segment = value.replace(os.sep, "_")
        if os.altsep:
            segment = segment.replace(os.altsep, "_")
        return segment

    def _json_default(self, value: Any) -> str:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        return str(value)


class TraceHooks:
    def __init__(self, writer: Optional[LLMTraceWriter]) -> None:
        self._writer = writer
        self._originals: list[tuple[object, str, Callable[..., Any]]] = []
        self._c4_job = None
        self._ai_invoke = None
        self._response_parser = None

    def __enter__(self) -> "TraceHooks":
        if not self._writer or not self._writer.enabled:
            return self
        import core.metrics.c4_batch_ai_screening_job as c4_job
        import core.providers.ai.invoke as ai_invoke
        import core.providers.ai.response_parser as response_parser

        self._c4_job = c4_job
        self._ai_invoke = ai_invoke
        self._response_parser = response_parser

        wrapped_invoke = self._wrap_invoke_planning_agent(ai_invoke.invoke_planning_agent)
        self._patch(ai_invoke, "invoke_planning_agent", wrapped_invoke)
        self._patch(c4_job, "invoke_planning_agent", wrapped_invoke)
        self._patch(ai_invoke, "build_prompt", self._wrap_build_prompt(ai_invoke.build_prompt))
        self._patch(
            ai_invoke,
            "_canonical_request_payload",
            self._wrap_request_payload(ai_invoke._canonical_request_payload),
        )
        self._patch(
            ai_invoke,
            "normalize_agent_response",
            self._wrap_normalize_agent_response(ai_invoke.normalize_agent_response),
        )
        self._patch(
            response_parser,
            "extract_output_text",
            self._wrap_extract_output_text(response_parser.extract_output_text),
        )
        self._patch(
            c4_job,
            "_build_recommendation_row",
            self._wrap_build_recommendation_row(c4_job._build_recommendation_row),
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for module, name, original in reversed(self._originals):
            setattr(module, name, original)

    def _patch(self, module: object, name: str, replacement: Callable[..., Any]) -> None:
        original = getattr(module, name)
        self._originals.append((module, name, original))
        setattr(module, name, replacement)

    def _wrap_invoke_planning_agent(self, original: Callable[..., Any]) -> Callable[..., Any]:
        writer = self._writer

        def wrapper(
            *,
            provider_id: str,
            model_id: str,
            snapshot_payload: dict,
            option_context: dict,
            authority_constraints: dict,
            instructions: dict,
            prompt_version: str,
            kapman_model_version: str,
            debug: bool = False,
            dry_run: bool = False,
        ) -> dict:
            symbol = _symbol_from_payload(snapshot_payload)
            provider_key = str(provider_id).lower() if provider_id is not None else "unknown"
            if writer:
                writer.push_context(symbol, provider_key)
            try:
                return original(
                    provider_id=provider_id,
                    model_id=model_id,
                    snapshot_payload=snapshot_payload,
                    option_context=option_context,
                    authority_constraints=authority_constraints,
                    instructions=instructions,
                    prompt_version=prompt_version,
                    kapman_model_version=kapman_model_version,
                    debug=debug,
                    dry_run=dry_run,
                )
            finally:
                if writer:
                    writer.pop_context()

        return wrapper

    def _wrap_build_prompt(self, original: Callable[..., Any]) -> Callable[..., Any]:
        writer = self._writer

        def wrapper(
            *,
            snapshot_payload: dict,
            option_context: dict,
            authority_constraints: dict,
            instructions: dict,
            prompt_version: str,
        ) -> str:
            prompt = original(
                snapshot_payload=snapshot_payload,
                option_context=option_context,
                authority_constraints=authority_constraints,
                instructions=instructions,
                prompt_version=prompt_version,
            )
            if writer:
                context = writer.current_context()
                if context:
                    writer.write_prompt(context.symbol, context.provider_id, prompt)
            return prompt

        return wrapper

    def _wrap_request_payload(self, original: Callable[..., Any]) -> Callable[..., Any]:
        writer = self._writer

        def wrapper(
            *,
            snapshot_payload: dict,
            option_context: dict,
            authority_constraints: dict,
            instructions: dict,
            prompt_version: str,
        ) -> dict:
            payload = original(
                snapshot_payload=snapshot_payload,
                option_context=option_context,
                authority_constraints=authority_constraints,
                instructions=instructions,
                prompt_version=prompt_version,
            )
            if writer:
                context = writer.current_context()
                if context:
                    writer.write_payload(context.symbol, context.provider_id, payload)
            return payload

        return wrapper

    def _wrap_normalize_agent_response(self, original: Callable[..., Any]) -> Callable[..., Any]:
        writer = self._writer

        def wrapper(
            *,
            raw_response: Any,
            provider_id: str,
            model_id: str,
            prompt_version: str,
            kapman_model_version: str,
        ) -> dict:
            symbol = "UNKNOWN"
            provider_key = str(provider_id).lower() if provider_id is not None else "unknown"
            if writer:
                context = writer.current_context()
                if context:
                    symbol = context.symbol
                writer.write_raw_response(symbol, provider_key, raw_response)
            normalized = original(
                raw_response=raw_response,
                provider_id=provider_id,
                model_id=model_id,
                prompt_version=prompt_version,
                kapman_model_version=kapman_model_version,
            )
            if writer:
                context = writer.current_context()
                if context:
                    symbol = context.symbol
                writer.write_parsed_recommendation(symbol, provider_key, normalized)
            return normalized

        return wrapper

    def _wrap_extract_output_text(self, original: Callable[..., Any]) -> Callable[..., Any]:
        writer = self._writer

        def wrapper(response: dict) -> list[str]:
            texts = original(response)
            if writer and texts:
                context = writer.current_context()
                if context:
                    writer.write_extracted_text(context.symbol, context.provider_id, texts[0])
            return texts

        return wrapper

    def _wrap_build_recommendation_row(self, original: Callable[..., Any]) -> Callable[..., Any]:
        writer = self._writer

        def wrapper(
            *,
            ticker_id: str,
            symbol: str,
            snapshot_time: datetime,
            provider_key: str,
            ai_model: str,
            response: dict[str, Any],
        ) -> Optional[tuple]:
            row = original(
                ticker_id=ticker_id,
                symbol=symbol,
                snapshot_time=snapshot_time,
                provider_key=provider_key,
                ai_model=ai_model,
                response=response,
            )
            if writer and row is not None:
                payload = {key: value for key, value in zip(_PERSISTENCE_COLUMNS, row)}
                writer.write_persistence_payload(symbol, provider_key, payload)
            return row

        return wrapper


def _symbol_from_payload(snapshot_payload: dict) -> str:
    symbol = None
    if isinstance(snapshot_payload, dict):
        symbol = snapshot_payload.get("symbol") or snapshot_payload.get("ticker")
    text = str(symbol).strip() if symbol is not None else "UNKNOWN"
    return text.upper() if text else "UNKNOWN"


def build_parser() -> argparse.ArgumentParser:
    import core.metrics.c4_batch_ai_screening_job as c4_job

    parser = c4_job.build_parser()
    parser.add_argument("--symbols", default=None, help="Comma-delimited list of symbols")
    parser.add_argument("--llm-trace", choices=["off", "summary", "full"], default="off")
    parser.add_argument("--llm-trace-dir", default="data/llm_traces/")
    return parser


def _parse_symbols(value: Optional[str]) -> list[str]:
    if value is None:
        return []
    parts = [part.strip().upper() for part in value.split(",")]
    return [part for part in parts if part]


def _build_trace_writer(mode: str, trace_dir: str) -> Optional[LLMTraceWriter]:
    if mode not in _SUMMARY_MODES:
        return None
    run_id = uuid.uuid4().hex
    config = LLMTraceConfig(mode=mode, trace_dir=Path(trace_dir), run_id=run_id)
    return LLMTraceWriter(config)


def main(argv: Optional[Sequence[str]] = None) -> int:
    import psycopg2

    import core.metrics.c4_batch_ai_screening_job as c4_job
    from core.ingestion.options.db import default_db_url

    parser = build_parser()
    args = parser.parse_args(argv)

    log = c4_job._configure_logging(args.log_level)
    db_url = args.db_url or default_db_url()
    writer = _build_trace_writer(args.llm_trace, args.llm_trace_dir)
    symbols = _parse_symbols(args.symbols)
    symbols_filter = symbols if args.symbols is not None else None

    with psycopg2.connect(db_url) as conn:
        with TraceHooks(writer):
            c4_job.run_batch_ai_screening(
                conn,
                snapshot_time=args.snapshot_time,
                ai_provider=args.provider,
                ai_model=args.model,
                symbols=symbols_filter,
                batch_size=int(args.batch_size),
                batch_wait_seconds=float(args.batch_wait_seconds),
                max_retries=int(args.max_retries),
                backoff_base_seconds=float(args.backoff_base_seconds),
                dry_run=bool(args.dry_run),
                log=log,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
