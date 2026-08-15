---
name: project-phase1-data-layer-plan
description: Concrete Phase 1 (DATA-1..5) implementation plan and the raw-data findings that overturn parts of the ticket text, given 2026-08-15
metadata:
  type: project
---

**STATUS: plan handed off, not yet executed as of 2026-08-15.** `back/` and `front/`
were still empty directories at planning time. Read `docs/07_Backlog_Epics_Tickets.md`
(DATA-1..5) and `docs/05_Resultats_Spike_Technique.md` first — this memory only records
what the tickets/docs don't already say, derived by inspecting the raw spike JSON
directly (`scripts/spike/output/*.json`, gitignored, not committed).

**`etablissement_mere` does NOT solve the multi-UAI dedup problem — this contradicts
what DATA-2's ticket text implies.** Of the 154 rows sharing one of the 74 duplicated
UAIs, only 2 have a non-null `etablissement_mere`. That field is a separate mechanism:
2,761 *other* rows, each with their own unique UAI, pointing to a distinct parent UAI
via `type_rattachement_etablissement_mere` (`ANNEXE GEOGRAPHIQUE` / `FILIERE OU
DEPARTEMENT OU SECTION`). `multi_uai` (0/1) does correctly and exhaustively flag the
154 affected rows — use it as a filter, not `etablissement_mere`.
Why: DATA-2 ticket text says "examine `multi_uai` and `etablissement_mere`" as if both
are dedup levers. Only one is.
How to apply: when implementing DATA-2, don't spend time trying to use
`etablissement_mere` to disambiguate multi-site duplicates — it can't. See
[[project_phase1_data_layer_plan]] step 3 for the actual recommended rule (surrogate
PK + composite unique `(uai, code_postal, commune, nom, type_etablissement)` +
`site_sequence` tiebreaker for the 2 residual exact-duplicate rows where even that
composite collides, e.g. UAI `0673079H`, `0753919C`).

**No natural column combination in the directory dataset is a fully reliable dedup
key** — verified by testing `(uai, nom)`, `(uai, code_postal, commune)`, and
`(uai, nom, code_postal)` against all 74 duplicate groups; each has residual
collisions, including two rows that are identical on every field the spike ever
pulled. A surrogate PK on `Etablissement` is required; `uai` stays non-unique and is
still the join key `IndicateurResultat` uses (IVAC/IVAL can't distinguish sites
sharing a UAI either — the source doesn't disambiguate, so don't invent a
disambiguation on the product side that the join can't actually honor).

**UAI format is a real, verified domain invariant**: `^[0-9]{7}[A-Z]$`, holds for all
67,896 directory rows, zero exceptions. Legitimate to enforce as DATA-1 domain
validation (distinct from the forbidden non-diffusion threshold derivation).

**The spike never queried the full IVAC/IVAL field catalogue** (always used a narrow
`select=`) and never observed a source field that distinguishes "DEPP declared
non-diffusion" from "no reason given" — only `valeur_ajoutee` nullness was ever
checked. API-4's two-category requirement (`docs/07`, `docs/08`) may not be
representable from the data at all. Must be confirmed against the live field
catalogue (dataset ids in [[reference_ods_data_sources]]) before finalizing
`IndicateurResultat.sous_seuil_diffusion` in DATA-1/DATA-4 — this is Step 0 of
[[project_phase1_data_layer_plan]]. Same gap applies to the directory's `adresse`,
`filieres[]`, `sections[]`, `effectif`, `annee_effectif` fields (in doc02's sketch,
never confirmed by the spike — only 11 of 71 directory fields were ever pulled).

**Recommended stack decisions for `back/`** (given as a recommendation, not yet
confirmed against implementation): psycopg **3** (not the spike's psycopg2) with raw
parameterized SQL / `COPY` for runtime queries, no SQLAlchemy ORM; Alembic used
Core-only (DDL only) purely to satisfy DATA-2's literal "Alembic migrations"
requirement; `httpx` (not spike's `urllib`) for the production HTTP adapter, mocked
with `respx` in tests; `apscheduler` in-process for DATA-5, started from a FastAPI
lifespan hook — no new service. `src` layout (`back/src/...`) installed via
`pip install -e .` in `Dockerfile.dev` so `uvicorn src.interfaces.api.main:app`
resolves regardless of uvicorn's cwd/sys.path behavior — this was flagged as a
concrete Docker footgun to avoid, not yet hit in practice.

**Standing tension, not yet resolved by the user**: CLAUDE.md says "identifiers:
English," but every ground-truth doc (tickets, doc02, doc03 glossary, doc08 API
contract) already consistently uses French domain nouns (`Etablissement`, `uai`,
`valeur_ajoutee`, `sous_seuil_diffusion`...). Recommended in the plan: keep French
domain nouns for entity/field names (matches existing convention across all docs),
English for everything else. Flagged for explicit sign-off, not silently decided.

**`IngestionRun` is a new persisted concept beyond DATA-1's literal three entities**
(`Etablissement`, `IndicateurResultat`, `SourceReference`) — required by DATA-5's own
acceptance criteria (match-rate-drop alerting, snapshot-before-reimport), but not
named by DATA-1. Recommended as an `infrastructure/`-level concept (not `domain/`),
separate from `SourceReference` (which stays narrowly scoped to per-value F10
attribution). Flagged for sign-off in the plan handoff.

**Rollback mechanism recommended for DATA-5**: staging table + single-transaction
atomic rename swap (`etablissement_staging` → `etablissement`, previous renamed to
`etablissement_previous`), not pg_dump/restore. Appropriate at ~9MB per the spike's
own volume finding; gives free, cheap manual rollback via a second rename.
