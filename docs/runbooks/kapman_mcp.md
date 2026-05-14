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

The server exposes five read-only tools:

- `get_wyckoff_proposal_context`
- `get_metrics`
- `get_metrics_batch`
- `screen_symbols`
- `screen_watchlist`

## Tool Surface

### `get_wyckoff_proposal_context(symbol, as_of_date)`

Returns Wyckoff proposal context for one symbol from persisted pipeline rows.

### `get_metrics(symbol, as_of_date)`

Returns normalized persisted metrics for one symbol from the latest eligible snapshot on or before `as_of_date`.

### `get_metrics_batch(symbols, as_of_date)`

Required inputs:

- `symbols`: list of symbols, maximum 30
- `as_of_date`: `YYYY-MM-DD`; required and must be supplied explicitly by the caller

Returns the same per-symbol field schema as `get_metrics`, keyed by symbol:

```json
{
  "results": {
    "AMD": {
      "symbol": "AMD",
      "ticker_id": "...",
      "effective_as_of_date": "2026-05-13",
      "latest_eligible_snapshot_date": "2026-05-12",
      "metrics": {},
      "data_quality_flags": {}
    }
  },
  "missing_symbols": [],
  "as_of_date": "2026-05-13"
}
```

Symbols with no ticker or no eligible snapshot are omitted from `results` and listed in `missing_symbols`.

### `screen_symbols(symbols, as_of_date)`

Required inputs:

- `symbols`: list of symbols, maximum 30
- `as_of_date`: `YYYY-MM-DD`; required and must be supplied explicitly by the caller

Runs the same ranking logic as `screen_watchlist`, but only for the supplied symbols. Use this when the operator already has a ticker list and needs a completeness-preserving screen for that list.

Response mirrors `screen_watchlist` and appends `missing_symbols`:

```json
{
  "effective_as_of_date": "2026-05-13",
  "count": 2,
  "results": [],
  "missing_symbols": []
}
```

Symbols with no ticker or no eligible snapshot are omitted from `results` and listed in `missing_symbols`.

### `screen_watchlist(as_of_date, filters, limit)`

Screens the stored active watchlist and returns the first `limit` ranked rows. Default `limit` is `50`. Use this for broad daily watchlist screening, not for checking completeness of a caller-supplied ticker list.

## Batch Cap

`get_metrics_batch` and `screen_symbols` accept at most 30 symbols per call. The cap is enforced server-side before any database lookup or partial result construction.

Both batch tools require `as_of_date`; callers should pass the active session date explicitly.

If the cap is exceeded, the tool returns:

```json
{
  "error": "BATCH_CAP_EXCEEDED",
  "max": 30,
  "received": 31
}
```

Callers are responsible for chunking larger input lists into batches of 30 or fewer symbols.

## When To Use Each Tool

- Use `get_metrics` for exact metric lookup on one known symbol.
- Use `get_metrics_batch` for exact metric lookup across an operator-supplied symbol list.
- Use `screen_symbols` to rank an operator-supplied symbol list while preserving missing-symbol diagnostics.
- Use `screen_watchlist` for ranked screening across the persisted active watchlist.
- Do not use `screen_watchlist(limit=...)` as a completeness query for an arbitrary symbol list; `limit` can hide lower-ranked symbols.

## Known Limitations

- Read-only database access only.
- No pipeline execution, ingestion, metrics jobs, or recommendation generation.
- No write tools.
- Wyckoff outputs are pipeline observations and always include `confirmation_status: "unconfirmed_pipeline_observation"`.
- Batch tools do not paginate. Inputs above 30 symbols must be chunked by the caller.
