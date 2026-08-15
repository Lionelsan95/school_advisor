---
name: reference-ods-data-sources
description: Gaps and behavior of the Opendatasoft/data.education.gouv.fr sources not covered in docs/03_Glossaire_Metier.md
metadata:
  type: reference
---

**RESOLVED 2026-08-15 by the executed spike.** All dataset ids are now recorded in
`docs/03_Glossaire_Metier.md` ("Sources API techniques") and in
`scripts/spike/ods_client.py`:

| Role | dataset_id | Rows | Years |
|---|---|---|---|
| Directory | `fr-en-annuaire-education` | 67 896 | — |
| IVAC (collèges) | `fr-en-indicateurs-valeur-ajoutee-colleges` | 26 869 | 2022–2025 |
| IVAL GT | `fr-en-indicateurs-de-resultat-des-lycees-gt_v2` | 32 485 | 2012–2025 |
| IVAL PRO | `fr-en-indicateurs-de-resultat-des-lycees-pro_v2` | 28 258 | 2012–2025 |
| IVAL GT legacy | `fr-en-indicateurs-de-resultat-des-lycees-denseignement-general-et-technologique` | 27 808 | 2012–2023 |
| IVAL PRO legacy | `fr-en-indicateurs-de-resultat-des-lycees-denseignement-professionnels` | 24 236 | 2012–2023 |

Catalog full-text search works as `?where="<term>"` (ODSQL string literal), not `?q=`.

**Pagination — corrected by execution.** `/records` is capped at 100 rows/page with an
offset ceiling, so it genuinely cannot page a full dataset. But the planned mitigation
(scope with `where` per département) is *not* the right answer: **`/exports/json` has no
offset ceiling and returns an entire dataset in one call** — 68k directory rows in ~4s.
Use `select=` to restrict columns.
How to apply: any full pull, in the spike or in the Phase 1 adapters, should use
`/exports/json`; reserve `/records` for aggregations (`group_by`) and small lookups.

**Gotcha:** the catalog *metadata* endpoint returns gzip even when the request sends
`Accept-Encoding: identity`, while `/records` and `/exports` honour it. Sniff the gzip
magic bytes (`\x1f\x8b`) rather than trusting response headers.

Outbound network access to `https://data.education.gouv.fr` was confirmed reachable (HTTP
200) from the architect's planning sandbox on 2026-08-15 — this does not guarantee the
execution environment (a different session/container) has the same access; spike code must
still fail loudly rather than fabricate results if unreachable.
