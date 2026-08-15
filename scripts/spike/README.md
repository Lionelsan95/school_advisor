# Phase 0 — technical spike scripts (DISPOSABLE)

**These scripts are not production code and must not be imported by `back/`.**

They exist to answer the three go/no-go questions of Phase 0
(see `docs/06_Implementation_Roadmap.md` and tickets SPIKE-1/2/3 in
`docs/07_Backlog_Epics_Tickets.md`) and to produce the written findings in
`docs/05_Resultats_Spike_Technique.md`.

The **deliverable of Phase 0 is that document**, not this code. Once Phase 1
implements the real ingestion adapters under
`back/src/infrastructure/ingestion/`, this directory can be deleted.

## Why these are not covered by pytest

`CLAUDE.md` requires a schema-mismatch test case for any data-source /
ingestion change. That gate targets the **Phase 1 production adapters**
(DATA-3/4/5), which run unattended and repeatedly against sources that can
drift silently. These scripts run once, by hand, and produce a dated report.

Instead of a test suite they carry **inline runtime assertions** (see
`ods_client.py` and each script's `check_*` calls): unexpected field names,
record counts or null rates abort the run loudly rather than producing a
quietly wrong number.

**This is explicitly not a substitute for the Phase 1 schema-mismatch test.**
See the entry recorded in `docs/04_Journal_Decisions.md`.

## Running

Requires network access to `data.education.gouv.fr` and Python 3 with
`requests` (already present on this machine; otherwise
`pip install -r requirements.txt`).

```bash
python3 scripts/spike/spike1_uai_join.py
python3 scripts/spike/spike2_ival_continuity.py

# SPIKE-3 additionally needs the local database:
docker compose up -d db
python3 scripts/spike/spike3_ingestion_prototype.py
```

Raw API payloads and generated reports land in `scripts/spike/output/`,
which is git-ignored — only the findings written into `docs/` are committed.
