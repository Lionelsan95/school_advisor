# Backlog — Epics and Tickets

*Each ticket is meant to be handed to Claude Code as a self-contained unit of
work. Reference `06_Implementation_Roadmap.md` for phase order and gating.
Reference `CLAUDE.md` for architecture and coding conventions — do not repeat
those constraints here, they apply to every ticket implicitly.*

---

## Phase 0 — Spike

### SPIKE-1: UAI join reliability test
**Goal:** measure how reliably the education directory and IVAC/IVAL datasets
can be joined on the UAI identifier.
**Deliverable:** a disposable script (not production code) that pulls a sample
from both APIs, attempts the join, and reports the match rate.
**Acceptance criteria:**
- Match rate computed on a real, non-trivial sample (e.g. one full département).
- Result and methodology written into `docs/05_Resultats_Spike_Technique.md`
  section 1.
- Explicit go/no-go statement recorded.

### SPIKE-2: IVAL methodology continuity check
**Goal:** determine whether the old and new IVAL dataset versions can be
displayed as one continuous historical series.
**Deliverable:** comparison notes, not code — read both dataset descriptions
and, if needed, sample overlapping years to check for discontinuities.
**Acceptance criteria:**
- Findings written into `docs/05_Resultats_Spike_Technique.md` section 2.
- Decision recorded on how F5 (history) should handle any break.

### SPIKE-3: Ingestion prototype
**Goal:** validate real data volumes and shapes before designing the final
schema.
**Deliverable:** a throwaway script loading a sample into local Postgres.
**Acceptance criteria:**
- Real row counts and field-level data quality observations recorded in
  `docs/05_Resultats_Spike_Technique.md` section 3.

---

## Phase 1 — Data layer and ingestion

### DATA-1: Domain entities
**Goal:** implement `Etablissement`, `IndicateurResultat`, `SourceReference`
as framework-agnostic domain objects in `back/src/domain/`.
**Acceptance criteria:**
- No import from `infrastructure/` or any framework (SQLAlchemy, FastAPI) in
  `domain/`.
- Fields match the schema in `docs/02_Architecture_Decisions.md`, adjusted per
  spike findings if needed.
- Unit tests for any domain-level validation logic (e.g. non-diffusion rule).

### DATA-2: Database schema and migrations
**Goal:** Alembic migrations implementing the domain entities in Postgres +
PostGIS.
**Acceptance criteria:**
- `IndicateurResultat` table is append-only by design (composite key includes
  `annee`; no update path that overwrites a prior year). The spike verified
  `(uai, annee, type_indicateur)` is strictly unique across all 87 612 rows.
- **A deduplication rule for the directory is decided and documented before
  `uai` is made a primary key on `Etablissement`.** The spike found 74 UAIs
  appearing twice — multi-site establishments sharing one identifier (see
  `05_Resultats_Spike_Technique.md`, section 3, problem 1). Examine the
  `multi_uai` and `etablissement_mere` source fields. A silent "last row wins"
  is not acceptable: it would drop a site without trace.
- Migration runs cleanly against a fresh database via `docker compose up`.

### DATA-3: Education directory ingestion adapter
**Goal:** adapter in `back/src/infrastructure/ingestion/` pulling from the
directory API (`fr-en-annuaire-education`) into `Etablissement` rows.
**Acceptance criteria:**
- Adapter isolated behind a port defined in `domain/` or `application/` (so it
  can be mocked in tests).
- Retrieves the dataset in full without truncation. *(Implemented via
  `/exports/json` rather than paginating `/records`: the spike established that
  `/records` caps at 100 rows per call and has an offset ceiling, so it cannot
  page a whole dataset at all. Pagination is therefore not the mechanism —
  see `05_Resultats_Spike_Technique.md`, section 3, point 4.)*
- Re-running produces no duplicate rows. *(Implemented as a snapshot +
  `TRUNCATE` + `COPY` full reload inside one transaction, not an upsert. The
  directory is a full published extract with no per-row change marker, so a
  full replace is both simpler and the only way to notice deletions. The
  previous state is retained for rollback.)*
- One establishment row per UAI, with every published site preserved.

### DATA-4: IVAC/IVAL ingestion adapter
**Goal:** adapter pulling from the IVAC and IVAL (GT + PRO) datasets into
`IndicateurResultat` rows, applying the join strategy validated in SPIKE-1.
**Acceptance criteria:**
- A missing `valeur_ajoutee` is stored **as the source delivers it** —
  never estimated or backfilled.
- **`sous_seuil_diffusion` is NOT derived from a candidate count.** The spike
  (see `05_Resultats_Spike_Technique.md`, section 3, problem 2) measured 457
  IVAL GT rows above the threshold with no value — 113 of them in Mayotte,
  where the value is not computed at all — and 75 below-threshold rows that do
  carry one. Deriving the flag arithmetically would mislabel a notable share of
  rows. Preserve the source-published null and record no reason rather than
  attributing the absence to the threshold.
- Unmatched establishments (join failures) are logged, not silently dropped.
  Reference match rate is 98.80%; see DATA-5 for the alerting threshold.

### DATA-5: Scheduled ingestion job with failure alerting
**Goal:** wire DATA-3 and DATA-4 into a scheduled job (cron-style, inside the
backend process per the architecture decision — no separate service).
**Acceptance criteria:**
- A failed fetch, a schema mismatch, or an unexpectedly low join match rate
  triggers a visible alert (log-level CRITICAL minimum; a real notification
  channel can come later in Phase 6).
- A snapshot of the previous valid state is retained before each reimport,
  allowing manual rollback.

---

## Phase 2 — Core read API

### API-1: `GET /establishments/{uai}` endpoint
**Goal:** full fact sheet for one establishment.
**Acceptance criteria:**
- Response includes identity data, published result years, the deterministically
  recovered expected rate, scope disclaimer, static explanations, and source
  links — see `08_API_Contract.md`. History remains API-7/Phase 5.
- A missing figure returns an explicit static explanation identifier without
  asserting a row-specific cause.
- Integration tests cover a normal case and an above-threshold row whose value
  is nevertheless absent, so a threshold explanation cannot regress unnoticed.

### API-2: `GET /establishments/search` endpoint
**Goal:** filtered, factual list of establishments.
**Acceptance criteria:**
- Supports UAI/name text lookup and filters for canonical commune, postcode,
  location/radius, type, sector (public/private), and filière.
- Canonical-site matching guarantees the displayed locality is the matched one.
- Fixed order: factual correspondence, then proximity when applicable, then
  stable identity keys — never by any result indicator.
- No filter or parameter allows sorting by "quality" or result value; if a
  consumer requests this, return a 400 with a clear message, don't silently
  ignore it.

### API-3: Static explanatory content store (F3)
**Goal:** storage and retrieval mechanism for the fixed explanatory text
blocks (what each indicator measures / doesn't measure).
**Acceptance criteria:**
- Content is stored as versioned data (a table or versioned config file), not
  a template string interpolated with live LLM output.
- Same indicator always returns the exact same explanatory text, regardless
  of which establishment it's attached to.
- A content change requires an explicit update to this store — document the
  update process in `docs/02_Architecture_Decisions.md` if not already clear.

### API-4: Missing-value transparency (F6)
**Goal:** ensure every response involving a missing indicator explains the
absence accurately — without asserting a cause the source does not give.
**Prerequisite resolved on 2026-08-15:** the DEPP methodology documents several
possible situations, but the open-data rows publish none of their codes. The
approved static text therefore enumerates possibilities without attributing
one to the displayed row. See `05_Resultats_Spike_Technique.md`, section 3,
problem 2, and `04_Journal_Decisions.md`.

> **Constraint established in Phase 1 — read before writing the serializer.**
> The field catalogues of all three indicator datasets were checked: **no
> source publishes any reason for a missing value.** Only the absence itself
> is observable. Consequently the database has no `sous_seuil_diffusion`
> column and none can be added from source data.
>
> The obsolete `sous_seuil_diffusion` and `non_diffusion_reason` fields were
> removed from `08_API_Contract.md`; they must not be reintroduced or computed
> from `candidates_present`.

**Acceptance criteria:**
- The response distinguishes *a figure that is present* from *a figure that is
  absent*, and attributes no cause to the displayed row.
- No response field asserts a cause, and no value is derived from a candidate
  count.
- The response never states the effectif threshold as the cause unless the
  source actually attributes the absence to it.
- Message text is static versioned content (per API-3) and has passed the
  human review step required by `CLAUDE.md` for F3/F6/F7 content.
- Covered by dedicated tests using fixture establishments for each case,
  including one above-threshold-but-valueless case (e.g. a Mayotte UAI).

### API-5: Scope disclaimer inclusion (F7)
**Goal:** every relevant response includes the permanent scope disclaimer.
**Acceptance criteria:**
- Disclaimer text is centralized (one source of truth), not duplicated across
  endpoints.
- Present in the live fact-sheet and search responses. The Phase 5 comparison
  response must reuse the same centralized value when it is implemented.

### API-6: Source attribution (F10)
**Goal:** every numeric data point in a response is paired with a source
reference.
**Acceptance criteria:**
- `SourceReference` linked and returned for every figure.
- Any value computed by the backend (not a raw source figure) is explicitly
  flagged as "computed by [product] from [source]" and distinguished from raw
  official data.

**Phase 2 completion evidence (2026-08-15):** API-1 through API-6 are complete
for the live search and fact-sheet endpoints. The recovered implementation
passed 266 tests (238 unit, 28 integration), fresh migrations 0001→0002,
repository-wide Ruff and strict mypy checks, and real-data smoke checks for a
normal lycée and the documented Mayotte absence case. Comparison remains
Phase 5 scope.

---

## Phase 3 — Conversational layer

### AGENT-0: Deterministic identity and locality foundation — complete
**Goal:** resolve factual UAI/name/commune/postcode requests before adding an
LLM, including « autour de Chaville » through an official local centre.
**Acceptance evidence (2026-08-15):**
- Migration 0003, official Geo API commune ingestion and 30 000-row/schema
  gates are implemented with atomic data/provenance rollback.
- `GET /communes/search` and expanded `GET /establishments/search` expose
  mandatory provenance and deterministic canonical-site matching.
- 359 tests pass (309 unit, 50 integration); Ruff, format, strict mypy and
  fresh 0001→0003/downgrade/re-upgrade checks pass.

### AGENT-1: Tool-use wiring — complete
**Goal:** the LLM layer can return only bounded search criteria and has no
direct factual-data access.
**Acceptance evidence (2026-08-15):**
- The provider-neutral `QueryInterpreter` returns only `InterpretedSearch`;
  the Anthropic adapter accepts exactly one forced closed-schema tool call.
- The orchestrator invokes the same validated commune and establishment
  application cases used by the HTTP endpoints. The provider receives no
  database connection, repository, factual response or free-form answer path.
- The internal facade avoids a self-HTTP loopback while preserving the Phase 2
  factual boundary; this decision is recorded in the journal.

### AGENT-2: Query interpretation and confirmation — complete
**Goal:** the assistant asks one approved static question for an ambiguous
location, echoes successful structured criteria, and recenters subjective
requests without generating prose.
**Acceptance evidence (2026-08-15):**
- Deterministic UAI/postcode/simple-name fast paths do not call the provider.
- Exact commune and official-centre proximity are distinct; missing, unknown,
  ambiguous and centre-less locations each trigger exactly one approved static
  clarification question.
- Every populated provider-returned search filter requires independent lexical
  support in the request; `location_mode` and `needs_location=true`
  additionally require supported exact-location or proximity markers.
  Unsupported or malformed interpretations fail closed before factual search.
- Subjective requests preserve only supported factual criteria and add the
  approved neutral recentering; provider prose is never displayed.

### AGENT-3: Neutrality guardrails and non-regression tests — partial
**Goal:** system prompt and automated tests preventing evaluative language.
**Acceptance criteria:**
- A documented test set of adversarial queries exists (e.g. "what's the best
  school near me", "which one should I choose") and all produce responses
  that redirect to factual search criteria/results without recommending.
- This test set runs in CI, not only manually.
- Forbidden-word list (best, top, recommended, better than, etc.) checked
  automatically against agent output in tests.
**Current evidence (2026-08-15):** forced bounded prompt/schema, semantic
anti-invention validation, adversarial subjective/prompt-injection tests and
static-output neutrality checks pass locally. `Backend quality gates` is now
configured for PRs and pushes to `main`: it migrates disposable PostGIS, then
runs full `pytest -ra` (including adversarial/static-output tests), Ruff and
strict mypy with no live provider key/call. Its local equivalent passed 510
tests with zero skips. The first successful GitHub-hosted run is still pending,
so this ticket remains partial and its CI acceptance criterion is not yet met.

### AGENT-4: Validated-interpretation caching — complete
**Goal:** reduce LLM cost for repeated common queries without caching facts.
**Acceptance evidence (2026-08-15):**
- Maximum entries and TTL are environment-configurable; the thread-safe
  process-local implementation defaults to 256 entries and 900 seconds.
- Normalized repeated requests reuse only a validated `InterpretedSearch`;
  commune, establishment and provenance reads still run each time.
- The key includes provider/model/prompt/schema identity plus source and
  editorial versions. A version change yields a new key (logical miss); old
  entries age out by TTL/LRU rather than a synchronous purge.
- Provider failures and invalid interpretations are never stored, and simple
  deterministic paths bypass both cache and version computation.
- TTL boundary, LRU promotion/eviction/replacement, invalid configuration,
  lock behavior, version misses and factual re-execution are automated tests.
- Accepted limits: one cold cache per process/worker, no Redis/cross-worker
  sharing and no single-flight for simultaneous misses.

---

## Phase 4 — Frontend MVP

### FE-1: Search interface
**Goal:** natural-language input calling AGENT-1/2, displaying API-2 results.
**Acceptance criteria:**
- No UI element (button, badge, color) implies ranking or quality — this is
  a design constraint, not just a copy constraint.
- Applied filters are visible and editable after results are shown.

### FE-2: Establishment fact sheet page
**Goal:** render API-1 response per the layout sketch in
`docs/01_Vision_Produit.md` (PRD section 6, F2).
**Acceptance criteria:**
- Explanatory text (F3) displayed inline next to each indicator, not behind
  an extra click.
- Non-diffusion messages (F6) rendered clearly, not as a blank field.
- Source links (F10) clickable next to every figure.

### FE-3: Scope disclaimer component
**Goal:** persistent, non-dismissible disclaimer per F7.
**Acceptance criteria:**
- Visible without scrolling on both desktop and mobile viewports.
- Reused as a single component across all pages that need it (not
  copy-pasted markup).

---

## Phase 5 — History, comparison, secondary features

### FE-4 / API-7: History chart (F5)
**Goal:** multi-year raw data visualization.
**Acceptance criteria:**
- Any methodology break identified in SPIKE-2 is visually marked on the
  chart with an annotation, not silently smoothed over.
- No trend line, no interpretive text ("improving", "declining") — data
  points only.

### FE-5 / API-8: Side-by-side comparison (F4)
**Goal:** two (max three) fact sheets aligned by row.
**Acceptance criteria:**
- No computed aggregate score, no highlighting of a "better" value on any row.
- Same visual weight (size, color) across all compared establishments.

### FE-6 / API-9: Export/share (F8)
**Goal:** PDF export or stable shareable link of a fact sheet.
**Acceptance criteria:**
- Exported content includes F3, F6, F7, F10 in full — no shortened version
  that drops disclaimers or explanations.
- Shareable link is timestamped so the recipient knows when the data was
  current.

### FE-7 / API-10: Glossary (F9)
**Goal:** accessible glossary with clickable term links throughout the UI.
**Acceptance criteria:**
- Every technical term used elsewhere in the UI (valeur ajoutée, IVAC, IVAL,
  UAI, REP/REP+, etc.) is a clickable link to its definition.
- Glossary accessible from any screen in one interaction.

---

## Phase 6 — Hardening and deployment readiness

### OPS-1: Production image validation
**Acceptance criteria:** production Dockerfiles (back and front) build and run
standalone, pointed at a non-local database via environment variables only.

### OPS-2: Configuration audit
**Acceptance criteria:** no hardcoded URL, secret, or environment-specific
value remains in `back/src` or `front/src` — grep-audit before closing this
ticket.

### OPS-3: Observability and alerting
**Acceptance criteria:** ingestion failures (from DATA-5) reach a real
notification channel, not just a log file nobody reads.

### OPS-4: Data traceability audit
**Acceptance criteria:** for a sample of API responses, every field can be
traced to raw source data, a documented calculation, or versioned static
content — spot-checked manually and documented as a repeatable process.
