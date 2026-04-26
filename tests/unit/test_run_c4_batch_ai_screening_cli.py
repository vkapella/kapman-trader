from __future__ import annotations

import argparse
import importlib.util
import sys
import types
from pathlib import Path


def _load_c4_cli_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "run_c4_batch_ai_screening.py"
    spec = importlib.util.spec_from_file_location("run_c4_batch_ai_screening", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_c4_cli_debug_flag_passes_through(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _DummyConnection:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_payload_module = types.ModuleType("core.providers.ai.payload_normalization")
    fake_payload_module.normalize_payload = lambda value: value

    fake_ai_module = types.ModuleType("core.providers.ai")
    fake_ai_module.__path__ = []  # type: ignore[attr-defined]
    fake_ai_module.payload_normalization = fake_payload_module

    fake_providers_module = types.ModuleType("core.providers")
    fake_providers_module.__path__ = []  # type: ignore[attr-defined]
    fake_providers_module.ai = fake_ai_module

    fake_core_module = types.ModuleType("core")
    fake_core_module.__path__ = []  # type: ignore[attr-defined]
    fake_core_module.providers = fake_providers_module

    fake_metrics_module = types.ModuleType("core.metrics")
    fake_metrics_module.__path__ = []  # type: ignore[attr-defined]

    fake_c4_job = types.ModuleType("core.metrics.c4_batch_ai_screening_job")
    fake_parser = argparse.ArgumentParser()
    fake_parser.add_argument("--db-url")
    fake_parser.add_argument("--snapshot-time", default=None)
    fake_parser.add_argument("--provider", choices=["anthropic", "openai"], required=True)
    fake_parser.add_argument("--model", required=True)
    fake_parser.add_argument("--batch-size", type=int, default=5)
    fake_parser.add_argument("--batch-wait-seconds", type=float, default=1.0)
    fake_parser.add_argument("--max-retries", type=int, default=3)
    fake_parser.add_argument("--backoff-base-seconds", type=float, default=1.0)
    fake_parser.add_argument("--dry-run", action="store_true")
    fake_parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    fake_c4_job.build_parser = lambda: fake_parser
    fake_c4_job._configure_logging = lambda level: object()

    def _fake_run_batch_ai_screening(conn, **kwargs):
        captured.update(kwargs)
        return []

    fake_c4_job.run_batch_ai_screening = _fake_run_batch_ai_screening

    fake_ingestion_module = types.ModuleType("core.ingestion")
    fake_ingestion_module.__path__ = []  # type: ignore[attr-defined]

    fake_ingestion_options_module = types.ModuleType("core.ingestion.options")
    fake_ingestion_options_module.__path__ = []  # type: ignore[attr-defined]

    fake_db_module = types.ModuleType("core.ingestion.options.db")
    fake_db_module.default_db_url = lambda: "postgresql://default/db"

    fake_psycopg2 = types.SimpleNamespace(connect=lambda _db_url: _DummyConnection())

    monkeypatch.setitem(sys.modules, "core", fake_core_module)
    monkeypatch.setitem(sys.modules, "core.providers", fake_providers_module)
    monkeypatch.setitem(sys.modules, "core.providers.ai", fake_ai_module)
    monkeypatch.setitem(sys.modules, "core.providers.ai.payload_normalization", fake_payload_module)
    monkeypatch.setitem(sys.modules, "core.metrics", fake_metrics_module)
    monkeypatch.setitem(sys.modules, "core.metrics.c4_batch_ai_screening_job", fake_c4_job)
    monkeypatch.setitem(sys.modules, "core.ingestion", fake_ingestion_module)
    monkeypatch.setitem(sys.modules, "core.ingestion.options", fake_ingestion_options_module)
    monkeypatch.setitem(sys.modules, "core.ingestion.options.db", fake_db_module)
    monkeypatch.setitem(sys.modules, "psycopg2", fake_psycopg2)

    c4_cli = _load_c4_cli_module()

    exit_code = c4_cli.main(
        [
            "--db-url",
            "postgresql://example/db",
            "--provider",
            "openai",
            "--model",
            "test-model",
            "--debug",
            "--log-level",
            "INFO",
        ]
    )

    assert exit_code == 0
    assert captured["ai_debug"] is True
