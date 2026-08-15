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
      missing. Test that the source's own indication is preserved, not that a
      threshold is recomputed. — 81 unit tests, no database and no network.
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
- [ ] All endpoints covered by integration tests using a seeded test database.
- [ ] No endpoint response contains evaluative wording (test this explicitly —
      see `09_Definition_of_Done_Quality_Gates.md`).
- [ ] API contract matches `08_API_Contract.md` (or the contract doc is
      updated to reflect reality — keep them in sync).
- [ ] Manual smoke test: fetch a real establishment end-to-end through Docker
      Compose and verify the response against the source data.

---

## Phase 3 — Conversational layer (F1)

**Goal:** natural-language search on top of the deterministic API from Phase 2.
The LLM interprets and orchestrates; it does not generate factual or
explanatory content.

**Scope:**
- LLM tool-use wiring: the agent calls the Phase 2 API, never queries the
  database directly.
- Query interpretation and reformulation-for-confirmation behavior.
- Guardrails: system prompt explicitly forbids evaluative wording, ranking
  language, and recommendations — with test cases (see `09_...` doc).
- Response caching for repeated/common queries (cost control).

**Entry criteria:** Phase 2 exit criteria met.

**Exit criteria:**
- [ ] A representative set of test queries (ambiguous, precise, edge cases
      like "best school") produces neutral, non-evaluative responses.
- [ ] Non-regression test suite for tone exists and runs in CI, not just
      manual spot-checks.
- [ ] Cache hit reduces LLM calls for repeated identical queries — verified
      with a basic load test or manual repetition.

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
- [ ] End-to-end manual walkthrough of the funnel described in
      `docs/01_Vision_Produit.md` section "Entonnoir utilisateur" works
      without dead ends.
- [ ] A non-technical reviewer (or you, wearing that hat) confirms no page
      reads as a recommendation.
- [ ] Responsive on mobile viewport — no native app, but must not break on
      small screens.

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
- [ ] All 10 features from `docs/01_Vision_Produit.md` are implemented and
      pass the neutrality checklist.
- [ ] Exported fact sheets contain the same disclaimers as the live version.

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
- [ ] Production image builds and runs via `docker compose -f
      docker-compose.prod.yml up` (or equivalent) pointed at a non-local
      database, without code changes.
- [ ] A deliberate ingestion failure (bad network, malformed source data) is
      caught and alerted, not silently ignored.
- [ ] Decision log (`docs/04_Journal_Decisions.md`) is up to date with every
      structuring choice made during implementation.
