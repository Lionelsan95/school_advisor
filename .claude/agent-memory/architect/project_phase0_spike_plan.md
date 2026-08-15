---
name: project-phase0-spike-plan
description: Plan and key methodology decisions for executing Phase 0 (SPIKE-1/2/3), given by the architect on 2026-08-15
metadata:
  type: project
---

**STATUS: the spike was EXECUTED on 2026-08-15. Verdict GO.** Results are in
`docs/05_Resultats_Spike_Technique.md`, which is now the ground truth — read it rather than
this plan. The notes below are kept for the methodology reasoning; where they differ from
what was actually done, the executed version is noted inline.

Repo was not a git repo yet and `back/`, `front/`, `scripts/` were empty at planning time;
the repo has since been initialised on `main`.

**Where spike code lives:** `scripts/spike/` (not `back/src/`), with raw pulled data
gitignored (**executed as `scripts/spike/output/`**, not `scripts/spike/data/`) and only
scripts + a written summary committed. This
keeps disposable spike code structurally separate from the hexagonal `back/src/` layout
mandated by CLAUDE.md.
Why: backlog SPIKE-1/2/3 tickets explicitly call the deliverable disposable, and CLAUDE.md
forbids polluting `domain/`/`application/`/`infrastructure/` with throwaway code.
How to apply: any future spike/prototype work (not just this one) should default to
`scripts/` rather than `back/src/`, unless it's graduating into a real Phase 1+ adapter.

**SPIKE-1 denominator methodology decided:** a naive match-rate over the whole directory
(~66k establishments of all levels) is meaningless because IVAC/IVAL only cover
collèges/lycées. The correct approach: (1) **executed nationally, not on one département** —
the full datasets fit in memory via `/exports/json` (68k directory rows pulled in ~4s), so
sampling was unnecessary and a borderline single-département rate would not have supported a
go/no-go; (2) filter to an "eligible population" = collège/lycée type, open/active
(exclude closed establishments), (3) treat a "match" as *any row existing* for that UAI in
IVAC/IVAL for a given year — even if `valeur_ajoutee` is null due to the non-diffusion
threshold, that still counts as a join success, not a miss (the threshold rule affects the
*value*, not row presence). (4) whether private hors-contrat establishments are
structurally absent from IVAC/IVAL is unknown and must be determined empirically by the
spike itself, not assumed. (5) sample ~15-20 of the actual misses and manually classify
into: below-threshold-but-in-dataset (not actually a miss), too-new-to-have-results
(legitimate), or genuine UAI mismatch (real join defect) — report all three counts, not
just one aggregate number.
Why: a wrong denominator would make the go/no-go threshold (90%, per
docs/02_Architecture_Decisions.md) meaningless in either direction.
How to apply: use this methodology when SPIKE-1 is actually executed or re-run; don't
recompute the denominator logic from scratch.

**docker-compose caveat at spike time:** `back/` and `front/` had no `Dockerfile.dev`, so
`docker compose up --build` (as documented in CLAUDE.md) would fail. For SPIKE-3's Postgres
prototype, only bring up the `db` service (`docker compose up -d db`). Re-check once Phase 1
(back Dockerfile) and Phase 4 (front Dockerfile) land — this caveat should disappear then.

**Test strategy decided:** CLAUDE.md's "never skip the schema-mismatch test case" rule
(data-source/ingestion workflow) applies to Phase 1 production adapters
(`back/src/infrastructure/ingestion/`, tickets DATA-3/DATA-4/DATA-5), not to Phase 0 spike
scripts. Spike scripts get lightweight inline runtime assertions/sanity checks (not pytest),
since the whole deliverable is a human-reviewed, dated written report
(`docs/05_Resultats_Spike_Technique.md`), not deployed/scheduled code. Record this
distinction explicitly in `docs/04_Journal_Decisions.md` when the spike is executed, so
nobody later assumes the schema-mismatch gate was already satisfied.
