"""A cross-process mutex for the ingestion run.

Why this is a correctness fix and not a throughput optimisation.

Every full-reload repository — establishments, sites, communes, source
references — snapshots the current table before truncating it:

    DROP TABLE IF EXISTS x_previous;
    CREATE TABLE x_previous AS SELECT * FROM x;

That snapshot is what `--rollback` restores from, and it is what makes the
architecture decision's "retain a snapshot of the previous valid state" real.

If two runs overlap, the second one's snapshot captures the *first run's
freshly loaded data* as "previous". A later rollback then restores that
instead of the genuinely prior state — and reports success while doing it.
The failure surfaces only when someone is already rolling back during an
incident, which is the worst possible moment to discover it.

Two ways to overlap, and the second needs no unusual configuration at all:

- Several uvicorn workers each start their own `BackgroundScheduler`.
  APScheduler's `max_instances=1` is per-process, so it does not help.
- A human runs `python -m src.infrastructure.ingestion` while the scheduled
  run is in progress. This is reachable today, with a single worker.

A Postgres *session-level* advisory lock is used rather than a table or a row:
it needs no schema, it is released automatically if the process dies (so a
crashed run cannot wedge every future one), and it is visible to any other
connection to the same database regardless of which process or host holds it.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

logger = logging.getLogger(__name__)

# An arbitrary but fixed key. Advisory locks share one namespace per database,
# so the value only has to be stable and unlikely to collide.
INGESTION_LOCK_KEY = 8_314_072_026


@contextmanager
def ingestion_lock(connection: psycopg.Connection) -> Iterator[bool]:
    """Yield True if this process took the lock, False if another holds it.

    Non-blocking on purpose. A queued second run would eventually re-fetch and
    re-load data the first run had just written — wasted work against a public
    API, for no benefit. Declining and saying so is the useful behaviour.

    The caller decides what a decline means; this context manager never raises
    on contention, and always releases what it acquired.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", (INGESTION_LOCK_KEY,))
        row = cursor.fetchone()
        acquired = bool(row[0]) if row else False

    try:
        yield acquired
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (INGESTION_LOCK_KEY,))
