# Project context for Claude Code

## What this project is

A public-data explainer for French school establishments (annuaire + IVAC/IVAL
indicators from data.education.gouv.fr). It translates official statistics into
plain, sourced, contextualized language.

## Non-negotiable product principle

**The tool explains, it never judges.**

- No ranking, no scoring, no "best school" logic, anywhere in the codebase.
- No evaluative wording in generated text ("good", "excellent", "recommended",
  "top", "best"). If you are about to write or suggest such wording, stop and
  flag it instead.
- Explanatory content for indicators (what a "valeur ajoutée" means, why a data
  point is missing, the scope disclaimer) must be **static, versioned content**,
  never generated freely by the LLM at request time. See `back/src/domain/`
  for where this content should live once implemented.

If unsure whether a feature or a piece of copy respects this principle, default
to the simpler, more neutral option — or ask before implementing.

## Architecture

- **Backend**: Python / FastAPI, hexagonal architecture.
  - `src/domain/` — entities and business rules, zero framework dependency.
  - `src/application/` — use cases orchestrating the domain.
  - `src/infrastructure/` — adapters: Postgres, external data-source APIs,
    ingestion jobs, LLM client. Nothing here should be imported by `domain/`.
  - `src/interfaces/api/` — FastAPI routers. Thin wiring only, no business logic.
- **Database**: PostgreSQL + PostGIS. No NoSQL, no Elasticsearch — not justified
  at this volume (~66k establishments). See `docs/02_Architecture_Decisions.md`.
- **No microservices, no message queue.** Single backend service. Do not
  introduce additional services unless a real bottleneck is observed and
  documented — see the architecture review's explicit warning against
  premature complexity.
- **Frontend**: React + Vite, responsive web only in V1 (no native app).
- **Ingestion**: scheduled job inside the backend process (not a separate
  service), decoupled from user-facing requests. Must fail loudly (alert) on
  source schema changes or sync failures — this was flagged as the most
  critical blind spot in the architecture review.
- **Historical data**: indicators are append-only by year — never overwrite a
  previous year's row.

## Reference documents

Full context lives in `docs/`:
- `01_Vision_Produit.md` — product vision, scope, personas, features F1-F10
- `02_Architecture_Decisions.md` — architecture rationale, decisions, risks
- `03_Glossaire_Metier.md` — domain vocabulary (IVAC, IVAL, UAI, DEPP...)
- `04_Journal_Decisions.md` — running decision log, check before proposing
  something that might already be settled
- `05_Resultats_Spike_Technique.md` — technical spike results (UAI join
  reliability, IVAL methodology continuity) — check this before building on
  the join between the directory and the indicators datasets

## Conventions

- All code, comments, commit messages, and identifiers: **English**.
- Python: type hints everywhere, `ruff` for linting, `pytest` for tests.
- Keep functions small and domain logic framework-agnostic (testable without
  spinning up FastAPI or a database).
- Commit small and often — this is a solo project relying on AI pair-coding;
  a fine-grained git history matters more here than in a team setting.

## Commands

```bash
# Local environment
cp .env.example .env
docker compose up --build

# Backend (run inside the backend container, or locally with the venv active)
pytest                  # run tests
ruff check .             # lint
ruff format .             # format
mypy src                  # type check

# Frontend
npm run dev              # Vite dev server
npm run build              # production build
npm run lint               # eslint
```

- Backend: http://localhost:8000 (health check at `/health`)
- Frontend: http://localhost:5173
- Database: localhost:5432 (postgis/postgis image)

## Boundaries

- **Static explanatory content (F3/F6/F7)** — once implemented (see ticket
  API-3 in `docs/07_Backlog_Epics_Tickets.md`), this content is off-limits for
  automated/free-form rewriting by any agent or session. It can be extended or
  corrected, but any change must be explicitly reviewed by a human before
  commit — never auto-committed as part of a routine code change. See the
  dedicated workflow below.
- **`docs/04_Journal_Decisions.md`** — append-only in spirit. Add new entries;
  don't rewrite or delete past ones without an explicit instruction to do so.
- **`docs/05_Resultats_Spike_Technique.md`** — once filled in from the
  technical spike, treat its findings (join match rate, methodology breaks) as
  ground truth. If new evidence contradicts it, flag the discrepancy rather
  than silently overwriting the file.

## Non-obvious gotchas

*(Empty for now — this project hasn't been implemented yet. As the codebase
grows, record here anything a future session would otherwise have to
rediscover the hard way: subtle remapping logic, ordering dependencies,
shared state across modules, anything "load-bearing" that isn't obvious from
reading the code once. Follow the style of the entries in this file's
inspiration source: state the fact, then state the consequence.)*

## Workflow

Use these subagent chains depending on the size and nature of the change.
"Fix directly" means the main thread applies the correction itself — no
dedicated agent for that step.

**Small edit**
write code → `code-improver` → fix directly if issues found (or delegate to
`debugger` if it's a real bug, not a style issue) → `test-writer` →
`test-runner` → `neutrality-checker` → `docs-sync-checker` → fix docs directly
if needed → `secret-scanner` → `commit-writer`

**Large feature / refactor**
`architect` → write code → `code-improver` → fix directly (or `debugger` for
real bugs) → `test-writer` → `test-runner` → `neutrality-checker` →
`docs-sync-checker` → fix docs directly → `secret-scanner` → `commit-writer`

**Bug fix**
`debugger` → `test-writer` (regression test) → `test-runner` →
`secret-scanner` → `commit-writer`

**Data source / ingestion change** (new dataset field, source API schema
change, join logic change)
`architect` (review against `docs/02_Architecture_Decisions.md` and
`docs/05_Resultats_Spike_Technique.md`) → write code → `test-writer` (must
include a case simulating a source schema mismatch) → `test-runner` →
`docs-sync-checker` (update `08_API_Contract.md` and the data model docs if
shapes changed) → `secret-scanner` → `commit-writer`. Never skip the
schema-mismatch test case — this is the project's most critical known blind
spot (see `docs/02_Architecture_Decisions.md`, "Risques / angles morts").

**Explanatory content change** (F3/F6/F7 static text)
write proposed content → **explicit human review and approval (mandatory,
not optional)** → `neutrality-checker` → `test-runner` (content-consistency
tests, e.g. same indicator always returns the same text) →
`docs-sync-checker` → `commit-writer`. No agent proceeds to commit this
category of change without a human sign-off step actually happening —
`commit-writer` must refuse to run if that step was skipped.

**Dependency maintenance** (periodic, not per-feature)
`dependency-auditor` → code adjustments if breaking changes → `test-runner` →
`secret-scanner` → `commit-writer`

**Docs-only change**
`docs-sync-checker` → fix directly → `commit-writer`

### What `neutrality-checker` must verify

This agent is specific to this project (not a generic code-quality check):
- No evaluative wording in any user-facing string (see the forbidden-word
  list in `docs/09_Definition_of_Done_Quality_Gates.md`).
- No new sort, filter, or UI ordering tied to a result indicator.
- Any new explanatory or disclaimer text matches the static-content pattern
  (not generated inline by an LLM call at request time).

## What NOT to do

- Do not add ranking, scoring, or comparison logic that produces an implicit
  "better/worse" signal.
- Do not let the LLM generate the explanatory/disclaimer text at request time
  — always route through static, versioned content.
- Do not introduce infrastructure complexity (queues, extra services, NoSQL)
  without first documenting why the current setup is insufficient.
- Do not silently swallow ingestion errors or schema mismatches from the
  external data sources — always surface them.
