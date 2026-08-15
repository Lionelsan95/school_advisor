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

## Local development

See `docs/setup.md` (to be created) for the full onboarding guide. Quick start:

```bash
cp .env.example .env
docker compose up --build
```

## Deployment

Not yet configured. The Docker images built for local development are designed to be the same
images promoted to a future staging/production environment (see `docs/deployment-notes.md`,
to be created before the first deployment).
