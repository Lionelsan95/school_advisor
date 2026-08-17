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
from typing import Any
from urllib.parse import urlparse

import psycopg
import pytest
from fastapi.testclient import TestClient

from src.domain.dataset_ids import (
    DATASET_COMMUNES,
    DATASET_DIRECTORY,
    DATASET_IVAC,
    DATASET_IVAL_GT,
    DATASET_IVAL_PRO,
)
from src.infrastructure.settings import get_settings
from src.interfaces.api.main import app

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


# ---------------------------------------------------------------------------
# Shared seeding machinery for the API integration tests.
#
# These lived in `test_establishments_api.py` and were imported from it by the
# history, compare and traceability modules. Four copies of a fixture, or three
# modules reaching into a fourth's private helpers, is the point at which they
# belong here instead — a test module is not an API for other test modules.
# ---------------------------------------------------------------------------


@pytest.fixture
def database_url(test_database_url: str) -> str:
    """The database these tests seed — and the one the app must be reading.

    `test_database_url` (conftest) is where the fixtures write. The app under
    test builds its pool from `DATABASE_URL` via `get_settings()`, which is a
    *different* knob. If the two disagree we would seed one database and query
    another, and every assertion would fail for a reason that has nothing to
    do with the code. Skip loudly instead.
    """
    app_url = get_settings().database_url
    if database_name(app_url) != database_name(test_database_url):
        pytest.skip(
            f"The app reads DATABASE_URL ({database_name(app_url)!r}) but these "
            f"tests seed {database_name(test_database_url)!r}. Point DATABASE_URL "
            f"at the test database for this run."
        )
    return test_database_url


@pytest.fixture
def db_connection(database_url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url, autocommit=True) as connection:
        yield connection


@pytest.fixture
def client(database_url: str) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded_uais(db_connection: psycopg.Connection) -> Iterator[list[str]]:
    """Tests append the fake UAIs they write; only those rows are cleaned up."""
    uais: list[str] = []
    yield uais
    if uais:
        with db_connection.cursor() as cursor:
            cursor.execute("DELETE FROM indicator_result WHERE uai = ANY(%s)", (uais,))
            cursor.execute("DELETE FROM site WHERE uai = ANY(%s)", (uais,))
            cursor.execute("DELETE FROM establishment WHERE uai = ANY(%s)", (uais,))


@pytest.fixture(autouse=True)
def ensure_source_references(db_connection: psycopg.Connection) -> None:
    """Guarantee every FactSheet-visible dataset has a provenance row.

    Uses `ON CONFLICT ... DO NOTHING` so it never overwrites a real, already
    -ingested reference: these tests must not depend on real data being
    present, but must not corrupt it either.
    """
    datasets = (
        DATASET_DIRECTORY,
        DATASET_IVAC,
        DATASET_IVAL_GT,
        DATASET_IVAL_PRO,
        DATASET_COMMUNES,
    )
    for dataset_id in datasets:
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO source_reference
                    (dataset_id, url, last_synchronised_at, source_published_at)
                VALUES (%s, %s, now(), NULL)
                ON CONFLICT (dataset_id) DO NOTHING
                """,
                (dataset_id, f"https://example.invalid/{dataset_id}"),
            )


def _insert_establishment(
    connection: psycopg.Connection,
    uai: str,
    *,
    name: str = "Fake Test Establishment",
    type_: str = "lycee",
    sector: str = "public",
    department_code: str = "999",
    is_open: bool = True,
    filieres: list[str] | None = None,
    sections: list[str] | None = None,
    sites: list[dict[str, Any]] | None = None,
) -> None:
    sites = sites or [
        {
            "sequence": 0,
            "name": name,
            "city": "Fakeville",
            "postal_code": "99999",
            "latitude": None,
            "longitude": None,
        }
    ]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO establishment
                (uai, name, type, sector, department_code, is_open,
                 site_count, filieres, sections, source_updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (uai) DO UPDATE SET
                name = EXCLUDED.name, type = EXCLUDED.type,
                sector = EXCLUDED.sector, department_code = EXCLUDED.department_code,
                is_open = EXCLUDED.is_open, site_count = EXCLUDED.site_count,
                filieres = EXCLUDED.filieres, sections = EXCLUDED.sections
            """,
            (
                uai,
                name,
                type_,
                sector,
                department_code,
                is_open,
                len(sites),
                filieres or [],
                sections or [],
                "2026-01-01T00:00:00+00:00",
            ),
        )
        for site in sites:
            cursor.execute(
                """
                INSERT INTO site
                    (uai, sequence, name, address, postal_code, city, city_code,
                     latitude, longitude)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (uai, sequence) DO UPDATE SET
                    name = EXCLUDED.name, latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude, city = EXCLUDED.city
                """,
                (
                    uai,
                    site["sequence"],
                    site.get("name", name),
                    site.get("address"),
                    site.get("postal_code"),
                    site.get("city"),
                    site.get("city_code"),
                    site.get("latitude"),
                    site.get("longitude"),
                ),
            )


def _insert_indicator(
    connection: psycopg.Connection,
    uai: str,
    year: int,
    *,
    indicator_type: str = "IVAC",
    sector: str = "public",
    candidates_present: int | None = 100,
    success_rate: float | None = 90.0,
    value_added_success: float | None = 1.0,
    access_rate: float | None = None,
    value_added_access: float | None = None,
    mention_rate: float | None = None,
    value_added_mention: float | None = None,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO indicator_result
                (uai, year, indicator_type, sector, candidates_present,
                 success_rate, value_added_success, access_rate,
                 value_added_access, mention_rate, value_added_mention)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (uai, year, indicator_type) DO UPDATE SET
                candidates_present = EXCLUDED.candidates_present,
                success_rate = EXCLUDED.success_rate,
                value_added_success = EXCLUDED.value_added_success,
                access_rate = EXCLUDED.access_rate,
                value_added_access = EXCLUDED.value_added_access,
                mention_rate = EXCLUDED.mention_rate,
                value_added_mention = EXCLUDED.value_added_mention
            """,
            (
                uai,
                year,
                indicator_type,
                sector,
                candidates_present,
                success_rate,
                value_added_success,
                access_rate,
                value_added_access,
                mention_rate,
                value_added_mention,
            ),
        )
