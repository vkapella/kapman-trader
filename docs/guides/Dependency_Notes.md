# Dependency Notes

This document records the rationale for major third-party dependencies.
`requirements.txt` is treated as an executable lockfile and may be regenerated.

## API / Runtime
- fastapi, uvicorn — HTTP API layer
- pydantic v1 — pinned; v2 migration deferred

## Database
- sqlalchemy 2.x — core DB access
- psycopg2-binary — local/dev Postgres driver

## Async / Caching
- redis, aioredis — transitional; async paths still in use

## Analytics
- pandas, numpy — core analytics
- ta — local technical indicators

## External APIs
- python-binance, ccxt — market data sources

## Utilities
- python-dotenv — environment loading
- python-dateutil, pytz — time handling
