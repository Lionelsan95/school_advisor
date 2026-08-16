---
name: project-phase4-frontend-mvp-plan
description: Phase 4 (FE-1/FE-2/FE-3) frontend plan — stack picks, CORS gap found, API-vs-UX-doc gaps, neutrality-as-structure approach
metadata:
  type: project
---

Plan produced 2026-08-16 for Phase 4 — Frontend MVP (FE-1 search, FE-2 fact
sheet, FE-3 scope disclaimer). `front/` was empty at the time; backend
(Phases 0-3) closed, 518 tests green, live endpoints: `/establishments/search`,
`/establishments/{uai}`, `/communes/search`, `/assistant/search`.

**Why this matters for future sessions:** several gaps found here are easy to
silently "fix" the wrong way (by inventing data or ranking) if rediscovered
without this context.

## Stack decision (recommended, not yet implemented at plan time)
TypeScript + React Router + a small custom `useApiResource` fetch hook (no
React Query/SWR) + plain CSS Modules (no Tailwind/MUI). Justification: solo
maintainer, CLAUDE.md's explicit stance against premature complexity, and the
data-fetching need here is simple (no optimistic updates, no complex cache
invalidation — the backend already owns caching via AGENT-4). Vitest +
Testing Library for unit/component tests (project already uses pytest-style
"fast, no network" unit layer on the backend; Vitest is the direct analogue).
Playwright deferred to Phase 5/6 unless a screen becomes hard to verify any
other way.

## Decision: CORS is not configured anywhere in the backend — fix in the backend, not with a dev proxy
`back/src/interfaces/api/main.py` has no `CORSMiddleware`. Confirmed live by
the coordinator: `OPTIONS /establishments/search` from `Origin:
http://localhost:5173` → 405, `GET /health` from that origin → no
`access-control-*` headers. A browser served by Vite on :5173 cannot call
:8000 as `docker-compose.yml`'s `VITE_API_BASE_URL=http://localhost:8000`
implies.

**Chosen: add `CORSMiddleware` to the backend, origins from a new
`cors_allowed_origins` setting** (comma-separated env var,
`back/src/infrastructure/settings.py`, default `http://localhost:5173`,
documented in `.env.example`) — a small **CORS-1 backend ticket**, sequenced
first in Phase 4, explicitly not silently folded into "frontend work."

**Rejected: Vite dev-server `server.proxy`.** It would need to target the
compose service name (`http://backend:8000`), not `localhost:8000`, since the
frontend itself runs in a container with no host networking shortcut — one
more layer of indirection. It also only fixes dev: the built production
bundle has no dev server to proxy through, so production still needs real
CORS or a reverse proxy in Phase 6 (OPS-1/OPS-2) regardless. Choosing the
proxy now means solving the same problem twice, with the frontend behaving
differently (same-origin in dev, cross-origin in prod) — exactly the kind of
environment divergence this project's Settings pattern (`DATABASE_URL` has no
default, `ods_base_url`/`geo_api_base_url` do) is designed to avoid. The
`CORSMiddleware` fix is idiomatic here in one place, in every environment.

**Consequence for the API client:** the frontend's fetch client always reads
an absolute `import.meta.env.VITE_API_BASE_URL` and calls it directly — no
relative-path/same-origin trick, no environment-conditional base URL logic.

**`docker-compose.yml`: keep the `frontend` service definition exactly as-is**
(`Dockerfile.dev`, `./front:/app` + anonymous `/app/node_modules`, port 5173,
`command: npm run dev -- --host`, `VITE_API_BASE_URL=http://localhost:8000`).
No compose changes needed on the frontend side. The only compose-adjacent
change is documenting `CORS_ALLOWED_ORIGINS=http://localhost:5173` in
`.env.example` for the backend (it already has a safe code default so a bare
checkout still works without editing `.env`).

**Tooling constraint carried into the task list:** the host has no node/npm
(only Docker) — node:22-alpine, host uid:gid 1000:1000 matching the image's
`node` user. All scaffolding and `npm` commands must run inside a container
(`docker run --rm -v $(pwd)/front:/app -w /app -u 1000:1000 node:22-alpine
...` before `Dockerfile.dev` exists, `docker compose run --rm frontend npm
...` after).

**CI:** add a new `.github/workflows/frontend.yml` job in Phase 4 itself
(lint + Vitest + build), mirroring `backend.yml`'s pattern and the same bar
Phase 3 held itself to (CI evidence required, not just a workflow file) —
not deferred to a later phase.

## Contract-vs-UX-doc gaps (do not silently invent data to fill these)
1. **Search result cards** (`docs/12_Architecture_Information.md` §4, and
   `docs/13_Inventaire_Ecrans_Etats.md` R-acceptance for E02) ask for "année la
   plus récente disponible" and "état de disponibilité des indicateurs" on
   each result card. `08_API_Contract.md` is explicit that
   `/establishments/search` result rows "carry identity only, never a result
   figure" — by design, so a client can never sort/colour the list by it. The
   two UX docs' own status banners already flag this as a target need, not a
   present capability. **Do not fetch per-row fact sheets from the search
   list to backfill this** (N+1, and re-introduces exactly the "figure in the
   list" pattern the API deliberately avoids) — this is a backend product
   decision (a non-evaluative "dernière année disponible" field on the search
   row) that belongs to a Phase 5-or-later API ticket, not Phase 4 frontend
   scope.
2. **Comparison across UX docs §8** (side-by-side, `/comparaison?uai=A,B`) is
   Phase 5 (FE-5/API-8) per `07_Backlog_Epics_Tickets.md`. Phase 4's IA doc
   mentions "Ajouter à la comparaison" as an action on result cards/fact
   sheets — build the UI affordance (add/remove from a client-side comparison
   selection, e.g. local state or `localStorage`) but the actual comparison
   screen is out of Phase 4 scope; route it to a placeholder or defer the
   button until FE-5 depending on user preference (flagged as open question).
3. `GET /establishments/{uai}/history`, `/compare`, `/glossary` are still
   target-shape only (Phase 5) — FE-2's fact sheet must not build a history
   chart or glossary links against them yet.

## Structural neutrality enforcement approach
Central `<Figure>` component is the only way any screen renders a numeric
result; it takes the API's `FigureOut`-shaped prop
(`{valeur, calcule, note_de_calcul, explication_absence}`) and a
`sourceRef`, never a raw number + a caller-chosen colour. It has no `variant`
prop that maps to good/bad. Absence is rendered by branching internally on
`explication_absence` (looked up against the `explications` block already
returned by the API — never a frontend-authored string). No sort/filter
UI control may be wired to a numeric field — enforced by only ever accepting
`SearchHitOut`-shaped data (which the API guarantees carries no figure) as
list input. Full component API proposal is in the plan delivered to the user
on 2026-08-16 (see conversation), not duplicated here since it's implementation
detail, not a standing decision.

## New user-facing French copy needing human sign-off
Any label the API contract does not itself supply (headings, button text like
"Ajouter à la comparaison", "Voir la fiche", the search field placeholder,
error banner titles) is new static content and falls under the F3/F6/F7
explanatory-content workflow in CLAUDE.md — human review required before
commit, `neutrality-checker` after. Listed explicitly in the plan delivered
2026-08-16 so they can be reviewed as a batch rather than discovered piecemeal
during implementation.
