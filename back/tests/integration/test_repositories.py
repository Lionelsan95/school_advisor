"""Integration tests for the Postgres repositories.

These exercise the SQL that unit tests cannot: the snapshot/truncate/refill
cutover, the append-only conflict handling, and the rollback path. They need a
live database and are marked `integration` so the default unit run stays fast
and offline:

    pytest tests/integration -m integration        # needs DATABASE_URL
    pytest tests/unit                              # no database required
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
import pytest

from src.domain.enums import EstablishmentType, IndicatorType, Sector
from src.domain.establishment import Establishment, Site
from src.domain.indicator_result import IndicatorResult
from src.infrastructure.persistence.repositories import (
    PostgresEstablishmentRepository,
    PostgresIndicatorRepository,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def connection() -> Iterator[psycopg.Connection]:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set — integration tests need a live database")
    with psycopg.connect(url) as conn:
        yield conn


@pytest.fixture
def clean_tables(connection: psycopg.Connection) -> Iterator[None]:
    """Leave the database as we found it: these tests own the tables."""
    with connection.cursor() as cursor:
        cursor.execute("TRUNCATE establishment, site, indicator_result")
    connection.commit()
    yield
    with connection.cursor() as cursor:
        cursor.execute("TRUNCATE establishment, site, indicator_result")
    connection.commit()


def make_establishment(uai: str, site_names: list[str]) -> Establishment:
    sites = tuple(
        Site(sequence=index, name=name, city="Testville", postal_code="00000")
        for index, name in enumerate(site_names)
    )
    return Establishment(
        uai=uai,
        name=sites[0].name,
        type=EstablishmentType.COLLEGE,
        sector=Sector.PUBLIC,
        department_code="075",
        is_open=True,
        sites=sites,
    )


def make_result(uai: str, year: int, value_added: float | None) -> IndicatorResult:
    return IndicatorResult(
        uai=uai,
        year=year,
        indicator_type=IndicatorType.IVAC,
        candidates_present=100,
        success_rate=90.0,
        value_added_success=value_added,
    )


class TestEstablishmentSnapshot:
    def test_replace_all_loads_establishments_and_every_site(
        self, connection: psycopg.Connection, clean_tables: None
    ) -> None:
        repo = PostgresEstablishmentRepository(connection)

        loaded = repo.replace_all(
            [
                make_establishment("0750001A", ["Main site", "Annexe"]),
                make_establishment("0750002B", ["Only site"]),
            ]
        )

        assert loaded == 2
        assert repo.count() == 2
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM site")
            row = cursor.fetchone()
            assert row is not None
            # Three site rows for two establishments: no location dropped.
            assert row[0] == 3

    def test_replace_all_preserves_declared_index_names(
        self, connection: psycopg.Connection, clean_tables: None
    ) -> None:
        """Regression test.

        An earlier staging-table-and-rename implementation left the live table
        carrying generated index names (`establishment_staging_type_idx2`),
        with the suffix incrementing on every run, which would break any later
        migration that referenced an index by its declared name.
        """
        repo = PostgresEstablishmentRepository(connection)

        for _ in range(3):
            repo.replace_all([make_establishment("0750001A", ["Site"])])

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename IN ('establishment', 'site')"
            )
            names = {row[0] for row in cursor.fetchall()}
        assert "ix_establishment_type" in names
        assert "ix_establishment_department" in names
        assert not any("staging" in name for name in names)

    def test_replace_all_keeps_a_restorable_snapshot(
        self, connection: psycopg.Connection, clean_tables: None
    ) -> None:
        repo = PostgresEstablishmentRepository(connection)
        repo.replace_all(
            [
                make_establishment("0750001A", ["First run"]),
                make_establishment("0750002B", ["First run"]),
            ]
        )

        repo.replace_all([make_establishment("0750003C", ["Second run"])])
        assert repo.count() == 1

        restored = repo.restore_previous()

        assert restored == 2
        with connection.cursor() as cursor:
            cursor.execute("SELECT uai FROM establishment ORDER BY uai")
            assert [row[0] for row in cursor.fetchall()] == ["0750001A", "0750002B"]


class TestIndicatorAppendOnly:
    def test_append_inserts_rows(
        self, connection: psycopg.Connection, clean_tables: None
    ) -> None:
        repo = PostgresIndicatorRepository(connection)

        inserted = repo.append(
            [make_result("0750001A", 2024, 2.0), make_result("0750001A", 2025, 1.0)]
        )

        assert inserted == 2
        assert repo.count() == 2

    def test_reappending_the_same_year_changes_nothing(
        self, connection: psycopg.Connection, clean_tables: None
    ) -> None:
        """A past year must never be rewritten by a later ingestion run."""
        repo = PostgresIndicatorRepository(connection)
        repo.append([make_result("0750001A", 2024, 2.0)])

        # Same key, different value — must be ignored, not applied.
        inserted = repo.append([make_result("0750001A", 2024, 99.0)])

        assert inserted == 0
        assert repo.count() == 1
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT value_added_success FROM indicator_result WHERE year = 2024"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 2.0

    def test_appending_a_new_year_keeps_previous_years(
        self, connection: psycopg.Connection, clean_tables: None
    ) -> None:
        repo = PostgresIndicatorRepository(connection)
        repo.append([make_result("0750001A", 2024, 2.0)])

        repo.append([make_result("0750001A", 2025, 3.0)])

        assert repo.count() == 2
        with connection.cursor() as cursor:
            cursor.execute("SELECT year FROM indicator_result ORDER BY year")
            assert [row[0] for row in cursor.fetchall()] == [2024, 2025]

    def test_a_missing_value_is_stored_as_null(
        self, connection: psycopg.Connection, clean_tables: None
    ) -> None:
        """No reason is inferred and no placeholder is invented."""
        repo = PostgresIndicatorRepository(connection)

        repo.append([make_result("0750001A", 2025, None)])

        with connection.cursor() as cursor:
            cursor.execute("SELECT value_added_success FROM indicator_result")
            row = cursor.fetchone()
            assert row is not None
            assert row[0] is None


class TestFailureLeavesDataUntouched:
    def test_a_failure_after_replace_all_rolls_back_the_snapshot(
        self, connection: psycopg.Connection, clean_tables: None
    ) -> None:
        """The whole run is one transaction.

        Mirrors what job.py does: if appending indicators fails after the
        establishments were replaced, the establishment table must not be left
        holding the new snapshot.
        """
        establishments = PostgresEstablishmentRepository(connection)
        establishments.replace_all([make_establishment("0750001A", ["Original"])])

        with pytest.raises(psycopg.Error), connection.transaction():
            establishments.replace_all(
                [make_establishment("0750002B", ["Replacement"])]
            )
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM table_that_does_not_exist")

        with connection.cursor() as cursor:
            cursor.execute("SELECT uai FROM establishment")
            assert [row[0] for row in cursor.fetchall()] == ["0750001A"]
