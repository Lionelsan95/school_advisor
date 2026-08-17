# Implementation Roadmap

*How to read this document: phases are sequential and gated. Do not start a phase
before the previous one's exit criteria are met. Each phase's detailed tickets
live in `07_Backlog_Epics_Tickets.md`.*

---

## Phase 0 — Technical spike (go/no-go gate)

**Goal:** validate the two riskiest technical assumptions before writing any
product code.

**Scope:**
1. Test the join between the education directory dataset and the IVAC/IVAL
   datasets on the UAI key. Measure the reliable match rate on a real sample.
2. Check methodological continuity of IVAL data between the old and new
   dataset versions (does a 13-year continuous series make sense, or is there
   a break that must be surfaced to the user?).
3. Build a throwaway ingestion prototype (one script, local Postgres) to
   observe real data volumes and shapes — not production code, disposable.

**Entry criteria:** none — this is the first phase.

**Exit criteria (must all be true to proceed to Phase 1):**
- [x] Match rate between directory and indicators is measured and documented
      in `docs/05_Resultats_Spike_Technique.md`. — **98.80%**, measured
      nationally (2026-08-15).
- [x] Go/no-go decision recorded. If no-go (match rate below the quality
      threshold, e.g. 90%), an alternative join strategy is documented before
      proceeding (e.g. semi-manual reconciliation queue for ambiguous cases).
      — **GO**; no alternative join strategy needed.
- [x] IVAL methodology continuity documented — any break year identified and
      how it will be surfaced in the UI (F5) is decided. — break is **2021**
      (baccalauréat reform), per-stream only; F5 uses total-level indicators.
- [x] Real record counts and field shapes from both source APIs are noted
      (used later to size the data model correctly). — ~68k establishments,
      ~88k indicator rows, ~21 MB in Postgres.

**Phase 0 closed on 2026-08-15.** Eight adjustments were carried into Phase 1+
tickets — see the table at the end of `docs/05_Resultats_Spike_Technique.md`.
Two of them must be settled *before* writing schema code: the UAI deduplication
rule (DATA-2) and the fact that `sous_seuil_diffusion` cannot be computed from
a candidate count (DATA-4 / API-4).

**Do not proceed past this phase on assumptions. If the spike is skipped,
say so explicitly rather than silently building on an unverified join.**

---

## Phase 1 — Data layer and ingestion

**Goal:** a working, testable data pipeline from public APIs to local Postgres,
independent of any HTTP API or LLM layer.

**Scope:**
- Domain entities (`Etablissement`, `IndicateurResultat`, `SourceReference`) —
  see `docs/02_Architecture_Decisions.md` for the base schema.
- Database migrations (append-only design for `IndicateurResultat`).
- Ingestion adapters for both source APIs (directory + IVAC/IVAL).
- Scheduled ingestion job with explicit failure alerting on schema mismatch
  or sync failure (flagged as the most critical blind spot — do not skip).
- Join logic implementing the strategy validated in Phase 0.

**Entry criteria:** Phase 0 exit criteria met.

**Exit criteria:**
- [x] Ingestion job runs end-to-end locally, populating the database from both
      live source APIs. — 67 816 establishments, 67 896 sites and 87 612
      indicator rows in ~15s. Triggered with
      `python -m src.infrastructure.ingestion`; the in-process scheduler runs
      the same code path daily when `INGESTION_ENABLED=true` (off by default,
      so a checkout never calls the public APIs unasked).
- [x] Unit tests cover the join logic and the handling of missing indicator
      values in isolation, without a real database. Note: the non-diffusion
      threshold (<20 candidates GT, <10 PRO) must **not** be implemented as a
      derivation rule — the spike showed it does not predict which values are
      missing. Test that the source-published null is preserved without a
      derived reason. — 81 unit tests, no database and no network.
- [x] Ingestion failure (simulated: unreachable source, unexpected schema)
      produces a visible alert/log, not a silent partial import. — a missing
      source field raises `SourceSchemaMismatchError` *before* any row is
      parsed; collapsed record counts and a match rate below 95% raise
      `SuspiciousIngestionError` before anything is written. Every failure
      logs CRITICAL and is recorded in the `ingestion_run` table.
- [x] Re-running ingestion does not overwrite prior years' indicator rows. —
      verified against the live data (a second run appends 0 rows) and by
      integration tests that re-offer an existing year with a changed value
      and assert the stored value is unchanged.

**Phase 1 closed on 2026-08-15.** 89 tests pass (81 unit + 8 integration);
ruff and mypy --strict are clean. Carried forward: a production `Dockerfile`
(OPS-1) and `front/Dockerfile.dev` (Phase 4) still do not exist, so
`docker compose up --build` cannot start all three services yet — use
`docker compose up -d db backend`.

---

## Phase 2 — Core read API (backend, no LLM yet)

**Goal:** a deterministic HTTP API serving factual establishment data, fully
testable without any LLM involved. This validates the data layer independently
from the conversational layer.

**Scope (maps to features F2, F6, F7, F10):**
- `GET /establishments/{uai}` — full establishment fact sheet.
- `GET /establishments/search` — filtered list (location, type, sector) with
  no quality-based sorting.
- Non-diffusion transparency logic (F6) built into the response shape, not
  bolted on in the frontend.
- Static explanatory content (F3) storage and retrieval mechanism — content
  is versioned data, not generated at request time.
- Scope disclaimer (F7) included in every relevant response payload.
- Source attribution (F10) included on every data point.

**Entry criteria:** Phase 1 exit criteria met.

**Exit criteria:**
- [x] All endpoints covered by integration tests using a seeded test database.
      — 28 integration tests in `tests/integration/test_establishments_api.py`,
      seeding fake `999…` UAIs at Null Island so a proximity search returns an
      exact, contamination-free set. They now run against a **disposable**
      database (`TEST_DATABASE_URL`, or a DATABASE_URL ending in `_test`) and
      skip loudly otherwise — see the incident note below.
- [x] No endpoint response contains evaluative wording (test this explicitly —
      see `09_Definition_of_Done_Quality_Gates.md`). — `tests/unit/
      test_neutrality.py` scans every `ExplanatoryContent` field, the scope
      disclaimer and the router's rejection message against the forbidden-word
      list with word-boundary matching; `neutrality-checker` reviewed the
      change.
- [x] API contract matches `08_API_Contract.md`. — the two live endpoints were
      rewritten from the running code, and every response key was verified
      programmatically against the document (11 shapes, no undocumented
      fields). Three groups of promised fields were removed because no source
      publishes them: the non-diffusion reason, the academic/national averages,
      and `effectif`.
- [x] Missing provenance fails visibly. — a result row cannot serialize with
      `source: null`; the API router logs the dataset/UAI/year and the API
      withholds the fact sheet with a neutral `503`.
- [x] Manual smoke test: fetch a real establishment end-to-end and verify the
      response against the source data. — `0800001S` returns 14 years with
      sources; `9760127J` (Mayotte, 655 candidates, 2019) returns the absence
      without asserting a cause, which is the case a threshold-based message
      would have mislabelled.

**Phase 2 closed on 2026-08-15 after recovery stabilization.** 266 tests pass
(238 unit + 28 integration); `ruff check .`, `ruff format --check .` and strict
mypy are clean. Migrations 0001→0002 were re-run against a fresh disposable
PostGIS database. Real-data smoke checks confirmed 14 sourced years for
`0800001S` and the reason-free absence for `9760127J` (Mayotte, 655 candidates,
2019). The F3/F6/F7 version-1 content was explicitly re-approved by the project
owner. Two items were also fixed that belonged to earlier phases: nothing ever
wrote to `source_reference` (so F10 had nothing to read), and directory
ingestion did not read the `voie_*` / `section_*` fields required by API-2.

> **Incident, 2026-08-15 — the integration suite wiped the development
> database.** `tests/integration/test_repositories.py` legitimately TRUNCATEs
> its tables, and `DATABASE_URL` pointed at the ingested development database,
> so a plain `pytest` destroyed 67 816 establishments and 87 612 indicator
> rows. Recovered in ~20s by re-running ingestion (the data is public), but the
> hazard was real and the documented command triggered it. Integration tests
> now refuse any database not explicitly marked disposable. Nothing about the
> Phase 2 code was at fault; the landmine pre-dated it.

**Carried forward:** a production `Dockerfile` (OPS-1) and `front/Dockerfile.dev`
(Phase 4) still do not exist, so `docker compose up --build` cannot start all
three services — use `docker compose up -d db backend`.

---

## Phase 3 — Conversational layer (F1)

**Goal:** natural-language search on top of the deterministic API from Phase 2.
The LLM interprets and orchestrates; it does not generate factual or
explanatory content.

**Completed prerequisite checkpoint (2026-08-15):** migration 0003 adds the
official commune reference and normalized PostgreSQL search indexes. Ingestion
validates and atomically snapshots communes and provenance; `/communes/search`
and the expanded `/establishments/search` now resolve UAI, name, canonical
commune and postcode without an LLM. Ordering is factual match tier, then
distance and stable identity keys; missing source provenance withholds results
with `503`. Evidence: 359 tests (309 unit + 50 integration), zero skips; Ruff
lint/format and strict mypy pass; a fresh database migrated 0001→0003, then
downgraded 0003→0002 and upgraded again. This checkpoint does **not** close
Phase 3.

**Bounded-assistant checkpoint (2026-08-15):** the provider-neutral
`QueryInterpreter` port and an Anthropic Messages adapter now feed exactly one
forced, closed-schema tool result into the no-conversation-history
`POST /assistant/search`. UAI, five-digit postcode and simple identity queries
bypass the provider. Complex or subjective requests require explicit lexical
support for every populated search filter; `location_mode` and
`needs_location=true` additionally require supported exact-location or
proximity markers. They then reuse the
validated commune and establishment application cases. Exact commune and
official-centre proximity are separate modes; ambiguity produces one approved
static question, provider prose is never returned, and version-1 assistant
content has explicit human approval. Mocked-provider, application and HTTP
contract tests cover unavailable, malformed, adversarial and prompt-injection
paths; no live Anthropic key/provider smoke is claimed.

**Validated-interpretation cache checkpoint (2026-08-15):**
`InMemoryInterpretationCache` is a thread-safe, process-local TTL/LRU cache.
Only post-validation structured interpretations are stored; facts and
provenance rerun every request. Normalized equivalent complex requests call
the provider once while commune and establishment searches run twice.
Provider/model/prompt-version/schema/source/editorial version changes miss
logically;
failures and invalid interpretations are not stored; deterministic fast paths
never inspect cache/version state. Automated tests cover the exact TTL
boundary, LRU promotion/eviction, replacement TTL, invalid configuration and
lock behavior. There is no Redis, cross-worker sharing or single-flight.
Phase 3 remains open only for an observed successful hosted CI execution of
the guardrail suite. Evidence:
510 tests (460 unit + 50 integration), zero skips; Ruff lint/format, strict
mypy and `git diff --check` pass against the disposable PostGIS test database.
No live Anthropic key/provider smoke is claimed.

**CI-configuration checkpoint (2026-08-15):**
`.github/workflows/backend.yml` defines `Backend quality gates` for every pull
request and push to `main`. It uses `actions/checkout@v7` with persisted
credentials disabled, `actions/setup-python@v7` with Python 3.12 and pip cache
keyed by `back/pyproject.toml`, then a health-checked
`postgis/postgis:16-3.4` service and dedicated `schools_db_test`. Alembic head,
the full 510-test suite, Ruff lint/format and strict mypy are required in that
order. The equivalent local run passed 510 tests (460 unit + 50 integration),
zero skips, and all static gates. CI supplies no Anthropic key and performs no
live provider smoke. No successful GitHub-hosted run is claimed: Phase 3
remains open only until the first hosted backend workflow run is observed
green without unexpected skips.

**Scope:**
- LLM tool-use wiring: inside the monolith, the orchestrator reuses the same
  validated Phase 2 application cases and schemas as the HTTP API; the
  provider receives no repository or connection and never queries the database.
- Commune resolution uses the deterministic local reference before an
  establishment proximity search; the LLM never invents coordinates.
- Query interpretation, one approved static location clarification when
  needed, and neutral recentering of subjective requests.
- Guardrails: system prompt explicitly forbids evaluative wording, ranking
  language, and recommendations — with test cases (see `09_...` doc).
- Bounded caching of validated interpretations for repeated/common queries;
  factual searches still execute against current data on every request.

**Entry criteria:** Phase 2 exit criteria met.

**Exit criteria:**
- [x] A representative set of test queries (ambiguous, precise, edge cases
      like "best school") produces neutral, non-evaluative responses.
- [x] Non-regression test suite for tone exists and runs in CI, not just
      manual spot-checks. — `.github/workflows/backend.yml` runs the full
      suite, ruff lint, ruff format and strict mypy against an ephemeral
      PostGIS container on every push and pull request. First observed hosted
      run: [31961896283](https://github.com/Lionelsan95/school_advisor/actions/runs/31961896283),
      **success** on `1bcb4d4` (2026-08-16), 510 tests, no skips.
- [x] Normalized repeated queries reduce provider calls; automated tests also
      cover TTL/LRU behavior, version misses, invalid/failure non-caching and
      per-request factual re-execution.

**Phase 3 closed on 2026-08-16.** The remaining criterion was an observed
successful hosted CI execution, now recorded above. The CI push trigger had to
be corrected first: it listed `main` only, while this repository's default
branch is `master`, so it would never have fired.

> **~~Known gap~~ — fixed 2026-08-16.** Resolved by distinguishing a refusal
> from an outage; see `04_Journal_Decisions.md`, « Un refus de classer n'est pas
> une panne ». Original description follows.
>
> A request that was *purely* subjective, with no salvageable factual
> criterion — "Quel est le meilleur collège ?" with no place, type or sector —
> returned the generic "interpretation unavailable" message instead of the
> charter's own §12 answer. Nothing was ranked and no evaluative wording was
> emitted, so the charter was not breached; but the user was told this was a
> technical unavailability, which it was not, and was invited to retry with a
> structured search that had nothing to search on. Root cause:
> `AssistantSearchUnavailable` carried no flag, so the `subjective` signal was
> discarded when `_validate_intent` rejected a criteria-less intent.

---

## Phase 4 — Frontend MVP

**Goal:** usable web interface covering F1, F2, F3, F6, F7, F10 (the MVP
scope defined in `docs/01_Vision_Produit.md`).

**Scope:**
- Search interface (chat-style or hybrid).
- Establishment fact sheet page.
- Explanatory content displayed inline (not hidden behind extra clicks).
- Scope disclaimer visible without scrolling/interaction.
- Source links on every figure.

**Entry criteria:** Phase 3 exit criteria met.

**Exit criteria:**
- [x] End-to-end manual walkthrough of the funnel described in
      `docs/01_Vision_Produit.md` section "Entonnoir utilisateur" works
      without dead ends.
- [x] A non-technical reviewer (or you, wearing that hat) confirms no page
      reads as a recommendation.
- [x] Responsive on mobile viewport — no native app, but must not break on
      small screens.

**Phase 4 closed on 2026-08-16 on the project owner's review and sign-off.**

> **What that sign-off did and did not rest on, recorded plainly so a later
> reader does not over-read it.** The three criteria above are human judgements
> by design, and the owner reviewed the implementation and accepted it. No
> automated visual or viewport test backs them: the browser tooling was not
> connected in the session that built this, so the sign-off rests on the owner's
> own inspection rather than on a recorded walkthrough. If a later phase needs
> these criteria to be *evidenced* rather than attested — for an accessibility
> audit, say — they should be re-run with tooling and the result recorded here.
> What *is* machine-verified: 46 frontend tests, oxlint, a clean TypeScript
> build, both CI workflows green, and a live-API smoke run confirming CORS,
> that every result row carries a source, and that search rows carry no figure.

FE-1, FE-2 and FE-3 are built: the search interface, the establishment fact
sheet with inline explanations and per-figure sources, and the non-dismissible
scope disclaimer.

Two decisions taken during the phase, both recorded in
`04_Journal_Decisions.md`: CORS was added to the backend (a backend change
inside a frontend phase, committed separately as CORS-1), and neutrality is
enforced by component structure rather than by copy discipline alone.

Deliberately out of scope, and not built: the "add to comparison" control. The
information-architecture doc treats it as always available, but the comparison
screen is Phase 5 (FE-5/API-8) and shipping a visible control that leads
nowhere is a dead end in the funnel the first criterion above tests for.

Also carried forward, unchanged: production images remain a Phase 6 concern
(OPS-1). Only development images exist.

---

## Phase 5 — History, comparison, and secondary features (F4, F5, F8, F9)

**Goal:** complete the remaining in-scope MVP features.

**Scope:**
- F5 — multi-year history chart, with the methodology break (if any, from
  Phase 0) visually marked.
- F4 — side-by-side view, strictly no aggregate scoring.
- F8 — export/share of a fact sheet (PDF or stable link), preserving F3/F6/F7.
- F9 — glossary, accessible from anywhere, terms clickable in context.

**Entry criteria:** Phase 4 exit criteria met.

**Exit criteria:**
- [x] All 10 features from `docs/01_Vision_Produit.md` are implemented and
      pass the neutrality checklist. — `neutrality-checker` reviewed F5, F4, F8
      and F9 and answered "non" to all seven of the charter's §14 questions.
      F9's inline term links were completed after that review: indicator
      labels, `filieres`, `sections` and `type_indicateur` are wrapped in a
      `GlossaryTerm` component, and every value the UI actually shows now
      resolves to a definition (verified against real data — the sections on a
      live fact sheet were `europeenne`, `sport`, `arts`, none of which had an
      entry until six were added).
- [x] Exported fact sheets contain the same disclaimers as the live version. —
      both the fact sheet and the comparison page render every explanation
      unconditionally in a print-only block, and a test asserts the comparison
      prints the *same* six charter-mandated parts as the fact sheet.

**Phase 5 closed on 2026-08-16.**

Delivered: the history chart with the 2021 rupture drawn as a break in the
line (API-7/FE-4), side-by-side comparison with rows aligned server-side so no
client can difference them (API-8/FE-5), export and share via a print
stylesheet (API-9/FE-6), and the glossary with inline term links
(API-10/FE-7). 622 backend and 72 frontend tests pass.

> **Two defects worth remembering, both found by review rather than by tests.**
> The comparison page printed three of the six mandatory explanation parts
> while the fact sheet printed six — an abridged export, which the F8 criterion
> forbids in those words. Nothing caught it because the print tests only
> covered one of the two export surfaces. Lesson: a criterion phrased "in full"
> needs a test per export surface, not per feature.
>
> Separately, a blanket forbidden-token scan on the comparison response failed
> on the project's own vocabulary: "écart" appears legitimately in the DEPP's
> definition of value added (observed minus *expected*). The checks now ban
> those tokens on keys anywhere, exempt the `explications` block, and
> separately assert that block is byte-identical to what the fact sheet serves.

**On F9's inline links:** deliberately not implemented by scanning reviewed
prose for term names and injecting markup — that would put generated markup
inside human-reviewed content, and would link the same word differently
depending on where it appeared. The enumerable call sites are wrapped
explicitly instead. If the glossary cannot be fetched, terms render as plain
text: a definition is an aid, and its absence must never withhold the figure
beside it.

---

## Phase 6 — Hardening and deployment readiness

**Goal:** the application is ready to be deployed, without necessarily being
deployed yet.

**Scope:**
- Production Dockerfile validated (build succeeds, image runs standalone).
- Environment-based configuration fully externalized (no hardcoded secrets
  or URLs anywhere — audit `back/src` for this).
- Basic observability: structured logs, ingestion failure alerting wired to
  a real notification channel (even just an email or a log-based alert).
- Data traceability: every API response traceable to its source (raw data /
  deterministic calculation / static versioned content) per the requirement
  in `docs/02_Architecture_Decisions.md` section "Contrainte spécifique".
- `docs/deployment-notes.md` written, covering target environment, secrets
  management approach, and rollback plan for ingestion.

**Entry criteria:** Phase 5 exit criteria met.

**Exit criteria:**
- [x] Production image builds and runs via `docker compose -f
      docker-compose.prod.yml up` pointed at a non-local database, without code
      changes. — both images build and report healthy, both run non-root
      (uid 10001 / 101), the backend served a real 14-year fact sheet and the
      SPA deep link resolved. **Partially verified:** the database was the
      development Postgres reached over the host's LAN address — external to
      the compose project, but not a managed remote instance. No cloud target
      exists in this environment. Re-run against a real database before
      deploying; see `docs/deployment-notes.md`, "Not verified".
- [x] A deliberate ingestion failure (bad network, malformed source data) is
      caught and alerted, not silently ignored. — `test_ingestion_job_alerting.py`
      drives the real use case and the real alert function against fakes and a
      mocked webhook, asserting the failure logs CRITICAL, the alert is posted
      with the reason, and the original exception still propagates. A dead
      webhook changes none of that and the `ingestion_run` failure row is still
      written. **Not verified:** that a real Slack or email relay accepts the
      payload shape.
- [x] Decision log (`docs/04_Journal_Decisions.md`) is up to date with every
      structuring choice made during implementation.

**Phase 6 closed on 2026-08-17.** 652 backend and 72 frontend tests pass; ruff,
ruff format, strict mypy and oxlint clean.

> **The most valuable find of the phase was a bug, not a ticket.** Overlapping
> ingestion runs silently corrupted rollback: the second run's snapshot captured
> the first's freshly loaded data as "previous", so a rollback restored the wrong
> state *and reported success*. It needed no unusual setup — a manual CLI run
> racing the scheduled one hits it with a single worker — and would only have
> surfaced mid-incident. Fixed with a Postgres advisory lock.

Two mistakes made during the phase, recorded because both are easy to repeat:
bringing up the production stack **recreated a development container**, because
Compose derives the project name from the directory and treated the two files'
`backend`/`frontend` as the same services; and a `/health` check answered from an
unrelated application already using the chosen port — a health endpoint that
answers does not prove the right service answered.

**Carried forward, deliberately not done:** the frontend image encodes its API
host at build time (Vite inlines `VITE_API_BASE_URL`), so it cannot be promoted
unmodified between environments with different APIs. The runtime-`env.js` fix is
deferred until a second environment exists to promote across, rather than guessed
at now.
