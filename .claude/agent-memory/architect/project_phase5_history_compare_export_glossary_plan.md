---
name: project-phase5-history-compare-export-glossary-plan
description: Phase 5 (FE-4/API-7, FE-5/API-8, FE-6/API-9, FE-7/API-10) plan — data-availability findings, chart/compare/export/glossary architecture decisions, doc conflicts found
metadata:
  type: project
---

Plan produced 2026-08-17 for Phase 5. Backend/frontend both closed out of
Phase 4 (525 back / 46 front tests green, CORS already fixed — see
[[project_phase4_frontend_mvp_plan]]). This memory records what isn't already
obvious from re-reading the tickets/contract, so a future session doesn't
redo this investigation.

## Good news: no new ingestion needed for history or compare
`IndicatorReader.list_for_establishment` (`back/src/infrastructure/persistence/queries.py`)
already returns every `IndicatorResult` row (all years, all three
`IndicatorType`s) with every field the fact sheet uses. History (API-7) and
compare (API-8) are both buildable purely from existing reads — no DATA-layer
ticket, no new column, no schema-mismatch test needed for *this* reason (the
schema-mismatch test is still mandatory for any *new ingestion* work, of
which there is none here).
`_to_result_row` in `get_establishment_fact_sheet.py` should be extracted to
a shared, public helper so `GetEstablishmentHistory` and `CompareEstablishments`
reuse it instead of re-deriving `Figure`/`expected_rate` logic a second time.

## F5 history chart: hand-rolled inline SVG, not a charting library
`front/package.json` has exactly 3 runtime deps (react, react-dom,
react-router-dom); `docs/04_Journal_Decisions.md`'s 2026-08-16 entry already
rejected MUI specifically because "ses primitives de mise en avant, badges et
notations sont à une propriété près d'enfreindre la charte" — the same
argument applies to any off-the-shelf charting lib (Chart.js/Recharts/Victory
default to smoothed curves, tooltips, and trend affordances that fight
charter §10's "aucune courbe de projection" / "aucune interprétation de
tendance"). Decision: hand-rolled SVG, so gaps in the `<path>` d-string are
literal (a missing year breaks the polyline instead of being interpolated),
a rupture year renders as two disconnected path segments plus a visible
annotation (not a dashed "guess" line), and there is no library default to
override. Cost is more implementation work for one component; accepted,
matches the project's stated dependency-minimalism.
**A mandatory equivalent `<table>` ships beside every chart** (charter §10),
built from the same data array so it cannot drift from what the SVG shows.

## F4 comparison: the backend aligns rows by year — the frontend never zips two fact sheets itself
`docs/08_API_Contract.md`'s current sketch (`{ establishments: [sheetA,
sheetB] }`) is rejected as the shape to build: handing the frontend two raw
fact sheets invites it to zip/diff them at render time, which is exactly the
"écart global" charter §11 forbids computing. Decision (mirrors how `Figure`
structurally forbids a `variant` prop): the compare endpoint returns rows
**pre-aligned by year on the server**, each row carrying one cell per
compared establishment; a year present for one establishment and absent for
another is a distinct absence reason from a null figure inside a published
row (see next point). This is a contract change from the doc08 sketch and
needs `docs-sync-checker` + explicit doc08 update. Frontend reuses the
existing `<Figure>` component unmodified for every cell — comparison gets "no
highlighting, same visual weight" for free because it is literally the same
component with no `winner`/`highlight` prop to add, not a new one that has to
independently earn that guarantee.

## New absence variant needed: "no row for this establishment/year" vs "no value in a published row"
`ABSENT_VALUE` (`valeur_non_disponible`) in `explanatory_content.py` explains
a null figure *within a row the source did publish*. Comparison introduces a
second, different absence: establishment A has no result row at all for a
year establishment B does have (e.g. IVAC's 2022–2025 window vs IVAL's
2012–2025, or an EREA vs a lycée GT). Conflating the two would misstate what
is known. Decision: new `ExplanatoryContent` entry (new editorial copy,
human-review gate) distinguishing "cet établissement n'a pas de résultat
publié pour cette année" from "cette valeur n'est pas publiée". Both must
read as neutral facts, never as a loss for the establishment lacking the row.

## Max compared establishments: doc conflict, went with 2
`docs/07_Backlog_Epics_Tickets.md` FE-5 says "two (max three)". Both
`docs/01_Vision_Produit.md` (F4: "Deux fiches en parallèle") and
`docs/13_Inventaire_Ecrans_Etats.md` §9 ("Deux établissements maximum", an
explicit acceptance criterion) and its mobile layout (fixed "valeur A" /
"valeur B" blocks, no third slot) say two. Plan built for `MAX_COMPARE = 2`
since two independent, detailed UX specs converge on it and nothing describes
a 3-up layout — flagged to the user as an open question, not silently
resolved.

## F9 glossary: backend-owned content, composed over `explanatory_content` rather than duplicated
Decision: `GET /glossary` is implemented (it's already an approved contract
endpoint), content lives in a new `back/src/domain/glossary_content.py`
following the exact `explanatory_content.py` pattern (frozen dataclass,
`content_id`, `version`, human-review gate). For the 5 concepts that already
have an `ExplanatoryContent` entry (valeur_ajoutee, taux_reussite, taux_acces,
taux_mention, taux_attendu), the glossary module **derives** its entry from
the existing one programmatically rather than re-authoring the text a second
time — avoids the "two texts to keep in sync" trap the project already hit
once (home-page scope reminder, `docs/04` 2026-08-16 entry) and only accepted
there because of a dedicated verbatim-test; better to not create the
duplication at all here. Only genuinely new terms (UAI, IVAC, IVAL, DEPP,
REP/REP+, ULIS, SEGPA, EREA, sections/filières...) get freshly authored
entries, sourced from `docs/03_Glossaire_Metier.md`'s raw material but
rewritten for a public reader (doc03 has dev-facing meta-commentary like
"Corrigé le 15/08/2026 (API-4)" not fit for end-user copy) — human review
still mandatory.

**Contract gap found:** doc08's current `/glossary` sketch (`{term,
definition}`) is too thin to build "clickable in context" against — no id to
address a term by, no source, no cross-links. Needs extending to something
like `{ id, terme, definition, exemple, source, termes_associes: [] }`
(French wire, matching the rest of doc08) before API-10 is implemented; flag
as a contract update, not a silent invention.

**"Clickable in context" mechanism:** not free-text scanning (fragile, and
fights the project's structured-copy model — `explanatory_content.py`'s
prose fields are plain strings and must stay that way, no injected markup).
Decision: a small `GlossaryTerm` wrapper component (same enforcement style as
`SourceLink`/`Figure`) used at the known, enumerable call sites where a
defined term already renders as a discrete value — indicator labels, the
`type_indicateur` badge, `identite.sections`/`identite.filieres` list items,
explanation panel titles. Auto-linking occurrences *inside* the free-prose
bodies of `explanatory_content.py`/`glossary_content.py` themselves is
explicitly out of scope for this phase — flagged, not silently attempted.

## F8 export/share: no new backend endpoint, client-side print stylesheet + copy-link
No PDF library exists anywhere in the stack; adding one (or a headless-
browser render service) would be a new dependency/subsystem the project has
consistently avoided (`back/pyproject.toml`'s "deliberately small" dependency
comment; CLAUDE.md's stance against new services), and a server-rendered PDF
template is a second surface that can drift from the reviewed, live fact
sheet — the same duplication risk flagged above for the glossary. Decision:
"export" = a print stylesheet (`@media print`) on the existing
`FactSheetPage` (and, by the same mechanism, the new comparison page, to
satisfy doc13 §9's "Un export conserve limites, années et sources" bullet
under the *comparison* acceptance criteria — doc12 §8 also lists
"partager/exporter" as a comparison action, so this is real scope, not
scope creep); "share" = a copy-link button for the already-stable
`/etablissements/{uai}` URL — no backend change needed, the URL is already
canonical and stable.

**Concrete implementation snag, not solvable by CSS alone:** `FactSheetPage`
only mounts one `ExplanationPanel` at a time (`openExplanation` state), so a
print stylesheet has nothing to reveal — a closed React panel has no DOM node
to show with `display: block`. The AC ("exported content includes F3/F6/F7/F10
in full, no shortened version") requires a real component change: a
print-only block that renders every explanation inline regardless of panel
state, sourced from the same `sheet.explications` map already on the page.

**Timestamp semantics chosen:** the shared link always shows the *current*
`derniere_synchronisation` when opened, not a frozen snapshot from
share-time — consistent with the product's append-only-by-year design (a
later sync only ever adds years, never rewrites one). Flagged as an explicit
interpretation, not a frozen point-in-time share, in case the product wants
stronger snapshot guarantees later.

## Sequencing decided
API-7 → FE-4 → API-10 → FE-7 → API-8 → FE-5 → FE-6/API-9 last (needs the
fact-sheet and comparison pages to already exist, and benefits from the
glossary component pattern being in place first). Full ordered task list
with file paths given to the user in the 2026-08-17 conversation, not
duplicated here since it's a task breakdown, not a standing decision.
