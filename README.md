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
├── front/                  # Web frontend (responsive, no native app in V1)
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/        # API calls to backend
│   │   └── hooks/
│   ├── public/
│   ├── Dockerfile
│   ├── Dockerfile.dev
│   └── package.json
│
├── docs/                   # Reference docs (kept in sync with the Claude Project knowledge base)
├── scripts/                # One-off / maintenance scripts
├── .github/workflows/      # CI (tests, lint) — deployment pipeline added later
├── docker-compose.yml      # Local dev environment (mirrors prod shape, not prod itself)
├── .env.example
└── CLAUDE.md               # Claude Code project context
```

## Why hexagonal architecture for the backend

Domain logic (what an "indicator" means, the non-diffusion threshold rule, the neutrality constraints)
must stay independent from any framework or infrastructure choice. This keeps the core business
rules testable in isolation and makes it possible to swap infrastructure pieces (e.g. change the
LLM provider, change the ingestion source) without touching domain logic.

## Current status

**Phase 1 complete** (data layer and ingestion). The backend ingests both public
datasets into Postgres end to end; `front/` is still empty. See
`docs/06_Implementation_Roadmap.md` for the phase gating and
`docs/05_Resultats_Spike_Technique.md` for the Phase 0 spike findings that the
data layer is built on.

What works today: `GET /health`, the full ingestion pipeline (67 816
establishments, 87 612 indicator rows, ~15s), and its rollback.
Not built yet: every read endpoint (Phase 2), the LLM layer (Phase 3), the
frontend (Phase 4).

## Local development

```bash
cp .env.example .env

# Database + backend. Both have images; `frontend` fails until Phase 4 adds
# front/Dockerfile.dev, so name the services explicitly for now.
docker compose up -d db backend
curl http://localhost:8000/health     # {"status":"ok"}
```

Run migrations and a first ingestion from the host:

```bash
cd back
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
export DATABASE_URL=postgresql://schools_app:<your password>@localhost:5432/schools_db

.venv/bin/alembic upgrade head
.venv/bin/python -m src.infrastructure.ingestion             # ~15s
.venv/bin/python -m src.infrastructure.ingestion --rollback  # undo it
```

Tests:

```bash
cd back
.venv/bin/python -m pytest tests/unit   # fast, no database, no network
.venv/bin/python -m pytest              # adds integration tests (needs DATABASE_URL)
```

Phase 0 spike scripts are kept for reference and are disposable — see
`scripts/spike/README.md`.

A full onboarding guide (`docs/setup.md`) is not written yet and is not needed
while the above is the whole story.

## Deployment

Not yet configured. The Docker images built for local development are designed to be the same
images promoted to a future staging/production environment. Deployment notes are due in
Phase 6 (ticket OPS-1, see `docs/07_Backlog_Epics_Tickets.md`) — the file
`docs/deployment-notes.md` does not exist yet.
