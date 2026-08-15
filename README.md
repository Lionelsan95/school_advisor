# School Establishments Data Assistant

Public-data explainer for French school establishments (annuaire + IVAC/IVAL indicators).
Guiding principle: **the tool explains, it never judges.** No ranking, no recommendation, no scoring.

## Repository structure

```
project-root/
├── back/                   # Backend monolith (hexagonal architecture)
│   ├── src/
│   │   ├── domain/          # Entities, business rules, ports (interfaces) — no framework dependency
│   │   ├── application/     # Use cases / services orchestrating the domain
│   │   ├── infrastructure/  # Adapters: db, external APIs, ingestion jobs, LLM client
│   │   │   ├── db/
│   │   │   ├── api/
│   │   │   ├── ingestion/
│   │   │   └── llm/
│   │   └── interfaces/
│   │       └── api/         # HTTP entrypoints (FastAPI routers)
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── migrations/          # Alembic migrations
│   ├── Dockerfile
│   ├── Dockerfile.dev
│   └── pyproject.toml
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

The project is at the **end of Phase 0** (technical spike — completed, verdict GO).
`back/` and `front/` are still empty: no application code exists yet. See
`docs/06_Implementation_Roadmap.md` for the phase gating and
`docs/05_Resultats_Spike_Technique.md` for the spike findings.

## Local development

```bash
cp .env.example .env

# Works today — the database is the only service with an image:
docker compose up -d db

# Will work once Phase 1 adds back/Dockerfile.dev and Phase 4 adds
# front/Dockerfile.dev. It fails today, by design, not by misconfiguration:
docker compose up --build
```

Phase 0 spike scripts (disposable, see `scripts/spike/README.md`):

```bash
python3 scripts/spike/spike1_uai_join.py
python3 scripts/spike/spike2_ival_continuity.py
python3 scripts/spike/spike3_ingestion_prototype.py   # needs the db service
```

A full onboarding guide (`docs/setup.md`) is not written yet and is not needed
while the above is the whole story.

## Deployment

Not yet configured. The Docker images built for local development are designed to be the same
images promoted to a future staging/production environment. Deployment notes are due in
Phase 6 (ticket OPS-1, see `docs/07_Backlog_Epics_Tickets.md`) — the file
`docs/deployment-notes.md` does not exist yet.
