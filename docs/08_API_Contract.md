# API Contract (draft — update as implementation reveals real constraints)

*This is a working contract, not a frozen spec. Update it whenever an endpoint's
real shape diverges from what's described here — keep it in sync rather than
letting it go stale (see the "outdated knowledge" warning in the project's
documentation practices).*

> **Implementation status (end of Phase 1, 2026-08-15): only `GET /health`
> exists.** Everything else below is the Phase 2+ target shape, not a live
> endpoint. The data layer behind them is in place and populated.
>
> Note for Phase 2: the database columns are in English (`value_added_success`,
> `candidates_present`, …) while this contract's JSON stays French. The mapping
> belongs at the serialization boundary — see `docs/04_Journal_Decisions.md`.

---

## Conventions

- All endpoints return JSON.
- All numeric data points that come from an official source include a
  `source` object with `url` and `published_at`.
- Any value computed by the backend rather than copied from a source includes
  `computed: true` and a `computation_note` explaining the calculation.
- Every response that concerns establishment results includes a top-level
  `scope_disclaimer` field (F7) — never omitted.
- No endpoint accepts a `sort_by=results` or equivalent quality-based sort
  parameter. Requesting one returns `400 Bad Request`.

---

## `GET /health`

Basic liveness check.

```json
{ "status": "ok" }
```

---

## `GET /establishments/search`

**Query parameters:**
- `lat`, `lng`, `radius_km` — location filter (optional but typically used together)
- `type` — `college` | `lycee` | ... (per directory dataset values)
- `sector` — `public` | `prive_sous_contrat` | `prive_hors_contrat`
- `filiere` — optional, e.g. `generale`, `technologique`, `professionnelle`
- `limit`, `offset` — pagination

**Default sort:** proximity if `lat`/`lng` provided, else alphabetical by
commune then name. Never by result indicators.

**Response:**
```json
{
  "results": [
    {
      "uai": "0910001A",
      "nom": "Collège Example",
      "type": "college",
      "statut_public_prive": "public",
      "commune": "Étampes",
      "code_postal": "91150",
      "latitude": 48.43,
      "longitude": 2.16
    }
  ],
  "total_count": 1,
  "filters_applied": {
    "location": { "lat": 48.43, "lng": 2.16, "radius_km": 10 },
    "type": null,
    "sector": null,
    "filiere": null
  }
}
```

---

## `GET /establishments/{uai}`

**Response:**
```json
{
  "uai": "0910001A",
  "identity": {
    "nom": "Collège Example",
    "type": "college",
    "statut_public_prive": "public",
    "adresse": "1 rue Example",
    "code_postal": "91150",
    "commune": "Étampes",
    "filieres": ["generale"],
    "sections": ["ULIS"],
    "effectif": 450,
    "annee_effectif": 2025
  },
  "results": [
    {
      "annee": 2024,
      "type_indicateur": "IVAC",
      "taux_reussite": 91.2,
      "taux_reussite_moyenne_academique": 88.5,
      "taux_reussite_moyenne_nationale": 87.9,
      "valeur_ajoutee": 2.3,
      "sous_seuil_diffusion": false,
      "non_diffusion_reason": null,
      "source": {
        "url": "https://data.education.gouv.fr/...",
        "published_at": "2025-04-03"
      }
    },
    {
      "annee": 2023,
      "type_indicateur": "IVAC",
      "taux_reussite": null,
      "valeur_ajoutee": null,
      "sous_seuil_diffusion": true,
      "non_diffusion_reason": "Effectif inférieur au seuil de fiabilité statistique (20 candidats en filière générale/technologique, 10 en filière professionnelle).",
      "source": {
        "url": "https://data.education.gouv.fr/...",
        "published_at": "2024-01-26"
      }
    }
  ],
  "explanations": {
    "valeur_ajoutee": "La valeur ajoutée compare les résultats obtenus par les élèves de cet établissement à ceux attendus statistiquement, compte tenu de leur profil scolaire et social à l'entrée. [...]"
  },
  "scope_disclaimer": "Ces données portent uniquement sur les résultats scolaires officiels. Elles ne renseignent pas sur l'ambiance, la vie scolaire, l'encadrement au quotidien ou d'autres critères propres à votre situation.",
  "last_updated": "2025-04-03"
}
```

> ⚠️ **`non_diffusion_reason` — wording above is PROVISIONAL and must not be
> implemented as-is.** The example attributes the absence to the effectif
> threshold, which SPIKE-3 showed to be wrong in a notable share of cases (457
> IVAL GT rows above the threshold have no value, 113 of them in Mayotte where
> it is not computed at all). The response must distinguish at least a value
> the source reports as *not published* from one that is simply *not available*
> with no stated reason.
>
> The replacement wording is F6 static editorial content and requires the human
> review step defined in `CLAUDE.md` ("Explanatory content change") before it is
> written here or in code. Tracked as ticket API-4, blocked on confirming the
> DEPP threshold semantics. See `05_Resultats_Spike_Technique.md`, section 3.

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

## Conversational endpoint (Phase 3, shape TBD)

Not fully specified yet — depends on the LLM integration approach chosen in
Phase 3 (e.g. a streaming chat endpoint vs. a structured query endpoint).
Update this section once AGENT-1 is implemented. At minimum it must:
- Only call the endpoints above for factual data (no direct DB access).
- Return the same `scope_disclaimer` and `source` structures as the REST
  endpoints, not free-form uncited text.
