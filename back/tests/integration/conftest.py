"""Shared fixtures for the integration tests — and the guard that keeps them
from running against a database somebody cares about.

Why this exists: `test_repositories.py` legitimately needs to TRUNCATE the
establishment/site/indicator tables to test the snapshot-and-refill cutover.
Pointed at the local development database, that silently destroys a full
ingested dataset — which is exactly what happened on 2026-08-15, because
`DATABASE_URL` was set to the dev database and CLAUDE.md's own documented
`pytest` command runs these tests.

So the destructive tests no longer trust `DATABASE_URL`. They run only against
a database explicitly designated as disposable:

  - `TEST_DATABASE_URL` if set, or
  - `DATABASE_URL` only when its database name ends in `_test`.

Anything else skips with an explanatory message rather than truncating. The
data being public and re-ingestible in ~20s is not a reason to destroy it: a
test suite that eats your working data is a test suite people stop running.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from urllib.parse import urlparse

import psycopg
import pytest

_TEST_DB_SUFFIX = "_test"


def database_name(url: str) -> str:
    return urlparse(url).path.lstrip("/")


def resolve_test_database_url() -> str | None:
    """The URL of a database these tests are allowed to wipe, or None."""
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    fallback = os.environ.get("DATABASE_URL")
    if fallback and database_name(fallback).endswith(_TEST_DB_SUFFIX):
        return fallback
    return None


def _skip_reason() -> str:
    configured = os.environ.get("DATABASE_URL")
    if not configured:
        return (
            "No test database configured. Set TEST_DATABASE_URL to a disposable "
            "database — these tests TRUNCATE tables."
        )
    name = database_name(configured)
    return (
        f"Refusing to run destructive integration tests against {name!r}: it is "
        f"not a test database. These tests TRUNCATE establishment, site and "
        f"indicator_result. Create a disposable database and point "
        f"TEST_DATABASE_URL at it:\n"
        f"  createdb {name}{_TEST_DB_SUFFIX}\n"
        f"  TEST_DATABASE_URL=... alembic upgrade head\n"
        f"  TEST_DATABASE_URL=... pytest tests/integration"
    )


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = resolve_test_database_url()
    if url is None:
        pytest.skip(_skip_reason())
    return url


@pytest.fixture
def connection(test_database_url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(test_database_url) as conn:
        yield conn
