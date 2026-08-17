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
  never generated freely by the LLM at request time. The approved indicator
  content lives in `back/src/domain/explanatory_content.py`; the separately
  approved assistant strings live in `back/src/domain/assistant_content.py`.

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
# Local environment — all three services build and start.
cp .env.example .env
docker compose up --build -d

# Backend — run from back/ (that is where pyproject.toml, tests/ and the venv
# live; from the repo root these pick up no config and sweep in docs/ etc.)
cd back
pytest tests/unit         # fast, no database and no network

# Integration tests TRUNCATE their tables, so they refuse to run against a
# database that is not explicitly disposable: they need TEST_DATABASE_URL, or
# a DATABASE_URL whose database name ends in `_test`. Anything else skips with
# an explanatory message. (This guard exists because they once wiped a fully
# ingested development database.) One-time setup:
#   docker exec schools_db psql -U schools_app -d postgres \
#     -c "CREATE DATABASE schools_db_test;"
#   docker exec schools_db psql -U schools_app -d schools_db_test \
#     -c "CREATE EXTENSION IF NOT EXISTS postgis;"
#   DATABASE_URL=<...schools_db_test> alembic upgrade head
# Then, to run everything:
DATABASE_URL="postgresql://schools_app:local_dev_password@localhost:5432/schools_db_test" \
TEST_DATABASE_URL="postgresql://schools_app:local_dev_password@localhost:5432/schools_db_test" pytest
ruff check .              # lint
ruff format --check .     # formatting validation (does not rewrite files)
mypy src                  # type check

# Trigger an ingestion run by hand (the scheduler only runs it when
# INGESTION_ENABLED=true). Needs DATABASE_URL.
python -m src.infrastructure.ingestion
python -m src.infrastructure.ingestion --rollback   # undo the last load

# Apply migrations (also needs DATABASE_URL; it has no fallback by design)
alembic upgrade head

# Frontend — the host has no node/npm in this environment, so every npm command
# runs in a container. Either use the compose service:
docker compose exec frontend npm run test
# ...or a throwaway container. Mount the REPOSITORY ROOT, not front/: the
# neutrality test reads docs/14_Charte_Neutralite_Editoriale.md to assert the
# home-page scope reminder still matches the charter word for word, and a
# front/-only mount makes that file unreachable. The -u keeps generated files
# owned by you rather than root on the bind mount.
docker run --rm -v "$PWD:/repo" -w /repo/front -u "$(id -u):$(id -g)" \
  node:22-alpine npm run test

npm run dev      # Vite dev server (compose already runs this)
npm run build    # tsc -b && vite build
npm run lint     # oxlint
npm run test     # vitest run
```

`.github/workflows/backend.yml` runs the same backend gates from `back/` on a
disposable PostGIS database: `python -m alembic upgrade head`, full
`python -m pytest -ra`, `python -m ruff check .`,
`python -m ruff format --check .`, and `python -m mypy src`. The local commands
above remain the reproducible equivalents. Workflow presence alone is not
evidence of a successful hosted run: do not close AGENT-3 or Phase 3 until a
green GitHub Actions run has actually been observed. Normal CI has no Anthropic
key and must not call a live provider or public source.

- Backend: http://localhost:8000 (health check at `/health`)
- Frontend: http://localhost:5173 (Vite dev server)
- Database: localhost:5432 (postgis/postgis image)

## Boundaries

- **Static explanatory content (F3/F6/F7)** — implemented in
  `back/src/domain/explanatory_content.py` and explicitly human-approved on
  2026-08-15. This content is off-limits for
  automated/free-form rewriting by any agent or session. It can be extended or
  corrected, but any change must be explicitly reviewed by a human before
  commit — never auto-committed as part of a routine code change. See the
  dedicated workflow below.
- **Static assistant content** — the six strings in
  `back/src/domain/assistant_content.py`, version 1, were explicitly approved
  on 2026-08-15. Provider output is never displayed. Any text change requires
  explicit human approval and an `ASSISTANT_CONTENT_VERSION` increment before
  the normal neutrality/content synchronization chain.
- **`docs/04_Journal_Decisions.md`** — append-only in spirit. Add new entries;
  don't rewrite or delete past ones without an explicit instruction to do so.
- **`docs/05_Resultats_Spike_Technique.md`** — once filled in from the
  technical spike, treat its findings (join match rate, methodology breaks) as
  ground truth. If new evidence contradicts it, flag the discrepancy rather
  than silently overwriting the file.

## Non-obvious gotchas

*(Established by the Phase 0 spike, 2026-08-15. Full evidence in
`docs/05_Resultats_Spike_Technique.md`. Keep adding here anything a future
session would otherwise rediscover the hard way: state the fact, then the
consequence.)*

- **UAI is not unique in the directory dataset** — 74 UAIs appear twice
  (multi-site establishments sharing one identifier). Consequence: `uai`
  cannot be made a primary key on `Etablissement` until DATA-2 settles a
  deduplication rule. On the indicator datasets, `(uai, year)` *is* strictly
  unique across all 87k rows, so the append-only design holds there.
- **A missing `valeur_ajoutee` does not imply the non-diffusion threshold.**
  457 IVAL GT rows above the threshold have no value (113 of them in Mayotte,
  where it isn't computed), and 75 below-threshold rows do have one (all in
  2016). Consequence: never derive `sous_seuil_diffusion` from a candidate
  count, and never label every missing value as "below threshold" — it is
  factually wrong and breaks the neutrality charter's rule against assigning
  a cause absent from the source.
- **`/records` cannot page a whole dataset** — 100 rows per page with an
  offset ceiling. Consequence: `/exports/json` is the only viable endpoint for
  a full pull. It has no offset limit and returns all 68k directory rows in
  ~4s.
- **The catalog metadata endpoint returns gzip even when the request sends
  `Accept-Encoding: identity`**, while `/records` and `/exports` honour it.
  Consequence: sniff the gzip magic bytes rather than trusting the headers.
- **`annee` (IVAL `_v2`) and `session` (IVAC) are ISO date strings**
  (`"2025-01-01T00:00:00+00:00"`), not integers — but the *legacy* IVAL
  datasets use plain integers, and type several numeric columns as text
  (`va_reu_total` is `"-5"`, not `-5.0`). Consequence: normalise on ingest.
- **The directory has a real regional coverage gap** — Var (83) holds 120
  records, fewer than Lozère, France's least populated département. It causes
  114 of the 119 unmatched indicator UAIs. Consequence: unmatched
  establishments are a source-completeness signal, not a join bug; a drop in
  the 98.8% match rate must alert (DATA-5).
- **The IVAL per-stream series breaks in 2021** (baccalauréat reform: L/ES/S
  replaced by a single general stream). Total-level indicators stay continuous
  2012–2025. Consequence: F5 history uses total-level indicators only, and
  `methodology_breaks` carries 2021 — not the 2019 placeholder in the API
  contract example.
- **IVAC covers only 2022–2025** (4 years) versus 14 for IVAL. Consequence:
  collège fact sheets have a much shorter history than lycée ones, by source
  design, and the UI must say so rather than look broken.

*(Added during Phase 1, 2026-08-15 — both found by integration tests, not by
reading the code.)*

- **A staging table built with `LIKE ... INCLUDING ALL` does not keep its
  index names, and `ALTER TABLE ... RENAME` does not rename indexes.** Swapping
  a staging table into place left the live table carrying
  `establishment_staging_type_idx2` instead of `ix_establishment_type`, with
  the numeric suffix incrementing on every run. Consequence: any later
  migration referring to an index by its declared name would fail on a
  database that had ingested even once. `replace_all` therefore snapshots,
  `TRUNCATE`s and refills the real tables rather than swapping — TRUNCATE is
  transactional in Postgres, so the cutover is still atomic.
- **`CREATE TEMPORARY TABLE ... ON COMMIT DROP` is not dropped between calls
  inside one outer transaction.** The whole ingestion run is wrapped in a
  single transaction, so the commit that would drop the temp table has not
  happened yet and a second `append()` fails with `DuplicateTable`.
  Consequence: drop it explicitly before creating it.
- **The whole ingestion run is one transaction** (`job.py`). Consequence: if
  indicators fail after establishments were replaced, the establishment
  snapshot rolls back too — the database and the `ingestion_run` audit row can
  never disagree about whether a run succeeded.

*(Added during Phase 2, 2026-08-15.)*

- **The DEPP documents three reasons a value-added figure can be missing, and
  the open-data export erases all of them.** Too few candidates, pupil
  information retrieved for under 75% of candidates, or Mayotte (expected
  rates not computed). The DEPP codes these `ND`/`NS`; the published API
  returns a plain `null` in every case — verified on rows with 143 and 655
  candidates. Consequence: the reason is knowable in general, unknowable per
  row. F6 content names the possibilities and attributes none of them.
- **The `<20 GT / <10 PRO` threshold in the glossary is the *raw rate*
  threshold, not the value-added one.** Value-added needs ≥40 GT and ≥20 PRO
  from session 2024 (≥40 for the collège général series, up from 30).
  Consequence: any code or copy citing 20/10 for value-added is wrong. Both
  figures now live in `docs/03_Glossaire_Metier.md`, corrected.
- **The catalog metadata carries two dates and only one means "the data
  changed".** `modified` also moves on a metadata-only edit; `data_processed`
  tracks the data itself. Consequence: `source_published_at` reads
  `data_processed`, or stays null — never `modified`.
- **The directory publishes `voie_*`/`section_*`/`segpa` as the strings
  `"0"`/`"1"` but `ulis` as an integer.** Consequence: `flag_is_set` accepts
  both spellings; do not compare these fields to `"1"` directly.
- **The directory has no `effectif` field at all**, and publishes no academic
  or national average per establishment. Consequence: those were removed from
  the API contract. The expected rate is recoverable exactly as
  `observed − value_added` and is exposed flagged `calcule: true`.
- **The read API pool is read-only and REPEATABLE READ** (`main.py`), and the
  router borrows one connection per request. Consequence: a fact sheet's three
  queries cannot straddle an ingestion commit, and any accidental write from a
  request path fails loudly instead of succeeding.
- **`search()` joins the canonical site with `LATERAL ... ORDER BY sequence
  LIMIT 1`, not `sequence = 0`.** The domain defines canonical as the lowest
  sequence. Consequence: a gap in site numbering cannot silently drop an
  establishment from every search result while leaving it reachable by UAI.

*(Added during the Phase 3 deterministic-search prerequisite, 2026-08-15.)*

- **Locality lookup never calls a geocoder during a user request.** The
  official Geo API commune reference is fetched and fully validated during
  ingestion, then stored locally. Consequence: an unavailable or malformed
  Geo API cannot make request latency or output nondeterministic.
- **Name, commune and postcode matching uses the canonical site only.**
  Matching an annexe while displaying the main site's different commune would
  make a result contradict its own filter. Consequence: other sites remain on
  the fact sheet but do not enter the one-line search match.
- **Text ordering is factual match tier, then distance, then stable identity
  tie-breakers.** `pg_trgm`/`unaccent` provide accent-insensitive lookup in
  PostgreSQL; no result indicator enters the query or index.
- **Rollback includes commune and source-reference snapshots.** Generated
  search columns are excluded from explicit restore inserts, and the success
  audit is committed in the same transaction as the data and provenance.

*(Added during the bounded Phase 3 assistant slice, 2026-08-15.)*

- **Simple UAI, five-digit postcode and identity-name assistant queries bypass
  the provider.** Complex and subjective queries alone enter the optional
  interpretation adapter; a missing key or provider failure cannot disable the
  structured GET endpoints or those fast paths.
- **No provider text is user-facing.** The adapter may return only one closed
  `InterpretedSearch` tool payload. Every populated search filter requires
  explicit lexical support in the original request; `location_mode` and
  `needs_location=true` additionally require supported exact-location or
  proximity markers, before any factual search.
- **Exact commune and proximity are distinct.** Exact mode filters on the
  official commune code. Proximity uses only the published official centre and
  asks one static clarification when the centre is absent; coordinates are
  never guessed.
- **The assistant cache stores validated interpretations, never facts.** Simple
  deterministic paths do not inspect it or compute a source-version token. A
  complex-query key is an opaque SHA-256 over the normalized request, the
  interpreter identity and source/editorial versions. Anthropic identity
  includes provider, model, `PROMPT_VERSION` and a digest of the closed tool
  schema: increment `PROMPT_VERSION` for prompt changes; schema changes alter
  the digest automatically. Source identity sorts every dataset ID, URL,
  synchronization timestamp and publication date. Editorial identity includes
  the assistant version, every explanatory-block version and a digest of the
  unversioned scope disclaimer.
- **Version invalidation is a logical cache miss.** Old entries are not purged
  synchronously; TTL/LRU eviction removes them. Provider failures and invalid
  interpretations are never stored, and factual commune/establishment reads
  always rerun. The cache is thread-safe but process-local, cold after restart,
  has no Redis/cross-worker sharing and is not single-flight, so simultaneous
  cold misses may duplicate a provider call without changing correctness.

*(Added during Phase 4, 2026-08-16 — frontend.)*

- **The frontend is cross-origin from the API** (Vite :5173, API :8000).
  `CORSMiddleware` is configured from `CorsSettings`, which is a *separate*
  class from `Settings` on purpose: middleware is installed at import time
  while `Settings.database_url` is required, so resolving CORS through
  `Settings` makes `main` unimportable without a database and breaks test
  collection. Consequence: do not move `cors_allowed_origins` onto `Settings`.
- **The host has no node/npm — only Docker.** Every npm command runs in a
  container, with `-u $(id -u):$(id -g)` so generated files are not root-owned
  on the bind mount. Consequence: `npm create`, `npm install`, `vitest` and
  `npm run build` all go through `docker compose exec frontend` or a throwaway
  `node:22-alpine`.
- **Neutrality in the UI is structural, not editorial discipline.** `Figure` is
  the only component that renders a result, has no `variant`/`tone`/`status`
  prop, requires `source`, and gets absence wording from the API. `SearchHit`
  carries no figure, so a result list cannot be sorted or coloured by one.
  `tokens.css` contains no red/green pair. Consequence: if you need to render a
  number, extend `Figure` — do not add a second path, and do not add a prop
  that could carry a judgement.
- **`front/src/content/copy.ts` is editorial content under the same human
  review gate as the backend's `explanatory_content.py`.** Three strings there
  name ranking in order to deny it and live in an audited `APPROVED_NEGATIONS`
  allowlist in `tests/neutrality.test.ts`. Consequence: a new string containing
  a forbidden word fails CI until a human reviews it and adds it deliberately.

*(Added during Phase 6, 2026-08-17.)*

- **Two ingestion runs must never overlap, and the reason is rollback, not
  throughput.** Every full-reload repository snapshots its table with
  `CREATE TABLE x_previous AS SELECT * FROM x` before truncating, and that
  snapshot is what `--rollback` restores. If runs overlap, the second one's
  snapshot captures the first's freshly loaded data as "previous", so a later
  rollback restores the wrong state *and reports success*. Consequence:
  `run_ingestion_once` takes a Postgres session-level advisory lock and returns
  `None` when it cannot. It needs no unusual setup to hit — a manual
  `python -m src.infrastructure.ingestion` racing the scheduled run does it
  with a single worker.
- **`APScheduler`'s `max_instances=1` is per-process, so it does not prevent
  this.** Consequence: do not rely on it, and do not run the API with
  `--workers N` expecting the scheduler to stay single — each worker starts its
  own. The lock is what actually protects the data.
- **A declined run is not recorded in `ingestion_run`.** That table answers
  "did the last run succeed"; filling it with skipped runs would bury the
  answer. Consequence: `run_ingestion_once` returning `None` is normal, and the
  CLI exits 0 for it — a non-zero code would make a cron wrapper alert on
  correct behaviour.

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
