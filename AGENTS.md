# Codex project instructions

## Authority and required context

`CLAUDE.md` remains the canonical project handbook shared with Claude Code.
Read it completely before changing application code, then read the reference
documents it routes to for the task at hand. In particular:

- Check `docs/04_Journal_Decisions.md` before proposing a structural choice.
- Check `docs/05_Resultats_Spike_Technique.md` before changing ingestion,
  source-field mappings, UAI joins, or historical indicators.
- Check `docs/07_Backlog_Epics_Tickets.md` and
  `docs/06_Implementation_Roadmap.md` before claiming a ticket or phase is
  complete.
- Check `docs/08_API_Contract.md` when an API or persisted data shape changes.
- Apply `docs/09_Definition_of_Done_Quality_Gates.md` to completed work.

If documents disagree, the non-negotiable neutrality principle below wins.
Flag other contradictions instead of silently choosing one version.

## Current recovery state

Phase 1 is an interrupted Claude Code implementation, not a clean starting
point. Preserve all pre-existing tracked and untracked work. Do not replace the
backend wholesale, discard files, or rewrite decisions merely to make the tree
look clean. Before implementation, inspect `git status`, the current code, its
tests, and `.claude/agent-memory/architect/project_phase1_data_layer_plan.md`.

Work one independently testable ticket or stabilization slice at a time. Keep
review and validation inside the same slice, and report a checkpoint before
starting the next one. Do not advance to Phase 2 until every Phase 1 exit
criterion has evidence.

## Non-negotiable product rules

The tool explains; it never judges.

- Never add rankings, scores, recommendations, "best school" behavior, or
  result-based ordering, filtering, colors, badges, or emphasis.
- Never infer a reason for missing official data when the source does not
  publish one. In particular, do not derive non-diffusion from candidate count.
- Explanations and disclaimers are static, versioned editorial content. An LLM
  must not generate them freely at request time.
- Every displayed fact must be traceable to official source data, a documented
  deterministic calculation, or approved versioned editorial content.
- Historical indicator rows are append-only. Never overwrite a prior year.

## Architecture and implementation boundaries

- Keep the Python backend hexagonal: `domain` has no framework or
  infrastructure imports; `application` depends on domain and ports;
  infrastructure implements ports; HTTP interfaces remain thin.
- Keep one backend service and PostgreSQL/PostGIS. Do not add queues,
  microservices, NoSQL, or Elasticsearch without a documented observed need.
- Use English for code, comments, identifiers, and commit messages. Preserve
  French wire-format names only where the published API contract requires them.
- Use type hints throughout Python. Run pytest, Ruff, and strict mypy checks.
- Any ingestion/source change must include a test simulating upstream schema
  mismatch and must fail visibly rather than publishing partial or silently
  corrupted data.
- `docs/04_Journal_Decisions.md` is append-only in spirit. Do not rewrite old
  entries without explicit user authorization.
- Treat the findings in `docs/05_Resultats_Spike_Technique.md` as measured
  ground truth. Flag contradictory new evidence; do not overwrite it silently.

## Codex subagent workflow

Use the project-scoped custom agents in `.codex/agents/` when available. If a
named custom agent is unavailable, delegate the same bounded role using a
built-in subagent and the instructions in this file. Keep write ownership with
the main thread except for `debugger` and `test_writer`, and never run multiple
write-heavy agents concurrently on overlapping files.

### Small edit

Main thread implements -> `code_improver` reviews -> main thread fixes review
findings, or `debugger` handles a genuine bug -> `test_writer` adds meaningful
coverage -> `test_runner` runs the relevant and full checks ->
`neutrality_checker` reviews user-facing effects -> `docs_sync_checker` checks
documentation -> main thread makes required documentation corrections ->
`secret_scanner` checks the final diff -> `commit_writer` proposes a message.

### Large feature or refactor

`architect` plans from the current repository -> main thread implements one
plan slice -> follow the complete small-edit review chain for that slice.

### Bug fix

`debugger` reproduces and fixes the root cause -> `test_writer` adds a
regression test -> `test_runner` verifies -> `secret_scanner` checks the diff ->
`commit_writer` proposes a message.

### Data-source or ingestion change

`architect` reviews the change against the architecture and spike findings ->
main thread implements -> `test_writer` adds normal, edge, and mandatory
schema-mismatch coverage -> `test_runner` verifies -> `docs_sync_checker`
checks the API contract and data-model documentation -> `secret_scanner` checks
the diff -> `commit_writer` proposes a message.

### Explanatory-content change

Main thread proposes content -> stop for explicit human review and approval ->
`neutrality_checker` reviews the approved text -> `test_runner` runs
content-consistency tests -> `docs_sync_checker` checks synchronization ->
`commit_writer` proposes a message. No agent may bypass the human approval step.

### Dependency maintenance

`dependency_auditor` reports evidence -> main thread makes approved adjustments
-> `test_runner` verifies -> `secret_scanner` checks -> `commit_writer` proposes
a message.

### Documentation-only change

`docs_sync_checker` reviews -> main thread corrects -> `commit_writer` proposes
a message.

Subagents return evidence and findings to the main thread. The main thread owns
the final decision, resolves conflicts, runs any required re-checks, and gives
the user a self-contained handoff. Do not create a Git commit unless the user
explicitly asks for one; `commit_writer` only proposes the message.

## Validation commands

Run backend checks in the reproducible backend environment when practical:

- `pytest`
- `ruff check .`
- `ruff format --check .`
- `mypy src`

Use Docker Compose or an equivalent isolated PostgreSQL instance for migration,
repository, and ingestion integration tests. Never claim a live-source or
fresh-database criterion passed without actually observing it.
