# School Establishments Data Assistant

Public-data explainer for French school establishments (annuaire + IVAC/IVAL indicators).
Guiding principle: **the tool explains, it never judges.** No ranking, no recommendation, no scoring.

## Repository structure

```
project-root/
├── back/                   # Backend monolith (hexagonal architecture)
│   ├── src/
│   │   ├── domain/          # Entities and business rules — no framework dependency
│   │   ├── application/     # Ports and use cases orchestrating the domain
│   │   ├── infrastructure/  # Adapters
│   │   │   ├── ingestion/   # Source API clients, adapters, scheduled job, CLI
│   │   │   └── persistence/ # Postgres repositories
│   │   └── interfaces/
│   │       └── api/         # HTTP entrypoints (FastAPI routers)
│   ├── tests/
│   │   ├── unit/            # No database, no network
│   │   └── integration/     # Needs DATABASE_URL
│   ├── alembic/             # Migrations
│   ├── Dockerfile.dev
│   └── pyproject.toml
│   # (a production Dockerfile arrives in Phase 6 — ticket OPS-1)
│
├── front/                  # React + Vite + TypeScript (Phase 4)
│
├── docs/                   # Reference docs (kept in sync with the Claude Project knowledge base)
├── scripts/                # One-off / maintenance scripts
├── .github/workflows/
│   └── backend.yml         # Backend quality gates with disposable PostGIS
├── docker-compose.yml      # Local dev environment (mirrors prod shape, not prod itself)
├── .env.example
└── CLAUDE.md               # Claude Code project context
```

## Why hexagonal architecture for the backend

Domain logic (what an "indicator" means, how missing data stays reason-free,
and the neutrality constraints)
must stay independent from any framework or infrastructure choice. This keeps the core business
rules testable in isolation and makes it possible to swap infrastructure pieces (e.g. change the
LLM provider, change the ingestion source) without touching domain logic.

## Current status

**Phases 0-4 closed; Phase 5 (history, comparison, export, glossary) in progress.** The backend
ingests the education datasets and the official commune reference into
Postgres, and serves factual search and establishment fact sheets. See
`docs/06_Implementation_Roadmap.md` for the phase gating and
`docs/05_Resultats_Spike_Technique.md` for the Phase 0 spike findings that the
data layer is built on.

What works today: `GET /health`, `GET /establishments/search` (including UAI,
name, canonical commune and postcode), `GET /communes/search`,
`GET /establishments/{uai}`, official-data ingestion, and atomic rollback of
establishments, communes and provenance.
`POST /assistant/search` is also live as a bounded structured assistant with
no conversation or user-session history. UAI, five-digit postcode and simple identity queries bypass the
provider; complex requests use an Anthropic-first adapter behind a
provider-neutral application port.

`ANTHROPIC_API_KEY` is optional. Without it, complex natural-language requests
return `etat: "indisponible"`; the deterministic GET endpoints and assistant
fast paths remain available. No provider prose is returned to the user.

Validated complex-query interpretations use a thread-safe, in-process TTL/LRU
cache (defaults: `ASSISTANT_CACHE_MAX_ENTRIES=256`,
`ASSISTANT_CACHE_TTL_SECONDS=900`). It never stores official facts: commune
resolution and establishment search run again on every request. There is no
Redis or external cache; each worker starts and maintains its own cold cache,
and simultaneous cold misses may make duplicate provider calls because the
cache is intentionally not single-flight.

## Local development

```bash
cp .env.example .env

docker compose up --build -d
curl http://localhost:8000/health     # {"status":"ok"}
open http://localhost:5173            # Vite dev server
```

Run migrations and a first ingestion from the host:

```bash
cd back
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
export DATABASE_URL=postgresql://schools_app:<your password>@localhost:5432/schools_db

.venv/bin/alembic upgrade head
.venv/bin/python -m src.infrastructure.ingestion             # ~20s
.venv/bin/python -m src.infrastructure.ingestion --rollback  # undo it
```

**After pulling changes, run both again**, in that order. A migration that adds
a lookup table or a generated column leaves an older database in a state the
code no longer matches, and the failure is not obvious: the fact sheet and the
filtered search keep working while text search fails with
`UndefinedFunction: normalize_search_text`, because only that path depends on
the new schema. Re-running the ingestion is what populates any newly added
reference data — indicator rows are append-only, so a re-run adds nothing it
should not (`Appended 0 new indicator row(s) from 87 612 offered`).

Tests:

```bash
cd back
.venv/bin/python -m pytest tests/unit   # fast, no database, no network

# Integration tests TRUNCATE tables. Use only an explicitly disposable DB.
docker exec schools_db psql -U schools_app -d postgres \
  -c "CREATE DATABASE schools_db_test;"       # one-time setup
DATABASE_URL=postgresql://schools_app:local_dev_password@localhost:5432/schools_db_test \
  .venv/bin/alembic upgrade head
DATABASE_URL=postgresql://schools_app:local_dev_password@localhost:5432/schools_db_test \
TEST_DATABASE_URL=postgresql://schools_app:local_dev_password@localhost:5432/schools_db_test \
  .venv/bin/python -m pytest

.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
```

`Backend quality gates` runs on every pull request and push to `main` or
`master` (this repository's default branch is `master`): one
`ubuntu-latest` job (15-minute timeout), Python 3.12, a health-checked
`postgis/postgis:16-3.4` service with disposable `schools_db_test`, Alembic to
head, full `pytest -ra`, Ruff lint/format and `mypy src`. CI receives no
Anthropic key and makes no live provider or live-source call; provider behavior
is mocked. A green hosted run has been observed, which is what closed Phase 3;
a workflow file alone was deliberately not accepted as evidence.

Phase 0 spike scripts are kept for reference and are disposable — see
`scripts/spike/README.md`.

A full onboarding guide (`docs/setup.md`) is not written yet and is not needed
while the above is the whole story.

## Deployment

Not yet configured. Only the backend development image exists today;
production images and deployment notes are due in Phase 6 (ticket OPS-1, see
`docs/07_Backlog_Epics_Tickets.md`).
