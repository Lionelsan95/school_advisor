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
  rows. Store the source's own indication and, where the source gives no
  reason, record the absence as unexplained rather than attributing it to the
  threshold.
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
- Response includes identity data, results with comparison averages, history
  (empty array acceptable at this phase — filled in Phase 5), scope
  disclaimer, and source links — see `08_API_Contract.md`.
- Missing/below-threshold indicators return an explicit reason field, never a
  silent null without explanation.
- Integration test with a seeded establishment covering both a normal case
  and a below-threshold case.

### API-2: `GET /establishments/search` endpoint
**Goal:** filtered, factual list of establishments.
**Acceptance criteria:**
- Supports filters: location/radius, type, sector (public/private), filière.
- Default sort: proximity or alphabetical — never by any result indicator.
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
**Blocked on a prerequisite:** the exact semantics of the DEPP non-diffusion
threshold must be confirmed against the official methodology documentation
before the message text is frozen. See `05_Resultats_Spike_Technique.md`,
section 3, problem 2.

> **Constraint established in Phase 1 — read before writing the serializer.**
> The field catalogues of all three indicator datasets were checked: **no
> source publishes any reason for a missing value.** Only the absence itself
> is observable. Consequently the database has no `sous_seuil_diffusion`
> column and none can be added from source data.
>
> The example payloads in `08_API_Contract.md` still show
> `sous_seuil_diffusion` and a populated `non_diffusion_reason`. **Those fields
> have nothing behind them.** Do not satisfy them by computing a reason from
> `candidates_present` — that is precisely the violation the Phase 1 design
> exists to prevent, and the spike measured 457 rows it would mislabel.
> Either drop the fields from the contract or leave the reason unset.

**Acceptance criteria:**
- The response distinguishes *a figure that is present* from *a figure that is
  absent*, and says nothing about why an absent one is absent.
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
- Present in fact sheet, search results, and comparison responses.

### API-6: Source attribution (F10)
**Goal:** every numeric data point in a response is paired with a source
reference.
**Acceptance criteria:**
- `SourceReference` linked and returned for every figure.
- Any value computed by the backend (not a raw source figure) is explicitly
  flagged as "computed by [product] from [source]" and distinguished from raw
  official data.

---

## Phase 3 — Conversational layer

### AGENT-1: Tool-use wiring
**Goal:** the LLM agent calls the Phase 2 API as its only source of factual
data — no direct database access from the LLM layer.
**Acceptance criteria:**
- Tool definitions map cleanly to API-1 and API-2.
- Agent cannot bypass the API to fetch or compute data itself.

### AGENT-2: Query interpretation and confirmation
**Goal:** the agent reformulates its understanding of an ambiguous query
before showing results (per `docs/01_Vision_Produit.md` F1 spec).
**Acceptance criteria:**
- Ambiguous test queries trigger exactly one clarifying question, never more.
- Reformulation text never implies a quality judgment about location or
  establishment type.

### AGENT-3: Neutrality guardrails and non-regression tests
**Goal:** system prompt and automated tests preventing evaluative language.
**Acceptance criteria:**
- A documented test set of adversarial queries exists (e.g. "what's the best
  school near me", "which one should I choose") and all produce responses
  that redirect to factual comparison without recommending.
- This test set runs in CI, not only manually.
- Forbidden-word list (best, top, recommended, better than, etc.) checked
  automatically against agent output in tests.

### AGENT-4: Response caching
**Goal:** reduce LLM cost for repeated common queries.
**Acceptance criteria:**
- Identical structured queries (same filters) hit a cache instead of
  re-invoking the LLM for the factual part of the response.
- Cache invalidates when underlying data changes (post-ingestion).

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
