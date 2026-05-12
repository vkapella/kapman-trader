# AGENTS.md

## Project Overview
KapMan Trader is a local, containerized trading decision-support system for KapMan Investments.

The system:

- Loads daily OHLCV market data for a broad ticker universe.
- Ingests options chains for active watchlists.
- Computes technical, price, dealer, volatility, and Wyckoff metrics.
- Persists daily analytical snapshots in PostgreSQL/TimescaleDB.
- Runs deterministic AI screening over the watchlist.
- Produces structured recommendations, diagnostics, dashboards, and reports for daily options planning.

This is not an order-routing system. It supports analysis, screening, recommendation generation, and review.

## Source Of Truth
Use repo documents before inventing behavior.

- Architecture authority: `/docs/architecture/KAPMAN_ARCHITECTURE.md`
- Current delivery sequencing: `/docs/planning/Roadmap.md`
- Story-level requirements: `/docs/stories/`
- Operational commands: `/docs/runbooks/kapman_tools_syntax.md`
- KapMan rule knowledge: `/docs/architecture/knowledge/`
- Research inputs and references: `/docs/research_inputs/` and `/docs/research/`
- Test layout and commands: `/tests/README.md`

If documents conflict, prefer this order:

1. Architecture and knowledge-base rules
2. Active roadmap and story documents
3. Existing implementation and tests
4. Older archived docs

## How To Work In This Repository
- Work autonomously and make the most conservative reasonable assumption when details are missing.
- Inspect existing files before editing and follow local patterns.
- Keep changes scoped to the requested story or defect.
- Prefer small, working vertical slices over broad scaffolding.
- Do not add placeholder TODOs for in-scope work.
- Do not silently weaken validation, skip tests, or hide failures.
- Do not commit secrets, real account credentials, API keys, or `.env` contents.
- Preserve deterministic behavior in ingestion, metric computation, database rebuilds, and AI output parsing.
- Treat generated data, benchmark exports, and research artifacts as separate from production code.

## Tech Stack
- Python core service: FastAPI, SQLAlchemy, pandas, numpy, Redis clients, market-data providers.
- Node API service: Express, dotenv, CORS.
- Frontend: Next.js 13.4, React 18, Tailwind CSS, TypeScript.
- Database: PostgreSQL 15 with TimescaleDB.
- Cache: Redis 7.
- Observability and inspection: Grafana, Prometheus, Metabase, pgAdmin.
- Testing: pytest with unit, integration, e2e, and db markers.
- Runtime: Docker Compose on local Mac-oriented environments.

Do not swap frameworks, database technologies, provider boundaries, or major package versions unless a story or architecture document requires it.

## Repository Layout
- `/core/` - Python FastAPI app, ingestion, providers, metrics, analytics jobs, database client code.
- `/core/ingestion/ohlcv/` - Polygon S3 OHLCV parsing and loading.
- `/core/ingestion/options/` - options-chain normalization, provider ingestion, and persistence.
- `/core/ingestion/tickers/` - ticker universe bootstrap and reference-data loading.
- `/core/ingestion/watchlists/` - deterministic watchlist loading.
- `/core/metrics/` - TA, price, dealer, volatility, Wyckoff, daily snapshot, and AI screening jobs.
- `/core/providers/market_data/` - Polygon, Unicorn, and other market-data provider adapters.
- `/core/providers/ai/` - AI provider abstraction, prompt loading, payload normalization, invocation, and response parsing.
- `/api/` - Express API gateway service.
- `/frontend/` - Next.js frontend.
- `/db/migrations/` - database schema baseline and migrations mounted into the DB container.
- `/db/dashboards/` and `/db/views/` - SQL inspection dashboards and shared views.
- `/scripts/` - runnable ingestion, metric, rebuild, smoke, cron, and utility entrypoints.
- `/tests/` - pytest unit, integration, e2e, db, provider, pipeline, and metric tests.
- `/docs/` - architecture, stories, runbooks, research, prompts, and knowledge-base rules.
- `/data/` - local data artifacts, chart packs, traces, reports, and benchmarks.
- `/schemas/` - structured output and AI contract schemas.

## Environment
Typical local setup:

```bash
source venv/bin/activate
set -a
source .env
set +a
docker compose up -d
```

Common environment variables used by services and scripts:

- `DATABASE_URL`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `REDIS_URL`
- `AI_PROVIDER`
- `CLAUDE_API_KEY`
- `OPENAI_API_KEY`
- `POLYGON_API_KEY`
- `OPTIONS_PROVIDER`
- `OHLCV_SOURCE`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET`

Do not print secret values in logs or final responses. When a command requires local secrets and they are missing, report the missing variable name only.

## Running The Stack
Use Docker Compose for the integrated environment:

```bash
docker compose up -d
docker compose ps
```

Expected local service ports:

- Frontend: `http://localhost:3001`
- Express API: `http://localhost:4000`
- Python core service: `http://localhost:5001`
- PostgreSQL/TimescaleDB: `localhost:5432`
- pgAdmin: `http://localhost:5050`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3003`
- Metabase: `http://localhost:3000`

Health checks:

```bash
curl -sf http://localhost:4000/health
curl -sf http://localhost:5001/health
```

## Validation
Run the narrowest relevant validation after each meaningful change.

Python:

```bash
pytest
pytest tests/unit
pytest tests/integration
pytest --cov=core tests/
```

Targeted pytest examples:

```bash
pytest tests/unit/metrics/test_ta_price_metrics.py
pytest tests/integration/test_c4_batch_ai_screening.py
pytest tests/integration/test_a0_ohlcv_upsert_idempotence.py
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

API:

```bash
cd api
npm run start
```

Database smoke and inspection commands are documented in `/docs/runbooks/kapman_tools_syntax.md`. Prefer those documented entrypoints over ad hoc commands.

## Database And Migration Rules
- PostgreSQL/TimescaleDB is the production data store.
- Keep schema changes in `/db/migrations/`.
- Keep reusable inspection SQL in `/db/dashboards/` or `/db/views/`.
- Preserve deterministic rebuild behavior through `scripts/db/a5_deterministic_rebuild.py` and `scripts/db/a6_wipe_db_and_migrate.py`.
- Do not make schema changes without matching tests or dashboard checks where appropriate.
- Do not introduce unmanaged tables or one-off local-only schema state.
- Prefer existing DB helper modules in `/core/db/` and domain-specific persistence modules before adding new database access paths.
- Raw SQL is acceptable in migrations, dashboard SQL, and established DB utility modules. Keep application SQL parameterized and focused.

## Pipeline Boundaries
- OHLCV ingestion belongs in `/core/ingestion/ohlcv/` and `scripts/ingest_ohlcv.py`.
- Ticker ingestion belongs in `/core/ingestion/tickers/` and `scripts/ingest_tickers.py`.
- Watchlist persistence belongs in `/core/ingestion/watchlists/` and `scripts/ingest_watchlists.py`.
- Options ingestion belongs in `/core/ingestion/options/` and `scripts/ingest_options.py`.
- Technical and price metric computation belongs in `/core/metrics/a2_local_ta_job.py` and related metric modules.
- Dealer metrics belong in `/core/metrics/dealer_metrics_job.py` and `/core/metrics/dealer_metrics_calc.py`.
- Volatility metrics belong in `/core/metrics/a4_volatility_metrics_job.py` and related volatility modules.
- Wyckoff regime, events, derived metrics, and sequences belong in the B-series files under `/core/metrics/`.
- Batch AI screening belongs in `/core/metrics/c4_batch_ai_screening_job.py` and `scripts/run_c4_batch_ai_screening.py`.
- Provider-specific behavior belongs under `/core/providers/`.

Keep parsing, provider access, persistence, metric computation, and presentation concerns separate.

## KapMan Analytics Rules
- KapMan recommendations must be grounded in real persisted data and documented rule files.
- Wyckoff analytics provide structural market context, not trade execution.
- Preserve the canonical MVP metrics defined in the roadmap: RSI, MACD, SMA/EMA, RVOL, VSI, HV, total GEX, net GEX, gamma flip, call wall, put wall, average IV, IV rank, put/call ratio, Wyckoff phase, Wyckoff events, BC score, and Spring score.
- Extended metrics may live in JSON fields when the schema allows it, but do not treat them as contractual unless docs say so.
- Do not invent strikes, expirations, Greeks, dealer metrics, or volatility values.
- Recommendations must use validated option-chain data for contract selection.
- Preserve uncategorized or low-confidence cases instead of forcing weak classifications.
- Surface missing data, stale data, parsing anomalies, provider failures, and validation failures explicitly.

## AI Provider And Output Rules
- AI provider code belongs under `/core/providers/ai/`.
- Keep provider abstraction swappable across Claude/OpenAI implementations.
- Normalize payloads before invocation and parse responses through the existing parser/contracts.
- Persist or log enough trace context to diagnose malformed model outputs, without leaking secrets.
- Follow `/docs/architecture/knowledge/KAPMAN_PROJECT_SYSTEM_INSTRUCTIONS_v2.3.md` for recommendation behavior.
- Follow `/docs/architecture/knowledge/KAPMAN_PROJECT_INSTRUCTIONS_v2.3.md` for report and trade-sheet formatting requirements.
- Never allow AI output to bypass deterministic validation for contracts, schema shape, or persisted recommendation records.

## Frontend And API Rules
- Frontend work lives in `/frontend/src/`.
- Express API work lives in `/api/src/`.
- Preserve existing framework conventions unless a story requires an upgrade.
- Keep frontend display logic separate from metric computation and provider calls.
- API routes should expose persisted or computed outputs through typed, predictable response shapes.
- Do not hardcode account names, personal labels, fake recommendations, or placeholder trading text into rendered UI.
- UI should make missing or stale data visible instead of showing blank success states.

## Coding Conventions
- Use clear, explicit code over clever abstraction.
- Prefer named functions and small modules with single responsibilities.
- Keep provider, ingestion, metric, persistence, and presentation boundaries intact.
- Reuse existing helpers and contracts before adding new ones.
- Add dependencies only when the repo has no reasonable existing tool for the job.
- Add tests for new behavior and regression-prone fixes.
- Keep comments sparse and useful.
- Avoid broad formatting churn in unrelated files.

## Git And GitHub Workflow
- Do not push directly to `main` unless the user explicitly requests it.
- Before making commits, check `git status -sb` and avoid disturbing unrelated changes.
- Use issue-linked branches and commits when GitHub work is requested or when the task is large enough to warrant it.
- Prefer branch names like `fix/KM-NNN-short-description` or `feature/KM-NNN-short-description` when an issue number exists.
- Reference the issue number in commit messages and PR descriptions when one exists.
- If asked to open a PR, run relevant validation first, push the branch, create the PR with `gh pr create`, and report the PR number and validation status.

## Definition Of Done
For code changes, confirm the relevant subset of the following before reporting completion:

- Targeted unit or integration tests pass.
- Full `pytest` passes when the change touches shared pipeline, DB, provider, or metric behavior.
- Frontend lint/build passes when changing `/frontend/`.
- API startup or route smoke checks pass when changing `/api/`.
- Docker services start and health checks pass when changing compose, service wiring, ports, env, or database setup.
- Migrations apply cleanly when changing `/db/migrations/`.
- Dashboard SQL or smoke SQL runs when changing DB inspection surfaces.
- Docs are updated when behavior, commands, or operational assumptions change.

If a validation step cannot run because credentials, external services, or local data are unavailable, state the exact blocker and the validation that remains unconfirmed.

## Off Limits
- Do not commit `.env`, credentials, API keys, tokens, or account-private data.
- Do not fabricate market data, option contracts, dealer metrics, volatility metrics, or AI recommendations.
- Do not silently drop malformed rows, provider failures, parse anomalies, or validation failures.
- Do not bypass deterministic rebuild, migration, or validation paths for convenience.
- Do not move production logic into research folders.
- Do not let research scripts mutate production tables unless explicitly designed and documented.
- Do not weaken tests to make failures pass.
- Do not replace the local Docker Compose architecture with a cloud dependency unless the architecture docs require it.
- Do not instruct the human to run tests or smoke checks when you can run them yourself.
