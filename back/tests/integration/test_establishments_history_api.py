"""Integration tests for GET /establishments/{uai}/history (API-7, F5).

Needs a live, already-migrated database — the same one
`tests/integration/test_establishments_api.py` uses — driven through
`fastapi.testclient.TestClient` against the real
`src.interfaces.api.main.app`.

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
    but the guarantee it provides (every FactSheet-visible dataset has a
    provenance row) is needed for history too.
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


class TestIvalGtHistorySpanningTheReform:
    def test_a_span_from_2019_to_2023_returns_ascending_points_and_the_break(
        self,
        client: TestClient,
        db_connection: psycopg.Connection,
        seeded_uais: list[str],
    ) -> None:
        uai = "9999911A"
        seeded_uais.append(uai)
        insert_establishment(db_connection, uai, type_="lycee")
        for year in (2019, 2020, 2021, 2022, 2023):
            insert_indicator(
                db_connection, uai, year, indicator_type="IVAL_GT", sector="public"
            )

        response = client.get(f"/establishments/{uai}/history")

        assert response.status_code == 200
        body = response.json()
        assert [point["annee"] for point in body["points"]] == [
            2019,
            2020,
            2021,
            2022,
            2023,
        ]
        assert body["annees_couvertes"] == [2019, 2020, 2021, 2022, 2023]
        assert len(body["ruptures_methodologiques"]) == 1
        assert body["ruptures_methodologiques"][0]["annee"] == 2021


class TestIvacOnlyHistoryNeverCarriesTheBreak:
    def test_an_ivac_only_establishment_returns_points_and_no_break(
        self,
        client: TestClient,
        db_connection: psycopg.Connection,
        seeded_uais: list[str],
    ) -> None:
        uai = "9999912B"
        seeded_uais.append(uai)
        insert_establishment(db_connection, uai, type_="college")
        for year in (2022, 2023, 2024, 2025):
            insert_indicator(
                db_connection, uai, year, indicator_type="IVAC", sector="public"
            )

        response = client.get(f"/establishments/{uai}/history")

        assert response.status_code == 200
        body = response.json()
        assert [point["annee"] for point in body["points"]] == [
            2022,
            2023,
            2024,
            2025,
        ]
        assert body["annees_couvertes"] == [2022, 2023, 2024, 2025]
        assert body["ruptures_methodologiques"] == []


class TestEveryPointCarriesASource:
    def test_every_point_in_the_history_carries_a_source(
        self,
        client: TestClient,
        db_connection: psycopg.Connection,
        seeded_uais: list[str],
    ) -> None:
        uai = "9999913C"
        seeded_uais.append(uai)
        insert_establishment(db_connection, uai, type_="lycee")
        insert_indicator(db_connection, uai, 2022, indicator_type="IVAL_GT")
        insert_indicator(db_connection, uai, 2023, indicator_type="IVAL_GT")

        response = client.get(f"/establishments/{uai}/history")

        assert response.status_code == 200
        points = response.json()["points"]
        assert len(points) == 2
        for point in points:
            assert point["source"] is not None
            assert point["source"]["dataset_id"] == DATASET_IVAL_GT
            assert point["source"]["url"]
            assert point["source"]["derniere_synchronisation"]


class TestHistoryErrorCases:
    def test_a_well_formed_but_unknown_uai_returns_404(
        self, client: TestClient
    ) -> None:
        response = client.get("/establishments/9999999Z/history")
        assert response.status_code == 404

    def test_a_malformed_uai_returns_400(self, client: TestClient) -> None:
        response = client.get("/establishments/not-a-uai/history")
        assert response.status_code == 400
