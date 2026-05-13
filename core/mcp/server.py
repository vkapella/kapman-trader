from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.mcp.tools.metrics import get_metrics
from core.mcp.tools.screen_watchlist import screen_watchlist
from core.mcp.tools.wyckoff_proposal import get_wyckoff_proposal_context


TOOLS: dict[str, Any] = {
    "get_wyckoff_proposal_context": get_wyckoff_proposal_context,
    "get_metrics": get_metrics,
    "screen_watchlist": screen_watchlist,
}


def _tool_descriptors() -> list[dict[str, Any]]:
    return [
        {
            "name": "get_wyckoff_proposal_context",
            "description": "Build Wyckoff proposal context from persisted rows",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "as_of_date": {"type": ["string", "null"]},
                    "lookback_days": {"type": "integer", "default": 90},
                },
                "required": ["symbol"],
            },
        },
        {
            "name": "get_metrics",
            "description": "Return normalized metrics from latest eligible snapshot",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "as_of_date": {"type": ["string", "null"]},
                    "include": {"type": ["array", "null"], "items": {"type": "string"}},
                    "metric_keys": {"type": ["array", "null"], "items": {"type": "string"}},
                },
                "required": ["symbol"],
            },
        },
        {
            "name": "screen_watchlist",
            "description": "Filter and rank persisted watchlist symbols",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "as_of_date": {"type": ["string", "null"]},
                    "filters": {"type": ["object", "null"]},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        },
    ]


def _write_message(payload: dict[str, Any], mode: Literal["mcp", "newline"]) -> None:
    body = json.dumps(payload, default=str)
    if mode == "newline":
        sys.stdout.write(body + "\n")
        sys.stdout.flush()
        return

    encoded = body.encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def _read_message() -> Optional[tuple[dict[str, Any], Literal["mcp", "newline"]]]:
    first_line = sys.stdin.buffer.readline()
    if not first_line:
        return None

    stripped = first_line.strip()
    if stripped.startswith(b"{"):
        return json.loads(stripped.decode("utf-8")), "newline"

    headers: dict[str, str] = {}
    line = first_line
    while line and line not in (b"\r\n", b"\n"):
        name, _, value = line.decode("ascii").partition(":")
        headers[name.lower()] = value.strip()
        line = sys.stdin.buffer.readline()

    content_length = int(headers.get("content-length", "0"))
    if content_length <= 0:
        raise ValueError("missing Content-Length header")
    body = sys.stdin.buffer.read(content_length)
    return json.loads(body.decode("utf-8")), "mcp"


def _reply(id_value: Any, mode: Literal["mcp", "newline"], result: Any = None, error: str | None = None) -> None:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": id_value}
    if error is not None:
        payload["error"] = {"code": -32000, "message": error}
    else:
        payload["result"] = result
    _write_message(payload, mode)


def serve_stdio() -> None:
    while True:
        req: dict[str, Any] = {}
        mode: Literal["mcp", "newline"] = "mcp"
        try:
            read = _read_message()
            if read is None:
                return
            req, mode = read
            method = req.get("method")
            req_id = req.get("id")
            params = req.get("params") or {}
            if method == "initialize":
                _reply(
                    req_id,
                    mode,
                    {
                        "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "kapman-mcp", "version": "0.1.0"},
                    },
                )
            elif method == "notifications/initialized":
                continue
            elif method == "ping":
                _reply(req_id, mode, {})
            elif method == "tools/list":
                _reply(req_id, mode, {"tools": _tool_descriptors()})
            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments") or {}
                if name not in TOOLS:
                    raise ValueError(f"unknown tool: {name}")
                result = TOOLS[name](**arguments)
                _reply(
                    req_id,
                    mode,
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, default=str, indent=2, sort_keys=True),
                            }
                        ]
                    },
                )
            else:
                if req_id is not None:
                    _reply(req_id, mode, error=f"unsupported method: {method}")
        except Exception as exc:  # noqa: BLE001
            _reply(req.get("id") if isinstance(req, dict) else None, mode, error=str(exc))


if __name__ == "__main__":
    serve_stdio()
