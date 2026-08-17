# Deployment notes

*Written during Phase 6 (OPS-1 to OPS-4). **No hosting target has been chosen.**
This document deliberately does not invent one: it records what a target must
provide, what has been verified and what has not, so that choosing a host later
is a decision rather than a rediscovery.*

---

## What exists

| Image | File | Runs as | Port | Healthcheck |
|---|---|---|---|---|
| Backend | `back/Dockerfile` | `appuser` (uid 10001) | 8000 | `GET /health` via `urllib` |
| Frontend | `front/Dockerfile` | `nginx` (uid 101) | 8080 | `wget --spider /` |

`docker-compose.prod.yml` composes them. It carries an explicit
`name: etablissements-en-clair-prod` — without it Compose derives the project
name from the directory, shares a project with `docker-compose.yml`, and
recreates the development containers. That happened during Phase 6; it is not
hypothetical.

It has **no `db` service**, on purpose. The OPS-1 exit criterion is running
against a non-local database with no code changes, and omitting the service
makes that true by construction rather than by remembering to override a
variable.

```bash
export DATABASE_URL='postgresql://user:pass@host:5432/schools_db'
export VITE_API_BASE_URL='https://api.example.org'
export CORS_ALLOWED_ORIGINS='https://example.org'
docker compose -f docker-compose.prod.yml up --build -d
```

---

## Configuration a target must provide

Nothing below has a production-safe default. Anything with a default is a local
development convenience, and a deployment that relies on one is misconfigured.

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | **yes** | No default, by design. A missing value fails at startup rather than connecting to whatever is on localhost. |
| `VITE_API_BASE_URL` | **yes, at build time** | See the build-time constraint below. The build fails without it, and a bundle built without it throws at runtime rather than silently pointing at the visitor's own machine. |
| `CORS_ALLOWED_ORIGINS` | yes in practice | Comma-separated. Defaults to the Vite dev server, which is wrong everywhere else. Never `*`. |
| `LOG_FORMAT` | recommended | `json` in production; `text` (default) is for reading in a terminal. |
| `LOG_LEVEL` | no | Defaults to `INFO`. |
| `INGESTION_ENABLED` | no | Defaults to `false`. Set to `true` on **exactly one** instance — see below. |
| `INGESTION_HOUR_UTC` | no | Defaults to 3. |
| `ALERT_WEBHOOK_URL` | recommended | Where ingestion failures are announced. Without it, failures still log CRITICAL and still record an `ingestion_run` row — degraded, not broken. |
| `ANTHROPIC_API_KEY` | no | Without it the assistant returns its static "unavailable" message and every deterministic endpoint keeps working. |

### Secrets

`DATABASE_URL` and `ANTHROPIC_API_KEY` are secrets. `ALERT_WEBHOOK_URL`
usually is too, since a webhook URL is itself the credential.

They are read from the environment only — there is no secrets file, no
credential baked into an image, and no default that would work. The current
`.env` file is a **development** convenience and is git-ignored; it is not a
deployment mechanism. A real target should inject these through whatever its
platform provides (a secret manager, or the orchestrator's own secret objects),
and the audit in OPS-2 confirmed no credential is hardcoded anywhere in
`back/src` or `front/src`.

### The one build-time variable

Vite inlines `VITE_API_BASE_URL` into the bundle **when the image is built**.
So a frontend image encodes the API host it was built for and **cannot be
promoted unmodified** from staging to production if their APIs differ.

This is not solved, and the reason is recorded rather than hidden: the usual fix
is emitting a small runtime `env.js` and substituting it on container start, but
no second environment exists yet to promote across, so building that indirection
now would be guessing at its shape. When a second environment appears, this is
the first thing to change — and a journal entry to write.

---

## Running only one ingester

Ingestion runs inside the backend process (an architecture decision — no
separate service). Two consequences for deployment:

1. **Set `INGESTION_ENABLED=true` on exactly one instance.** Several instances
   with it on would each schedule a run.
2. **Do not add `--workers`.** Each worker starts its own scheduler, and
   APScheduler's `max_instances=1` is per-process.

Neither is a data-safety issue any more: a Postgres advisory lock means a second
concurrent run declines and says so. But the extra runs do no work, and the
reason the lock exists is worth knowing — see the rollback section.

---

## Ingestion rollback

Every full-reload table is snapshotted before it is replaced, so the previous
state is recoverable:

```bash
# From back/, with DATABASE_URL pointing at the target database.
python -m src.infrastructure.ingestion --rollback
```

This restores establishments, sites, communes and source references from the
snapshot taken before the **last** load. Indicator rows are append-only and are
not rolled back — a past year is never rewritten, so there is nothing to undo.

**Why concurrency matters here.** The snapshot is taken at the start of a run.
If two runs overlapped, the second's snapshot would capture the first's
freshly loaded data as "previous", and a rollback would restore the wrong state
*while reporting success* — discovered during an incident, at the worst possible
moment. The advisory lock exists to make that impossible. Do not remove it.

**Rollback is not a substitute for a backup.** It recovers from a bad *load*,
using tables that live in the same database. It does not survive losing the
database. A target must arrange its own backups.

---

## Data traceability audit (OPS-4)

The requirement in `docs/02_Architecture_Decisions.md` is that everything shown
to a user traces to one of three origins: raw official data, a documented
deterministic calculation, or versioned static editorial content.

### The automated half

`back/tests/integration/test_traceability_audit.py` walks real API responses and
asserts, for every value at any depth:

- a present figure is either raw (no computation note) or derived (`calcule:
  true` **and** a note saying how);
- an absent figure points at a registered content id and claims no calculation;
- every result row carries a source with a dataset id, an http URL and a
  synchronisation timestamp;
- every explanatory block is in the real registry, is versioned, and is served
  **byte-identical** to it — if the API could reword a block in flight,
  versioning it would prove nothing;
- no string over 80 characters appears anywhere outside the registries, which
  is the shape a future field carrying composed prose would take.

It is written to make no assumptions about which fields exist, so a field added
later is audited without anyone remembering to extend a list.

### The manual half, and why it cannot be automated

A test can prove a sentence is registered, versioned and attached to the right
figure. It cannot prove the sentence is **true**, or that it stays neutral. A
block can be perfectly traceable and still wrong.

Procedure, to re-run before any release that changes editorial content or adds a
data source:

1. **Sample.** Take five establishments deliberately, not randomly: one lycée
   with a full history, one collège (short IVAC history), one with an absent
   value-added figure above the diffusion threshold, one multi-site, and one
   with no indicators at all.
2. **For each field on each fact sheet**, name its origin out loud. If a value
   cannot be assigned to one of the three, stop — that is the finding.
3. **Read the explanatory blocks against their source.** Check the DEPP
   methodology still says what the block says. Thresholds have changed before:
   the value-added thresholds moved in session 2024, and the project's own
   glossary was wrong about them until Phase 2 caught it.
4. **Apply the charter's §14 seven-question checklist** to each sampled page.
5. **Record the result** as a dated entry in `docs/04_Journal_Decisions.md`,
   naming who reviewed it and what was sampled. An audit with no record is an
   audit nobody can rely on having happened.

---

## Not verified, and not to be claimed as verified

Honesty about the limits of what this environment could prove:

- **A genuinely remote database.** The production images were run against the
  development Postgres reached over the host's LAN address — external to the
  compose project, but not a managed remote instance. Re-run against a real one
  before deploying.
- **A real notification endpoint.** The alerting path is tested against a mocked
  webhook. Nothing has confirmed that a real Slack or email relay accepts the
  payload shape.
- **TLS, domains, reverse proxying, backups, log shipping.** All belong to a
  hosting target that has not been chosen. The frontend image serves plain HTTP
  on 8080 and expects something in front of it.
- **Load.** No load testing has been done. The read volume is small and the
  data is 21 MB, so nothing suggests a problem — but nothing has measured it
  either.
