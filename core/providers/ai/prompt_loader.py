from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROMPT_DIRS = (Path("prompts"), Path("data/prompts"))
SCHEMA_DIR = Path("schemas")


def _resolve_path(name: str, roots: tuple[Path, ...]) -> Path:
    candidate = Path(name)
    if candidate.exists():
        return candidate
    for root in roots:
        path = root / name
        if path.exists():
            return path
    raise FileNotFoundError(f"Resource not found: {name}")


def load_prompt(name: str) -> str:
    path = _resolve_path(name, PROMPT_DIRS)
    return path.read_text(encoding="utf-8")


def load_schema(name: str) -> dict[str, Any]:
    path = _resolve_path(name, (SCHEMA_DIR,))
    return json.loads(path.read_text(encoding="utf-8"))
