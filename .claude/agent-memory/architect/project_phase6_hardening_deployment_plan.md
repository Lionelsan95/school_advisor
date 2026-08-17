---
name: project-phase6-hardening-deployment-plan
description: Phase 6 (OPS-1..OPS-4) plan — production images, config audit, alerting, traceability audit; the advisory-lock correctness bug found in job.py
metadata:
  type: project
---

Plan produced 2026-08-17 for Phase 6, after Phases 0-5 closed (622 back / 72
front tests, see [[project_phase5_history_compare_export_glossary_plan]]).

## Correctness bug found, not just a ticket: concurrent ingestion runs corrupt rollback
`start_scheduler()` runs once per uvicorn worker process (`main.py` lifespan).
`max_instances=1, coalesce=True` on the APScheduler job (`job.py`) is
per-process only. `PostgresEstablishmentRepository.replace_all`,
`PostgresCommuneRepository.replace_all`, and
`PostgresSourceReferenceRepository.snapshot()/restore_previous()`
(`back/src/infrastructure/persistence/repositories.py`) all snapshot via
`CREATE TABLE X_previous AS SELECT * FROM X` before truncating. Two
concurrent runs (multi-worker scheduler race, or a manual CLI run racing the
scheduled one — happens even with one worker) means the second run's
snapshot captures the *first run's freshly loaded data* as "previous", so
`--rollback` silently restores the wrong state while reporting success.

**Decision: fix with an in-process session-level `pg_try_advisory_lock`
around the whole of `run_ingestion_once`, AND default production to one
uvicorn worker (no `--workers` flag).** Neither alone is enough — the lock
without a documented worker convention still invites scaling workers "for
throughput" on a workload that doesn't need it; the worker convention alone
without a lock is a landmine for whoever changes `--workers` later without
reading the docs. Rejected: dropping the in-process scheduler for an
external cron — would need a `docs/04` entry *superseding* the recorded
architecture decision (in-process scheduler, no separate service), not
justified when a few lines of lock code fully solves it.
`run_ingestion_once` return type becomes `IngestionReport | None` (`None` =
declined, not recorded in `ingestion_run` — a decline isn't an attempt).

## OPS-1 stack picks
- Backend prod image: multi-stage, `python:3.12-slim` **tag-pinned, not
  digest-pinned** (digest pinning would diverge dev/prod and adds an
  update-tracking chore disproportionate to a solo project — revisit only on
  a real supply-chain concern). Non-root user. Healthcheck via
  `urllib.request` (no curl dependency). `CMD` has no `--reload`, no
  `--workers` (defaults to 1 — see above).
- Frontend prod image: Vite build in a `node:22-alpine` stage, served by
  `nginxinc/nginx-unprivileged:alpine` (not plain `nginx:alpine` — avoids
  hand-rolling the non-root/port-8080 setup). SPA fallback via
  `try_files $uri /index.html`.
- **Real, stated-not-solved constraint**: Vite inlines `VITE_API_BASE_URL`
  at build time (`ARG` in the Dockerfile). One image cannot be promoted
  unmodified across environments with different API hosts. A runtime
  `env.js`-via-`envsubst` pattern is the known fix but deliberately deferred
  — no second environment exists yet to promote across.
- `docker-compose.prod.yml`: `backend` + `frontend` services only, **no
  `db` service** — satisfies "non-local database via env only" by
  construction.
- Cannot be verified in this sandbox: a genuine cloud/non-local Postgres.
  Closest real smoke test available: point prod-compose `DATABASE_URL` at
  the dev `db` container's host-published port via LAN/host address (not
  the compose network) rather than merely claiming the criterion met.

## OPS-2 audit result (file:line), so it isn't re-derived
All backend literals found (`settings.py:19,20,26,59`, `ods_client.py:34`,
`geo_api_client.py:15`, `anthropic_interpreter.py:129`,
`domain/dataset_ids.py`) are legitimate — either `Settings`-backed defaults
matching the Definition-of-Done §5 pattern, constructor defaults only
reachable from tests (production always passes the real value explicitly,
confirmed by reading `job.py`/`main.py`), or domain constants (dataset ids,
identical across environments). **One real finding**: `front/src/api/
client.ts:10`'s `?? "http://localhost:8000"` fallback is unconditional, so a
prod build missing the build-time `VITE_API_BASE_URL` arg would silently
ship pointing at the visitor's own machine instead of failing loudly (same
class of gap `DATABASE_URL`'s no-default was built to avoid on the
backend). Fix: restrict the fallback to `import.meta.env.DEV`
(build-time-replaced, dead-code-eliminated from prod bundles), throw
otherwise.

## OPS-3 stack picks
- Structured logging: hand-rolled JSON `logging.Formatter` (no new
  dependency), toggled by new `Settings.log_format` ("text" dev / "json"
  prod). Consolidates `main.py` lifespan and `ingestion/__main__.py`'s
  previously-separate `logging.basicConfig` calls into one
  `configure_logging(settings)`.
- Alerting: **webhook, not email or log-only** — `httpx`/`respx` already
  present (zero new deps), directly testable offline by mocking the
  endpoint. New `back/src/infrastructure/ingestion/alerts.py`, wrapped in
  its own try/except so a dead webhook can never mask or worsen the
  underlying failure and never blocks the existing CRITICAL log / non-zero
  exit code. New `Settings.alert_webhook_url: str | None = None`.
- Not verifiable here: a real Slack/email endpoint actually receiving
  anything — only the `respx`-mocked path can be proven in this sandbox.

## OPS-4 approach
Three-origin traceability model already structurally present in
`back/src/interfaces/api/schemas.py` (`SourceOut`, `FigureOut.calcule`/
`note_de_calcul`, `content_id`), so the *shape* check is automatable: new
`back/tests/integration/test_traceability_audit.py` walks a small fixed
response sample asserting every figure resolves to one of the three origins
and every `content_id` exists in the real `explanatory_content.py`/
`glossary_content.py` registries. What automation cannot check — whether the
prose itself is accurate/neutral, not just present — stays a documented
manual procedure (sample selection, reviewer sign-off location, re-run
cadence) in `docs/deployment-notes.md`, not folded into the test.

## Full task list
Given to the user in the 2026-08-17 conversation as six ordered slices, not
duplicated here since it's a task breakdown (file paths, workflow chain per
CLAUDE.md) rather than a standing decision.
