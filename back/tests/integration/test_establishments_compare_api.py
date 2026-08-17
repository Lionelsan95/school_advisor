"""Integration tests for GET /establishments/compare (API-8, F4).

Needs a live, already-migrated database — the same one
`tests/integration/test_establishments_api.py` uses — driven through
`fastapi.testclient.TestClient` against the real `src.interfaces.api.main.app`.

Every row this module writes uses a UAI under the fake "999...." prefix, per
the convention set in `test_establishments_api.py`: no real French département
code reaches 999, so cleanup can target exact UAIs rather than a TRUNCATE.
"""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient

from src.domain.dataset_ids import DATASET_IVAC, DATASET_IVAL_GT
from src.infrastructure.settings import get_settings
from src.interfaces.api.main import app
from tests.integration.conftest import database_name
from tests.integration.helpers import (
    insert_establishment,
    insert_indicator,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def database_url(test_database_url: str) -> str:
    """Same guard as `test_establishments_api.py` — see its docstring."""
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
    uais: list[str] = []
    yield uais
    if uais:
        with db_connection.cursor() as cursor:
            cursor.execute("DELETE FROM indicator_result WHERE uai = ANY(%s)", (uais,))
            cursor.execute("DELETE FROM site WHERE uai = ANY(%s)", (uais,))
            cursor.execute("DELETE FROM establishment WHERE uai = ANY(%s)", (uais,))


@pytest.fixture(autouse=True)
def ensure_source_references(db_connection: psycopg.Connection) -> None:
    """Mirrors `test_establishments_api.py`'s fixture of the same name — it
    is not shared across modules there, so it is not reused directly here,
    but the guarantee it provides (every response-visible dataset has a
    provenance row) is needed for a comparison too.
    """
    datasets = (DATASET_IVAC, DATASET_IVAL_GT)
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


class TestUnionOfYearsEndToEnd:
    """The realistic case the ticket names: a lycée (IVAL GT, deep history)
    compared with a collège (IVAC, only 2022+). The response must show the
    union of both series, and the year one establishment never published
    must carry the `annee_non_publiee` explanation — never a blank that
    reads like a withheld figure, and never dropped to make the table tidy.
    """

    def test_a_lycee_and_a_college_compare_across_the_union_of_their_years(
        self,
        client: TestClient,
        db_connection: psycopg.Connection,
        seeded_uais: list[str],
    ) -> None:
        lycee_uai = "9999921A"
        college_uai = "9999922B"
        seeded_uais.extend([lycee_uai, college_uai])
        insert_establishment(db_connection, lycee_uai, type_="lycee")
        insert_establishment(db_connection, college_uai, type_="college")
        for year in range(2019, 2024):
            insert_indicator(
                db_connection,
                lycee_uai,
                year,
                indicator_type="IVAL_GT",
                sector="public",
            )
        for year in (2022, 2023):
            insert_indicator(
                db_connection,
                college_uai,
                year,
                indicator_type="IVAC",
                sector="public",
            )

        response = client.get(
            "/establishments/compare",
            params=[("uai", lycee_uai), ("uai", college_uai)],
        )

        assert response.status_code == 200
        body = response.json()

        # Union of {2019..2023} (lycée) and {2022, 2023} (collège) — five
        # years, most recent first, not the two-year intersection.
        years = [row["annee"] for row in body["lignes"]]
        assert years == [2023, 2022, 2021, 2020, 2019]

        row_2019 = next(row for row in body["lignes"] if row["annee"] == 2019)
        cell_lycee, cell_college = row_2019["cellules"]
        assert cell_lycee["uai"] == lycee_uai
        assert cell_lycee["annee_publiee"] is True
        assert cell_lycee["resultat"] is not None
        assert cell_lycee["explication_absence"] is None

        assert cell_college["uai"] == college_uai
        assert cell_college["annee_publiee"] is False
        assert cell_college["resultat"] is None
        assert cell_college["explication_absence"] == "annee_non_publiee"

        row_2023 = next(row for row in body["lignes"] if row["annee"] == 2023)
        assert all(cell["annee_publiee"] for cell in row_2023["cellules"])
        assert all(cell["resultat"] is not None for cell in row_2023["cellules"])

        # The static block explaining the absence is present exactly once,
        # keyed by content id, not repeated per cell.
        assert "annee_non_publiee" in body["explications"]


class TestCompareErrorCases:
    def test_an_unknown_uai_pair_returns_404(self, client: TestClient) -> None:
        response = client.get(
            "/establishments/compare",
            params=[("uai", "9999999X"), ("uai", "9999998Y")],
        )
        assert response.status_code == 404

    def test_a_single_uai_returns_400(self, client: TestClient) -> None:
        response = client.get("/establishments/compare", params={"uai": "9999999X"})
        assert response.status_code == 400

    def test_the_same_uai_twice_returns_400(self, client: TestClient) -> None:
        response = client.get(
            "/establishments/compare",
            params=[("uai", "9999999X"), ("uai", "9999999X")],
        )
        assert response.status_code == 400
