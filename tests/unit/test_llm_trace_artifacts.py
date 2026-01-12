import importlib.util
import json
import sys
from pathlib import Path


def _load_trace_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "run_c4_batch_ai_screening.py"
    spec = importlib.util.spec_from_file_location("run_c4_batch_ai_screening", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_trace_off_creates_no_artifacts(tmp_path: Path) -> None:
    module = _load_trace_module()
    config = module.LLMTraceConfig(mode="off", trace_dir=tmp_path, run_id="run-off")
    writer = module.LLMTraceWriter(config)

    writer.write_prompt("AAPL", "openai", "prompt")
    writer.write_payload_raw("AAPL", "openai", {"b": 2, "a": 1})
    writer.write_payload_normalized("AAPL", "openai", {"b": 2, "a": 1})
    writer.write_raw_response("AAPL", "openai", {"ok": True})
    writer.write_extracted_text("AAPL", "openai", "extracted")
    writer.write_parsed_recommendation("AAPL", "openai", {"rec": True})
    writer.write_persistence_payload("AAPL", "openai", {"persist": True})

    assert list(tmp_path.iterdir()) == []


def test_trace_summary_artifacts(tmp_path: Path) -> None:
    module = _load_trace_module()
    config = module.LLMTraceConfig(mode="summary", trace_dir=tmp_path, run_id="run-summary")
    writer = module.LLMTraceWriter(config)

    writer.write_prompt("AAPL", "openai", "prompt")
    writer.write_payload_raw("AAPL", "openai", {"b": 2, "a": 1})
    writer.write_payload_normalized("AAPL", "openai", {"b": 2, "a": 1})
    writer.write_raw_response("AAPL", "openai", {"ok": True})
    writer.write_extracted_text("AAPL", "openai", "extracted")
    writer.write_parsed_recommendation("AAPL", "openai", {"rec": True})
    writer.write_persistence_payload("AAPL", "openai", {"persist": True})

    target_dir = tmp_path / "run-summary" / "AAPL"
    artifacts = {path.name for path in target_dir.iterdir()}
    assert artifacts == {
        "01_openai_prompt.md",
        "02_openai_payload_raw.json",
        "02b_openai_payload_normalized.json",
        "03_openai_raw_response.json",
        "05_openai_parsed_recommendation.json",
    }


def test_trace_full_artifacts(tmp_path: Path) -> None:
    module = _load_trace_module()
    config = module.LLMTraceConfig(mode="full", trace_dir=tmp_path, run_id="run-full")
    writer = module.LLMTraceWriter(config)

    writer.write_prompt("AAPL", "openai", "prompt")
    writer.write_payload_raw("AAPL", "openai", {"b": 2, "a": 1})
    writer.write_payload_normalized("AAPL", "openai", {"b": 2, "a": 1})
    writer.write_raw_response("AAPL", "openai", {"ok": True})
    writer.write_extracted_text("AAPL", "openai", "extracted")
    writer.write_parsed_recommendation("AAPL", "openai", {"rec": True})
    writer.write_persistence_payload("AAPL", "openai", {"persist": True})

    target_dir = tmp_path / "run-full" / "AAPL"
    artifacts = {path.name for path in target_dir.iterdir()}
    assert artifacts == {
        "01_openai_prompt.md",
        "02_openai_payload_raw.json",
        "02b_openai_payload_normalized.json",
        "03_openai_raw_response.json",
        "04_openai_extracted_text.txt",
        "05_openai_parsed_recommendation.json",
        "06_openai_persistence_payload.json",
    }


def test_provider_prefix_and_isolation(tmp_path: Path) -> None:
    module = _load_trace_module()
    config = module.LLMTraceConfig(mode="summary", trace_dir=tmp_path, run_id="run-providers")
    writer = module.LLMTraceWriter(config)

    writer.write_prompt("AAPL", "openai", "openai prompt")
    writer.write_prompt("AAPL", "anthropic", "anthropic prompt")

    target_dir = tmp_path / "run-providers" / "AAPL"
    openai_path = target_dir / "01_openai_prompt.md"
    anthropic_path = target_dir / "01_anthropic_prompt.md"

    assert openai_path.exists()
    assert anthropic_path.exists()
    assert openai_path.read_text(encoding="utf-8") == "openai prompt"
    assert anthropic_path.read_text(encoding="utf-8") == "anthropic prompt"


def test_pretty_printed_json(tmp_path: Path) -> None:
    module = _load_trace_module()
    config = module.LLMTraceConfig(mode="summary", trace_dir=tmp_path, run_id="run-json")
    writer = module.LLMTraceWriter(config)

    payload = {"b": 2, "a": 1}
    writer.write_payload_raw("AAPL", "openai", payload)

    target_path = tmp_path / "run-json" / "AAPL" / "02_openai_payload_raw.json"
    expected = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    assert target_path.read_text(encoding="utf-8") == expected


def test_trace_io_failure_is_swallowed(tmp_path: Path) -> None:
    module = _load_trace_module()
    trace_dir = tmp_path / "trace-root"
    trace_dir.write_text("not a dir", encoding="utf-8")
    config = module.LLMTraceConfig(mode="summary", trace_dir=trace_dir, run_id="run-fail")
    writer = module.LLMTraceWriter(config)

    writer.write_prompt("AAPL", "openai", "prompt")
    writer.write_payload_raw("AAPL", "openai", {"ok": True})
