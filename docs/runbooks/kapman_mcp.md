# kapman-mcp (Local Read-Only MCP Server)

## Start

```bash
python -m core.mcp.server
```

Transport is stdio only.

## Required Environment Variables

- `DATABASE_URL`

## LLM Client Connection

Connect an MCP-compatible client to the process command:

- command: `python`
- args: `-m core.mcp.server`
- transport: `stdio`

The server exposes exactly three tools:

- `get_wyckoff_proposal_context`
- `get_metrics`
- `screen_watchlist`

## Known Limitations

- Read-only database access only.
- No pipeline execution, ingestion, metrics jobs, or recommendation generation.
- No write tools.
- Wyckoff outputs are pipeline observations and always include `confirmation_status: "unconfirmed_pipeline_observation"`.
