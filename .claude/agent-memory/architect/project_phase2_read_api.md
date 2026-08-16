---
name: phase2-read-api
description: Architecture decisions and data-layer gaps found while planning Phase 2 (API-1..API-6, core read API) on 2026-08-15
metadata:
  type: project
---

Planned Phase 2 (`GET /establishments/{uai}`, `GET /establishments/search`,
static content, disclaimer, source attribution) on 2026-08-15. Key findings a
future session should not have to re-derive from scratch:

**Gaps between `docs/08_API_Contract.md` and what Phase 1 actually ingested**
(confirmed by reading `back/alembic/versions/0001_initial_schema.py`,
`back/src/infrastructure/ingestion/indicator_adapter.py` and
`back/src/infrastructure/ingestion/directory_adapter.py`):
- `sous_seuil_diffusion` / `non_diffusion_reason` — already known-wrong per
  ticket API-4, no column, no source field.
- `taux_reussite_moyenne_academique` / `taux_reussite_moyenne_nationale` in
  the fact-sheet example — **newly found**, not previously flagged anywhere.
  No such field is ingested or mapped in `IndicatorDatasetSpec`; `indicator_result`
  has no columns for an academic/national reference rate, only the
  establishment's own `success_rate`/`access_rate`/`mention_rate` and their
  `value_added_*` counterparts (which already express the observed-vs-expected
  comparison). Recommendation: drop the two `*_moyenne_*` fields from the
  contract; "results with comparison averages" (API-1 wording) is satisfied by
  the `value_added_*` fields, not by raw peer-average rates.
- `identity.filieres`, `sections`, `effectif`, `annee_effectif` — not in the
  `establishment` table and not read by `DirectoryAdapter` (`DIRECTORY_FIELDS`
  is a fixed 13-field list that excludes them). Recommendation: drop from the
  contract for Phase 2; reintroducing them would require reopening DATA-3,
  out of Phase 2's gated scope.
- `source_reference` table exists in the 0001 migration but **nothing ever
  writes to it** — grepped `back/src` for `source_reference`/`SourceReference`,
  only the domain dataclass definition matches. API-6 (source attribution)
  cannot be built until ingestion is extended to upsert one row per
  `dataset_id` (4 datasets: directory + IVAC + IVAL_GT + IVAL_PRO) with
  `last_synchronised_at` and, if the ODS catalog metadata exposes it,
  `source_published_at`. This is a Phase 1 completeness fix surfaced during
  Phase 2 planning, not a new Phase 2 feature — recommend doing it as its own
  early commit/ticket before the API-6 serializer work.

**Layering decisions made for this plan** (not yet implemented — see the full
plan given to the user on 2026-08-15 for the exact task breakdown):
- Read-side ports are new, separate `Protocol`s in `application/ports.py`
  (e.g. `EstablishmentReader`, `IndicatorReader`, `SourceReferenceReader`),
  implemented by new adapters in a new `infrastructure/persistence/queries.py`
  — kept apart from `repositories.py`, which stays ingestion/write-only. Read
  and write are different bounded contexts even though they hit the same
  tables.
- Static explanatory content (API-3) and the scope disclaimer (API-5) live in
  `src/domain/explanatory_content.py` as frozen dataclasses in a
  `content_id -> ExplanatoryContent` dict, per CLAUDE.md's explicit pointer
  ("See `src/domain/` for where this content should live"). Chosen over
  YAML/JSON or a DB table: mypy-strict catches key typos at import time, git
  diffs stay reviewable (matters for the mandatory human-review workflow), no
  migration/admin-UI is needed for a solo maintainer, and it matches the
  existing domain-layer style (`enums.py`, `indicator_result.py`).
- English DB columns -> French JSON mapping happens only at the
  `interfaces/api` serialization boundary (Pydantic response models with
  French aliases or an explicit serializer function), per the existing journal
  entry "Identifiants de code en anglais, format JSON en français" — domain
  and application stay English/source-label internally.
- Location search: no new PostGIS geometry column. `site.latitude`/`longitude`
  stay plain `Float`; add a composite btree index
  `(latitude, longitude)` for a bounding-box pre-filter, then compute exact
  distance with `ST_DistanceSphere`/`ST_MakePoint` cast inline (postgis
  extension is already enabled in migration 0001, just unused). Search
  matches against the *canonical* site only (`sequence` lowest) — annexe
  sites share the parent's coordinates per the spike's documented caveat in
  `Site`'s docstring, so searching every site would only add duplicate,
  non-precise matches.
