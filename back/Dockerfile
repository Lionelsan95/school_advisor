# Production image for the backend.
#
# Multi-stage so the build tooling (pip, wheels, compilers pulled in by any
# dependency needing them) does not ship to production. Only the installed
# packages and the source are copied forward.
#
# The base image is tag-pinned rather than digest-pinned. Digest pinning would
# diverge this from Dockerfile.dev and adds an update-tracking chore out of
# proportion to a solo project; it is worth revisiting if a real supply-chain
# requirement appears, and that is a decision to record rather than drift into.

FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Manifest first so the dependency layer caches across source edits.
COPY pyproject.toml ./
COPY src ./src

# Install into a virtualenv that can be copied wholesale into the runtime
# stage. Installing to the system prefix would drag pip's own metadata along.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir .


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Non-root. The process reads a database and serves HTTP; nothing it does needs
# root, and a container that runs as root only fails safe by accident.
RUN useradd --system --create-home --uid 10001 appuser

WORKDIR /app

COPY --from=build /opt/venv /opt/venv
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini ./

USER appuser

EXPOSE 8000

# urllib rather than curl: the slim image has no curl, and installing one just
# to answer a healthcheck would add an attack surface for a one-line job.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# No --reload, and deliberately no --workers.
#
# Each worker process starts its own APScheduler, and APScheduler's
# `max_instances=1` is per-process — so N workers means N concurrent ingestion
# runs. The advisory lock in `ingestion/locking.py` makes that safe rather than
# corrupting, but the runs are still pointless: N-1 of them decline. At this
# read volume one worker is ample, and scaling belongs at the container level
# with `INGESTION_ENABLED` set on exactly one instance.
CMD ["uvicorn", "src.interfaces.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
