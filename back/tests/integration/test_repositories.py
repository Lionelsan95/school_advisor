"""Integration tests for the Postgres repositories.

These exercise the SQL that unit tests cannot: the snapshot/truncate/refill
cutover, the append-only conflict handling, and the rollback path. They need a
live database and are marked `integration` so the default unit run stays fast
and offline:

    pytest tests/integration -m integration        # needs TEST_DATABASE_URL
    pytest tests/unit                              # no database required

These tests TRUNCATE their tables, so they run only against a database
explicitly designated as disposable — see `conftest.py`.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
import pytest

from src.domain.commune import Commune
from src.domain.enums import EstablishmentType, IndicatorType, Sector
from src.domain.establishment import Establishment, Site
from src.domain.indicator_result import IndicatorResult
from src.domain.source_reference import SourceReference
from src.infrastructure.persistence.repositories import (
    PostgresCommuneRepository,
    PostgresEstablishmentRepository,
    PostgresIndicatorRepository,
    PostgresSourceReferenceRepository,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def clean_tables(connection: psycopg.Connection) -> Iterator[None]:
    """Empty the tables around each test.

    These tests genuinely own the tables — but only because `conftest.py`
    guarantees the `connection` fixture points at a disposable test database
    and skips otherwise. Do not reintroduce a local `connection` fixture
    reading DATABASE_URL: that is what let this TRUNCATE wipe a full ingested
    development dataset on 2026-08-15.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "TRUNCATE establishment, site, indicator_result, commune, source_reference"
        )
        cursor.execute(
            "DROP TABLE IF EXISTS establishment_previous, site_previous, "
            "commune_previous, source_reference_previous"
        )
    connection.commit()
    yield
    with connection.cursor() as cursor:
        cursor.execute(
            "TRUNCATE establishment, site, indicator_result, commune, source_reference"
        )
        cursor.execute(
            "DROP TABLE IF EXISTS establishment_previous, site_previous, "
            "commune_previous, source_reference_previous"
        )
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


def make_commune(
    code: str,
    name: str,
    *,
    postal_codes: tuple[str, ...] = ("00000",),
    latitude: float | None = 48.8,
    longitude: float | None = 2.3,
) -> Commune:
    return Commune(
        code=code,
        name=name,
        postal_codes=postal_codes,
        department_code=code[:2],
        latitude=latitude,
        longitude=longitude,
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

    def test_rollback_recomputes_generated_search_columns(
        self, connection: psycopg.Connection, clean_tables: None
    ) -> None:
        repo = PostgresEstablishmentRepository(connection)
        original = Establishment(
            uai="0750001A",
            name="École Jean-Jaurès",
            type=EstablishmentType.COLLEGE,
            sector=Sector.PUBLIC,
            department_code="075",
            is_open=True,
            sites=(
                Site(
                    sequence=0,
                    name="École Jean-Jaurès",
                    city="L'Île-Rousse",
                    postal_code="20220",
                ),
            ),
        )
        repo.replace_all([original])
        repo.replace_all([make_establishment("0750002B", ["Replacement"])])

        repo.restore_previous()

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT e.search_name, s.search_city "
                "FROM establishment e JOIN site s USING (uai) "
                "WHERE e.uai = '0750001A'"
            )
            row = cursor.fetchone()
        assert row == ("ecole jean jaures", "l ile rousse")


class TestCommuneSnapshot:
    def test_replace_all_keeps_postal_codes_and_missing_centre(
        self, connection: psycopg.Connection, clean_tables: None
    ) -> None:
        repo = PostgresCommuneRepository(connection)

        loaded = repo.replace_all(
            [
                make_commune(
                    "2B134",
                    "L'Île-Rousse",
                    postal_codes=("20220", "20221"),
                ),
                make_commune(
                    "92022",
                    "Chaville",
                    postal_codes=("92370",),
                    latitude=None,
                    longitude=None,
                ),
            ]
        )

        assert loaded == 2
        assert repo.count() == 2
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT code, search_name, postal_codes, latitude, longitude "
                "FROM commune ORDER BY code"
            )
            rows = cursor.fetchall()
        assert rows == [
            ("2B134", "l ile rousse", ["20220", "20221"], 48.8, 2.3),
            ("92022", "chaville", ["92370"], None, None),
        ]

    def test_restore_previous_recovers_the_complete_snapshot(
        self, connection: psycopg.Connection, clean_tables: None
    ) -> None:
        repo = PostgresCommuneRepository(connection)
        repo.replace_all(
            [
                make_commune("2B134", "L'Île-Rousse"),
                make_commune("92022", "Chaville"),
            ]
        )
        repo.replace_all([make_commune("75056", "Paris")])

        restored = repo.restore_previous()

        assert restored == 2
        with connection.cursor() as cursor:
            cursor.execute("SELECT code, name FROM commune ORDER BY code")
            assert cursor.fetchall() == [
                ("2B134", "L'Île-Rousse"),
                ("92022", "Chaville"),
            ]

    def test_restore_without_snapshot_fails_visibly(
        self, connection: psycopg.Connection, clean_tables: None
    ) -> None:
        with pytest.raises(RuntimeError, match="nothing to restore"):
            PostgresCommuneRepository(connection).restore_previous()


class TestSourceReferenceSnapshot:
    def test_snapshot_restore_recovers_previous_provenance(
        self, connection: psycopg.Connection, clean_tables: None
    ) -> None:
        repo = PostgresSourceReferenceRepository(connection)
        original = SourceReference(
            dataset_id="geo-api-gouv-communes",
            url="https://geo.api.gouv.fr/decoupage-administratif/communes",
            last_synchronised_at=datetime(2026, 8, 14, tzinfo=UTC),
            source_published_at=None,
        )
        replacement = SourceReference(
            dataset_id="geo-api-gouv-communes",
            url="https://example.invalid/replacement",
            last_synchronised_at=datetime(2026, 8, 15, tzinfo=UTC),
            source_published_at=None,
        )
        repo.upsert(original)
        repo.snapshot()
        repo.upsert(replacement)

        restored = repo.restore_previous()

        assert restored == 1
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT url, last_synchronised_at FROM source_reference "
                "WHERE dataset_id = 'geo-api-gouv-communes'"
            )
            row = cursor.fetchone()
        assert row == (original.url, original.last_synchronised_at)


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
