# API Contract (draft — update as implementation reveals real constraints)

*This is a working contract, not a frozen spec. Update it whenever an endpoint's
real shape diverges from what's described here — keep it in sync rather than
letting it go stale (see the "outdated knowledge" warning in the project's
documentation practices).*

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
      "year": 2019,
      "note": "Changement de méthode de calcul — voir docs/05_Resultats_Spike_Technique.md"
    }
  ]
}
```

*(This endpoint's exact shape depends on SPIKE-2 findings — update once the
technical spike is done.)*

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
