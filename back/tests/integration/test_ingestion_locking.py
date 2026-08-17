"""Regression tests for the ingestion lock.

This is not a throughput concern. Every full-reload repository snapshots its
table before truncating, and that snapshot is what `--rollback` restores from.
If two runs overlap, the second one's snapshot captures the first run's freshly
loaded data as "previous", so a later rollback restores the wrong state and
reports success. It surfaces only while someone is already rolling back during
an incident.

Reachable without any unusual configuration: a human running
`python -m src.infrastructure.ingestion` while the scheduled run is in progress
hits it with a single uvicorn worker.
"""

from __future__ import annotations

import psycopg
import pytest

from src.infrastructure.ingestion.locking import (
    INGESTION_LOCK_KEY,
    ingestion_lock,
)

pytestmark = pytest.mark.integration


def test_a_second_concurrent_run_is_refused(
    connection: psycopg.Connection, test_database_url: str
) -> None:
    with (
        psycopg.connect(test_database_url) as other,
        ingestion_lock(connection) as first,
    ):
        assert first is True

        # Nested on purpose: the second attempt happens *while* the first
        # still holds the lock, which is the situation being tested.
        with ingestion_lock(other) as second:
            # Declining is the point. Queuing would re-fetch and re-load data
            # the first run had just written, against a public API.
            assert second is False


def test_the_lock_is_released_when_the_run_finishes(
    connection: psycopg.Connection, test_database_url: str
) -> None:
    with ingestion_lock(connection) as first:
        assert first is True

    with psycopg.connect(test_database_url) as other, ingestion_lock(other) as second:
        assert second is True


def test_the_lock_is_released_even_if_the_run_raises(
    connection: psycopg.Connection, test_database_url: str
) -> None:
    """A failed run must not wedge every subsequent one."""
    with pytest.raises(RuntimeError), ingestion_lock(connection) as acquired:
        assert acquired is True
        raise RuntimeError("ingestion blew up")

    with psycopg.connect(test_database_url) as other, ingestion_lock(other) as second:
        assert second is True


def test_a_dead_process_does_not_hold_the_lock_forever(
    test_database_url: str,
) -> None:
    """Session-level, not transaction-level, and deliberately not a table row.

    A crashed run releases the lock when its connection dies. A lock row in a
    table would need a human to clear it, at exactly the moment nobody wants to
    be reading this docstring.
    """
    orphan = psycopg.connect(test_database_url)
    with orphan.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", (INGESTION_LOCK_KEY,))
        row = cursor.fetchone()
        assert row is not None and row[0] is True
    orphan.close()

    with psycopg.connect(test_database_url) as other, ingestion_lock(other) as acquired:
        assert acquired is True


def test_the_lock_does_not_block_ordinary_reads(
    connection: psycopg.Connection, test_database_url: str
) -> None:
    """An advisory lock is cooperative: it must not lock readers out.

    The API keeps serving during an ingestion run; only another ingestion run
    is refused.
    """
    with (
        ingestion_lock(connection),
        psycopg.connect(test_database_url) as reader,
        reader.cursor() as cursor,
    ):
        cursor.execute("SELECT count(*) FROM establishment")
        assert cursor.fetchone() is not None
