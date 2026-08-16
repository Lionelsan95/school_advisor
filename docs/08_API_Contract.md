# API Contract (draft — update as implementation reveals real constraints)

*This is a working contract, not a frozen spec. Update it whenever an endpoint's
real shape diverges from what's described here — keep it in sync rather than
letting it go stale (see the "outdated knowledge" warning in the project's
documentation practices).*

> **Implementation status (bounded-assistant checkpoint, 2026-08-15).** Live and matching
> this document: `GET /health`, `GET /establishments/search`,
> `GET /establishments/{uai}`, `GET /communes/search` and
> `POST /assistant/search`. Still target-shape only: `/history`, `/compare`
> and `/glossary` (Phase 5).
>
> The three live data-endpoint sections below were rewritten against the running code. Three
> groups of fields promised by the Phase 1 draft were **removed because no
> source publishes them** — see `docs/04_Journal_Decisions.md`:
> - `sous_seuil_diffusion` / `non_diffusion_reason` — no source states a reason
>   for a missing value (confirmed against the DEPP methodology, ticket API-4).
> - `taux_reussite_moyenne_academique` / `_nationale` — no per-establishment
>   academic or national average is published. `taux_reussite_attendu` replaces
>   them, flagged `calcule: true`.
> - `identity.effectif` / `annee_effectif` — absent from the directory dataset.
>
> Database columns are in English (`value_added_success`, `candidates_present`,
> …) while this contract's JSON is French. The mapping lives at the single
> serialization boundary, `back/src/interfaces/api/schemas.py`.

---

## Conventions

- All endpoints return JSON.
- Every indicator result row carries a `source` object (`dataset_id`, `url`,
  `derniere_synchronisation`, `date_publication`) — F10.
  If that reference is missing, the fact sheet is withheld with `503`; a
  successful response never contains an orphan numeric row or `source: null`.
- Establishment and commune search responses carry one mandatory top-level
  `source` for their official reference dataset. Missing search provenance
  withholds the complete result set with `503`.
- Every figure is an object, not a bare number:
  `{ "valeur", "calcule", "note_de_calcul", "explication_absence" }`.
  A value computed by the backend has `calcule: true` and a `note_de_calcul`;
  a value the source did not publish has `valeur: null` and an
  `explication_absence` pointing at a static content block. **No field
  attributes a row-specific cause** — no source publishes one (API-4).
- Every response concerning establishment results includes a top-level
  `rappel_de_portee` (F7) — never omitted.
- Establishment search accepts no caller-selected sort. Any of `sort`, `sort_by`,
  `sortby`, `order`, `order_by`, `orderby`, `tri` in the query string returns
  `400 Bad Request` with an explanatory message — the request is refused, not
  ignored. Search ordering is fixed by factual match, proximity and stable
  identity tie-breakers, and the applied ordering is echoed back in `tri`.
- Explanatory text is static versioned content addressed by `content_id`
  (`back/src/domain/explanatory_content.py`), never generated per request.

---

## `GET /health`

Basic liveness check.

```json
{ "status": "ok" }
```

---

## `GET /establishments/search`

**Query parameters** (all optional):
- `q` — UAI, establishment name, canonical-site commune or postcode
  (2–120 characters, including at least one letter or digit). Matching is
  case- and accent-insensitive for names and communes.
- `code_commune` — exact official commune code on the canonical site.
- `code_postal` — exact postcode on the canonical site.
- `lat`, `lng`, `rayon_km` — location filter. Must be supplied **together**;
  a partial set returns `400`. `rayon_km` is capped at 100.
- `type` — `college` | `lycee` | `erea` | `ecole` | `autre`
- `secteur` — `public` | `prive`. The directory publishes no
  sous-contrat/hors-contrat distinction, and ~2.9 % of rows leave the field
  empty; those are returned only when no `secteur` filter is applied.
- `filiere` — `generale` | `technologique` | `professionnelle`
- `limit` (1–100, default 20), `offset` (≥ 0)

**Ordering:** when `q` is present, deterministic match tiers are applied:
exact UAI, exact normalized establishment name, exact canonical commune or
postcode, establishment-name prefix, commune prefix, establishment-name
substring, then commune substring. Distance follows the match tier when a
location is supplied, then name/UAI stabilize ties. Without a location,
commune/name/UAI are the stable tie-breakers.
Without `q`, ordering is proximity when located and alphabetical otherwise.
Never by a result indicator — see the sort rule in Conventions.

**Result rows carry identity only, never a result figure.** Returning one here
would let a client sort or colour the list by it. Results live on the fact
sheet, one establishment at a time.

Establishments appear once each, represented by their canonical site (the
lowest `sequence`), so a multi-site UAI is not duplicated. Establishments with
no coordinates are excluded from a location-filtered search — they cannot be
placed, and a guessed position would be invented data.

**Response:**
```json
{
  "resultats": [
    {
      "uai": "0910001A",
      "nom": "Collège Example",
      "type": "college",
      "statut_public_prive": "public",
      "commune": "Étampes",
      "code_postal": "91150",
      "code_departement": "091",
      "filieres": ["generale", "technologique"],
      "latitude": 48.43,
      "longitude": 2.16,
      "distance_km": 1.24
    }
  ],
  "nombre_total": 1,
  "tri": "correspondance_puis_proximite",
  "filtres_appliques": {
    "q": "collège example",
    "code_commune": null,
    "code_postal": null,
    "type": "college",
    "secteur": null,
    "filiere": null,
    "latitude": 48.43,
    "longitude": 2.16,
    "rayon_km": 10,
    "limit": 20,
    "offset": 0
  },
  "source": {
    "dataset_id": "fr-en-annuaire-education",
    "url": "https://data.education.gouv.fr/explore/dataset/fr-en-annuaire-education/information/",
    "derniere_synchronisation": "2026-08-15T17:20:39.036978Z",
    "date_publication": null
  },
  "rappel_de_portee": "Ces indicateurs décrivent certains résultats scolaires. Ils ne mesurent pas l'ambiance, l'accompagnement quotidien, le bien-être des élèves ni l'adéquation avec un enfant."
}
```

`distance_km` is `null` when no location filter was applied. `tri` is
`"alphabetique"`, `"proximite"`, `"correspondance"` or
`"correspondance_puis_proximite"` — stated explicitly so a consumer never has
to infer the ordering, and so it is visible that neither option involves a
result.

**Errors:** `400` for a partial location, an invalid text query, or any sort
parameter. FastAPI returns `422` for a parameter outside its declared bounds
(e.g. `rayon_km=500`). Missing directory provenance returns `503` and no
results:

```json
{"detail":"Une référence de source nécessaire à cette recherche est indisponible. Les résultats ne sont pas publiés afin de ne pas présenter de données sans origine."}
```

---

## `GET /communes/search`

Searches the official commune reference ingested ahead of requests. It never
calls an external geocoder at request time.

- `q` is required (2–120 characters, including a letter or digit).
- `limit` is 1–20 (default 10).

Ordering is exact commune code, exact postcode, exact normalized name, name
prefix, name substring, then stable name/code tie-breakers. It is factual
lookup ordering, not establishment ranking. A centre may be `null`; coordinates
are never reconstructed from school locations.

```json
{
  "resultats": [{
    "code": "92022",
    "nom": "Chaville",
    "codes_postaux": ["92370"],
    "code_departement": "92",
    "latitude": 48.8091,
    "longitude": 2.191
  }],
  "source": {
    "dataset_id": "geo-api-gouv-communes",
    "url": "https://geo.api.gouv.fr/decoupage-administratif/communes",
    "derniere_synchronisation": "2026-08-15T20:00:00Z",
    "date_publication": null
  }
}
```

Missing commune-reference provenance returns the same neutral `503` shape as
establishment search and publishes no result. A semantically invalid `q`
returns `400`; missing or declared-bound-invalid parameters return FastAPI's
`422`.

---

## `GET /establishments/{uai}`

Returns the full fact sheet: identity, every published result year, the static
explanatory blocks, the scope disclaimer and source attribution.

**Errors:** `400` if the UAI is malformed (does not match `^[0-9]{7}[A-Z]$`),
`404` if it is well-formed but unknown, and `503` if a published result row
lacks its mandatory source reference. The distinction is deliberate: malformed
input, an unknown UAI, and a data-integrity failure are different answers.

The `503` response is static and neutral; the internal log carries the missing
dataset, UAI and year so the reference can be repaired without exposing those
details to the user:

```json
{
  "detail": "Une référence de source nécessaire à cette fiche est indisponible. La fiche n'est pas publiée afin de ne pas présenter de donnée sans origine."
}
```

**Response** (abridged — one result row shown of the 14 a lycée typically has):
```json
{
  "uai": "0800001S",
  "identite": {
    "nom": "Lycée Boucher de Perthes",
    "type": "lycee",
    "statut_public_prive": "public",
    "adresse": "1 rue Example",
    "code_postal": "80100",
    "commune": "Abbeville",
    "code_departement": "080",
    "filieres": ["generale", "technologique"],
    "sections": ["europeenne", "ulis"],
    "sites": [
      {
        "nom": "Lycée Boucher de Perthes",
        "adresse": "1 rue Example",
        "code_postal": "80100",
        "commune": "Abbeville",
        "code_commune": "80001",
        "latitude": 50.1026,
        "longitude": 1.8422
      }
    ]
  },
  "resultats": [
    {
      "annee": 2025,
      "type_indicateur": "IVAL_GT",
      "candidats_presents": 383,
      "taux_reussite":            { "valeur": 94.0, "calcule": false, "note_de_calcul": null, "explication_absence": null },
      "taux_reussite_attendu":    { "valeur": 97.0, "calcule": true,  "note_de_calcul": "Calculé par ce service : taux constaté − valeur ajoutée. La source publie les deux termes, pas leur différence.", "explication_absence": null },
      "valeur_ajoutee_reussite":  { "valeur": -3.0, "calcule": false, "note_de_calcul": null, "explication_absence": null },
      "taux_acces":               { "valeur": 79.0, "calcule": false, "note_de_calcul": null, "explication_absence": null },
      "valeur_ajoutee_acces":     { "valeur": -8.0, "calcule": false, "note_de_calcul": null, "explication_absence": null },
      "taux_mention":             { "valeur": 61.0, "calcule": false, "note_de_calcul": null, "explication_absence": null },
      "valeur_ajoutee_mention":   { "valeur": -2.0, "calcule": false, "note_de_calcul": null, "explication_absence": null },
      "source": {
        "dataset_id": "fr-en-indicateurs-de-resultat-des-lycees-gt_v2",
        "url": "https://data.education.gouv.fr/explore/dataset/fr-en-indicateurs-de-resultat-des-lycees-gt_v2/information/",
        "derniere_synchronisation": "2026-08-15T17:20:39.036978Z",
        "date_publication": "2026-04-03"
      }
    }
  ],
  "explications": {
    "valeur_ajoutee":        { "content_id": "valeur_ajoutee", "version": 1, "titre": "Valeur ajoutée", "definition_simple": "…", "comment_lire": "…", "ce_que_cela_mesure": "…", "ce_que_cela_ne_mesure_pas": "…", "methode": "…", "source": "…" },
    "taux_reussite":         { "…": "…" },
    "taux_attendu":          { "…": "…" },
    "taux_acces":            { "…": "…" },
    "taux_mention":          { "…": "…" },
    "valeur_non_disponible": { "…": "…" }
  },
  "rappel_de_portee": "Ces indicateurs décrivent certains résultats scolaires. …",
  "derniere_synchronisation": "2026-08-15T17:20:39.036978Z"
}
```

**Absent figures (F6).** When a source published nothing, the figure is
`{"valeur": null, "explication_absence": "valeur_non_disponible"}` and the
matching block appears under `explications`. That block names the situations
the DEPP documents as possible causes and attributes **none** of them to this
row — no source publishes a per-row reason. A dependent computed figure is
absent too: `taux_reussite_attendu` needs both the observed rate and the value
added, and is never partially reconstructed.

Example, a real above-threshold-but-valueless case (UAI `9760127J`, Mayotte,
655 candidates in 2019):
```json
{
  "annee": 2019,
  "candidats_presents": 655,
  "taux_reussite":           { "valeur": 57.0, "explication_absence": null },
  "valeur_ajoutee_reussite": { "valeur": null, "explication_absence": "valeur_non_disponible" },
  "taux_reussite_attendu":   { "valeur": null, "explication_absence": "valeur_non_disponible" }
}
```

`explications` always contains the same six blocks, so a reader never sees an
indicator explained on one fact sheet and bare on another.
`derniere_synchronisation` includes the directory sync, so an establishment
with no indicator rows at all (a primary school) still reports when its
identity data was refreshed rather than looking like a broken pipeline.

---

## `GET /establishments/{uai}/history`

**Response:** array of yearly raw data points (used by F5), plus any
methodology break annotation identified in the technical spike.

```json
{
  "uai": "0910001A",
  "history": [
    { "annee": 2012, "valeur_ajoutee": 1.1 },
    { "annee": 2013, "valeur_ajoutee": 0.8 }
  ],
  "methodology_breaks": [
    {
      "year": 2021,
      "note": "Réforme du baccalauréat — voir docs/05_Resultats_Spike_Technique.md"
    }
  ]
}
```

*Updated after SPIKE-2 (2026-08-15).* The break year is **2021** (baccalauréat
reform), not 2019. It affects the per-stream sub-indicators only: the
total-level values this endpoint returns (`taux_reu_total`, `va_reu_total`,
`taux_acces_2nde`) are continuous over 2012–2025 and were verified identical
between the legacy and `_v2` datasets on every overlapping year.

Note the asymmetry in history depth, which is a property of the sources: IVAL
(lycées) covers 2012–2025, IVAC (collèges) only 2022–2025.

The exact `note` wording is static editorial content (F3/F6/F7) and requires
human review before commit — see `CLAUDE.md`, "Explanatory content change".

---

## `GET /establishments/compare?uai=A&uai=B`

**Response:** array of full fact sheets (same shape as
`GET /establishments/{uai}`), returned side by side with no computed
comparison score.

```json
{
  "establishments": [ /* fact sheet A */, /* fact sheet B */ ],
  "scope_disclaimer": "..."
}
```

---

## `GET /glossary`

```json
{
  "terms": [
    {
      "term": "Valeur ajoutée",
      "definition": "..."
    }
  ]
}
```

---

## `POST /assistant/search`

Bounded natural-language interpretation with no conversation or user-session
history. The backend retains only a bounded process-local cache of validated
structured interpretations; this is not a general chat or free-form answer
endpoint.

Request (one `requete` string, 1–500 wire characters):

```json
{ "requete": "collèges publics autour de Chaville" }
```

The response is one of three discriminated shapes:

- `etat: "resultats"` — `recherche` is exactly the existing
  `SearchResponseOut`, including its mandatory directory `source`, factual
  `tri`, `filtres_appliques` and `rappel_de_portee`. `lieu_resolu` contains one
  official commune or `null`; `source_lieu` contains its official provenance
  or `null`; `reformulation_neutre` contains the approved subjective-query
  recentering or `null`.
- `etat: "clarification"` — `type_clarification` is one of `lieu_requis`,
  `lieu_inconnu`, `lieu_ambigu`, `centre_indisponible`; `question` is one
  approved static question; `options` contains only official commune matches;
  `source` contains commune provenance when a lookup occurred, otherwise
  `null`; `reformulation_neutre` is nullable.
- `etat: "indisponible"` — HTTP `200` with the approved static `message`. Only
  optional language interpretation is unavailable; the structured endpoints
  remain accessible.

Version-1 assistant content, explicitly human-approved on 2026-08-15:

1. « Ce service ne classe pas et ne recommande pas les établissements. La
   demande est limitée à des critères factuels sans ordre fondé sur les
   résultats. »
2. « Autour de quelle commune souhaitez-vous effectuer la recherche ? »
3. « Quelle commune officielle souhaitez-vous utiliser pour cette recherche ? »
4. « Plusieurs communes correspondent. Laquelle souhaitez-vous utiliser ? »
5. « Le référentiel officiel ne publie pas de centre pour cette commune.
   Souhaitez-vous préciser une autre commune ? »
6. « L'interprétation en langage naturel n'est pas disponible. La recherche
   structurée reste accessible. »

`ASSISTANT_CONTENT_VERSION = 1` is repository metadata and is not currently a
wire field. Provider output is never displayed.

### Interpretation rules

- UAI, five-digit postcode and simple identity text bypass Anthropic. Complex
  or subjective requests use the optional bounded interpreter.
- Exact-commune mode produces `code_commune`. Explicit proximity resolves the
  official commune centre and defaults to 10 km if no radius is stated.
  Coordinates and absent centres are never guessed.
- Missing or ambiguous places produce exactly one clarification question.
- Every populated provider-produced search filter must have independent lexical
  support in the original request; `location_mode` and `needs_location=true`
  additionally require supported exact-location or proximity markers.
  Unsupported or malformed fields, a missing
  key, timeout/provider error, or any response other than exactly one valid
  tool call returns `indisponible` before factual search.
- Subjective requests retain only supported factual criteria and return the
  approved recentering. No result-based order, score or recommendation is
  added.
- In the monolith, the orchestrator reuses the same validated commune and
  establishment application cases and serialization schemas as the REST
  endpoints. There is no self-HTTP loopback; the provider receives no
  repository, database connection or factual result.

### Interpretation cache

Caching changes no request/response shape and exposes no cache-hit indicator.
The opaque key combines the accent/case/whitespace-normalized query, interpreter
identity and source/editorial version token. Anthropic identity includes
provider, model, prompt version and the closed tool-schema digest. Defaults are
256 entries and 900 seconds, configurable through
`ASSISTANT_CACHE_MAX_ENTRIES` and `ASSISTANT_CACHE_TTL_SECONDS`.

Only structured intent that passed application validation is cached. Commune
resolution, establishment search and provenance checks execute on every
request; provider failures and invalid interpretations are never stored.
Source-reference/editorial/provider/model/prompt-version/schema changes yield a
new key; old entries age out by TTL/LRU. The cache is per process, cold on restart, and adds
no Redis, cross-worker sharing or single-flight. Simultaneous cold misses can
therefore duplicate a provider call without changing the result contract.

### Errors

- A whitespace-only application query returns `400`.
- A missing field, empty wire string or string longer than 500 characters is
  rejected by request validation with `422`.
- Missing directory or commune provenance returns the same neutral `503`
  integrity error as the deterministic endpoints; the full factual answer is
  withheld.
