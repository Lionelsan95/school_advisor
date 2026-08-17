"""Integration tests for the Phase 2 read API (API-1, API-2, API-4, API-5, API-6).

Needs a live, already-migrated database (the same one `tests/integration/
test_repositories.py` uses) and drives it through `fastapi.testclient.
TestClient` against the real `src.interfaces.api.main.app`, which opens a
read-only, REPEATABLE READ connection pool exactly as production does.

The database this project's docker-compose already runs holds real ingested
national data (~68k establishments) that these tests must never depend on,
and must never delete — see CLAUDE.md and the task instructions. Every row
this module writes uses a UAI under the fake "999...." prefix (no real
French département code reaches 999) and a fake location in the middle of
the Atlantic, off Null Island, so proximity searches can be scoped with an
exact, contamination-free result set. Cleanup only ever targets those exact
UAIs — never a TRUNCATE.

Seed data is written on an autocommit connection and committed *before* each
request: the app's pool is configured read-only, so it cannot see writes an
external, uncommitted transaction is still holding.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from src.application.errors import MissingSourceReferenceError
from src.application.search_communes import MissingCommuneSourceError
from src.application.search_establishments import MissingSearchSourceError
from src.domain.dataset_ids import (
    DATASET_COMMUNES,
    DATASET_DIRECTORY,
    DATASET_IVAC,
    DATASET_IVAL_GT,
)
from src.domain.explanatory_content import SCOPE_DISCLAIMER
from src.interfaces.api.communes import get_commune_search_use_case
from src.interfaces.api.establishments import (
    get_fact_sheet_use_case,
    get_search_use_case,
)
from src.interfaces.api.main import app
from tests.integration.helpers import (
    insert_establishment,
    insert_indicator,
)

pytestmark = pytest.mark.integration

# "Null Island" (0°N, 0°E) — the Gulf of Guinea. No French establishment is
# anywhere near it, so a radius search centred here can only ever return the
# fake rows this module writes, however wide the radius.
ORIGIN_LAT = 0.0
ORIGIN_LNG = 0.0
LAT_STEP = 0.01  # ~1.11 km at the equator


class TestFactSheetNormalCase:
    def test_a_normal_year_returns_present_figures_with_no_absence_marker(
        self,
        client: TestClient,
        db_connection: psycopg.Connection,
        seeded_uais: list[str],
    ) -> None:
        uai = "9999991A"
        seeded_uais.append(uai)
        insert_establishment(db_connection, uai, type_="college")
        insert_indicator(
            db_connection,
            uai,
            2025,
            indicator_type="IVAC",
            candidates_present=120,
            success_rate=90.0,
            value_added_success=2.0,
        )

        response = client.get(f"/establishments/{uai}")

        assert response.status_code == 200
        body = response.json()
        row = next(r for r in body["resultats"] if r["annee"] == 2025)
        assert row["valeur_ajoutee_reussite"]["valeur"] == 2.0
        assert row["valeur_ajoutee_reussite"]["explication_absence"] is None
        # taux attendu = taux constaté - valeur ajoutée = 90 - 2 = 88, and it
        # must be flagged as this service's own computation (F10), not raw
        # source data.
        assert row["taux_reussite_attendu"]["valeur"] == pytest.approx(88.0)
        assert row["taux_reussite_attendu"]["calcule"] is True
        assert row["taux_reussite_attendu"]["note_de_calcul"]


class TestFactSheetMissingValueTransparency:
    """API-4 — the Mayotte-style case: candidates were present (so the
    threshold explanation alone cannot be right for every such row — see the
    Phase 0 spike), yet no value-added figure was published. The response
    must mark the absence without asserting why.
    """

    def test_a_high_candidate_row_with_no_published_value_added_marks_the_absence(
        self,
        client: TestClient,
        db_connection: psycopg.Connection,
        seeded_uais: list[str],
    ) -> None:
        uai = "9999992B"
        seeded_uais.append(uai)
        insert_establishment(db_connection, uai, type_="lycee", department_code="976")
        insert_indicator(
            db_connection,
            uai,
            2025,
            indicator_type="IVAL_GT",
            candidates_present=415,
            success_rate=85.0,
            value_added_success=None,
        )

        response = client.get(f"/establishments/{uai}")

        assert response.status_code == 200
        body = response.json()
        row = next(r for r in body["resultats"] if r["annee"] == 2025)

        assert row["candidats_presents"] == 415
        figure = row["valeur_ajoutee_reussite"]
        assert figure["valeur"] is None
        assert figure["calcule"] is False
        assert figure["explication_absence"] == "valeur_non_disponible"

        # Derived from the absent value-added, so it must stay absent too —
        # never partially reconstructed.
        expected_rate_figure = row["taux_reussite_attendu"]
        assert expected_rate_figure["valeur"] is None
        assert expected_rate_figure["calcule"] is False
        assert expected_rate_figure["explication_absence"] == "valeur_non_disponible"

        # No field on the row itself asserts a cause.
        assert "raison_absence" not in row
        assert "sous_seuil_diffusion" not in row
        assert "non_diffusion_reason" not in row

        explanation = body["explications"]["valeur_non_disponible"]
        combined = " ".join(
            [
                explanation["definition_simple"],
                explanation["comment_lire"],
                explanation["ce_que_cela_mesure"],
                explanation["ce_que_cela_ne_mesure_pas"],
                explanation.get("methode") or "",
                explanation["source"],
            ]
        )
        # The explanation is the same static block for every row — it never
        # names this establishment or this département.
        assert uai not in combined
        assert "976" not in combined


class TestFactSheetErrorCases:
    def test_a_well_formed_but_unknown_uai_returns_404(
        self, client: TestClient
    ) -> None:
        response = client.get("/establishments/9999999Z")
        assert response.status_code == 404

    def test_a_malformed_uai_returns_400(self, client: TestClient) -> None:
        response = client.get("/establishments/not-a-uai")
        assert response.status_code == 400

    def test_missing_provenance_returns_503_instead_of_orphan_numbers(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        class MissingProvenanceUseCase:
            def run(self, uai: str) -> None:
                raise MissingSourceReferenceError(DATASET_IVAC, uai, 2025)

        caplog.set_level(logging.ERROR, logger="src.interfaces.api.establishments")
        app.dependency_overrides[get_fact_sheet_use_case] = MissingProvenanceUseCase
        try:
            response = client.get("/establishments/9999999Z")
        finally:
            app.dependency_overrides.pop(get_fact_sheet_use_case, None)

        assert response.status_code == 503
        assert response.json() == {
            "detail": (
                "Une référence de source nécessaire à cette fiche est "
                "indisponible. La fiche n'est pas publiée afin de ne pas "
                "présenter de donnée sans origine."
            )
        }
        provenance_logs = [
            record
            for record in caplog.records
            if record.name == "src.interfaces.api.establishments"
            and record.getMessage()
            == "Fact sheet withheld because source provenance is missing"
        ]
        assert len(provenance_logs) == 1
        record = provenance_logs[0]
        assert record.levelno == logging.ERROR
        assert record.dataset_id == DATASET_IVAC
        assert record.uai == "9999999Z"
        assert record.year == 2025


class TestFactSheetCarriesScopeDisclaimerAndSource:
    """API-5 (scope disclaimer) and API-6 (source attribution)."""

    def test_the_fact_sheet_carries_the_scope_disclaimer(
        self,
        client: TestClient,
        db_connection: psycopg.Connection,
        seeded_uais: list[str],
    ) -> None:
        uai = "9999993C"
        seeded_uais.append(uai)
        insert_establishment(db_connection, uai)

        response = client.get(f"/establishments/{uai}")

        assert response.status_code == 200
        assert response.json()["rappel_de_portee"] == SCOPE_DISCLAIMER

    def test_every_result_row_carries_a_source_reference(
        self,
        client: TestClient,
        db_connection: psycopg.Connection,
        seeded_uais: list[str],
    ) -> None:
        uai = "9999994D"
        seeded_uais.append(uai)
        insert_establishment(db_connection, uai, type_="lycee")
        insert_indicator(db_connection, uai, 2024, indicator_type="IVAL_GT")
        insert_indicator(db_connection, uai, 2025, indicator_type="IVAL_GT")

        response = client.get(f"/establishments/{uai}")

        assert response.status_code == 200
        results = response.json()["resultats"]
        assert len(results) == 2
        for row in results:
            assert row["source"] is not None
            assert row["source"]["dataset_id"] == DATASET_IVAL_GT
            assert row["source"]["url"]
            assert row["source"]["derniere_synchronisation"]


class TestSearchFilters:
    """Uses a cluster of fake establishments around Null Island so that type,
    sector, filiere and radius filters can be asserted exactly — no real
    establishment can appear in this result set at any radius.
    """

    @pytest.fixture(autouse=True)
    def _seed_cluster(
        self,
        db_connection: psycopg.Connection,
        seeded_uais: list[str],
    ) -> None:
        cluster = [
            dict(uai="9999901A", type_="lycee", sector="public", filieres=["generale"]),
            dict(
                uai="9999902B",
                type_="lycee",
                sector="prive",
                filieres=["technologique"],
            ),
            dict(uai="9999903C", type_="college", sector="public", filieres=[]),
        ]
        for index, spec in enumerate(cluster):
            uai = spec["uai"]
            seeded_uais.append(uai)
            insert_establishment(
                db_connection,
                uai,
                type_=spec["type_"],
                sector=spec["sector"],
                filieres=spec["filieres"],
                sites=[
                    {
                        "sequence": 0,
                        "name": f"Fake {uai}",
                        "city": "Fakeville",
                        "postal_code": "99999",
                        "latitude": ORIGIN_LAT + index * LAT_STEP,
                        "longitude": ORIGIN_LNG,
                    }
                ],
            )
        # A multi-site establishment: two sites, one of them the canonical
        # (lowest sequence, near the cluster), the other far away. It must
        # appear exactly once in every search result.
        multi_uai = "9999905E"
        seeded_uais.append(multi_uai)
        insert_establishment(
            db_connection,
            multi_uai,
            type_="lycee",
            sector="public",
            filieres=[],
            sites=[
                {
                    "sequence": 0,
                    "name": "Multi-site — main",
                    "city": "Fakeville",
                    "postal_code": "99999",
                    "latitude": ORIGIN_LAT + 3 * LAT_STEP,
                    "longitude": ORIGIN_LNG,
                },
                {
                    # Mirrors the Phase 0 spike finding (Site's docstring):
                    # annexe sites of a multi-site establishment repeat the
                    # parent's coordinates in the source, so this one sits
                    # right next to the main site rather than far away —
                    # close enough to also fall inside a small search radius,
                    # so a broken "one row per establishment" dedup would be
                    # caught here, not masked by distance filtering alone.
                    "sequence": 1,
                    "name": "Multi-site — annexe",
                    "city": "Fakeville",
                    "postal_code": "99999",
                    "latitude": ORIGIN_LAT + 3 * LAT_STEP + 0.0005,
                    "longitude": ORIGIN_LNG,
                },
            ],
        )
        # An establishment with no coordinates at all: must be excluded from
        # any location search, never guessed.
        no_coords_uai = "9999904D"
        seeded_uais.append(no_coords_uai)
        insert_establishment(
            db_connection,
            no_coords_uai,
            type_="lycee",
            sector="public",
            filieres=["generale"],
            sites=[
                {
                    "sequence": 0,
                    "name": "No coordinates",
                    "city": "Fakeville",
                    "postal_code": "99999",
                    "latitude": None,
                    "longitude": None,
                }
            ],
        )
        # Pagination fillers, further out (offsets 4..8 -> 8, 4x -> 8.88 km).
        for offset in range(4, 9):
            uai = f"99999{offset:02d}G"
            seeded_uais.append(uai)
            insert_establishment(
                db_connection,
                uai,
                type_="lycee",
                sector="public",
                filieres=[],
                sites=[
                    {
                        "sequence": 0,
                        "name": f"Filler {uai}",
                        "city": "Fakeville",
                        "postal_code": "99999",
                        "latitude": ORIGIN_LAT + offset * LAT_STEP,
                        "longitude": ORIGIN_LNG,
                    }
                ],
            )

    def _search(self, client: TestClient, **params: Any) -> dict[str, Any]:
        response = client.get("/establishments/search", params=params)
        assert response.status_code == 200
        result: dict[str, Any] = response.json()
        return result

    def test_type_filter_returns_only_matching_establishments(
        self, client: TestClient
    ) -> None:
        body = self._search(
            client,
            type="college",
            lat=ORIGIN_LAT,
            lng=ORIGIN_LNG,
            rayon_km=100,
        )
        uais = {hit["uai"] for hit in body["resultats"]}
        assert uais == {"9999903C"}

    def test_sector_filter_returns_only_matching_establishments(
        self, client: TestClient
    ) -> None:
        body = self._search(
            client,
            secteur="prive",
            lat=ORIGIN_LAT,
            lng=ORIGIN_LNG,
            rayon_km=100,
        )
        uais = {hit["uai"] for hit in body["resultats"]}
        assert uais == {"9999902B"}

    def test_filiere_filter_returns_only_matching_establishments(
        self, client: TestClient
    ) -> None:
        body = self._search(
            client,
            filiere="generale",
            lat=ORIGIN_LAT,
            lng=ORIGIN_LNG,
            rayon_km=100,
        )
        uais = {hit["uai"] for hit in body["resultats"]}
        # 9999904D also offers "generale" but has no coordinates, so a
        # location search must exclude it regardless.
        assert uais == {"9999901A"}

    def test_proximity_filter_orders_ascending_by_distance(
        self, client: TestClient
    ) -> None:
        body = self._search(client, lat=ORIGIN_LAT, lng=ORIGIN_LNG, rayon_km=4)
        hits = body["resultats"]
        uais_in_order = [hit["uai"] for hit in hits]

        assert uais_in_order == ["9999901A", "9999902B", "9999903C", "9999905E"]
        distances = [hit["distance_km"] for hit in hits]
        assert distances == sorted(distances)
        assert body["tri"] == "proximite"

    def test_an_establishment_with_null_coordinates_is_excluded_from_a_location_search(
        self, client: TestClient
    ) -> None:
        body = self._search(client, lat=ORIGIN_LAT, lng=ORIGIN_LNG, rayon_km=100)
        uais = {hit["uai"] for hit in body["resultats"]}
        assert "9999904D" not in uais

    def test_a_multi_site_establishment_appears_exactly_once(
        self, client: TestClient
    ) -> None:
        body = self._search(client, lat=ORIGIN_LAT, lng=ORIGIN_LNG, rayon_km=100)
        uais_in_order = [hit["uai"] for hit in body["resultats"]]
        assert uais_in_order.count("9999905E") == 1

    def test_an_empty_result_set_is_returned_when_nothing_matches(
        self, client: TestClient
    ) -> None:
        body = self._search(
            client,
            type="ecole",
            lat=ORIGIN_LAT,
            lng=ORIGIN_LNG,
            rayon_km=100,
        )
        assert body["resultats"] == []
        assert body["nombre_total"] == 0

    def test_pagination_has_no_overlap_and_a_stable_total(
        self, client: TestClient
    ) -> None:
        page_size = 3
        seen: list[str] = []
        totals: set[int] = set()
        for offset in (0, 3, 6):
            body = self._search(
                client,
                lat=ORIGIN_LAT,
                lng=ORIGIN_LNG,
                rayon_km=100,
                limit=page_size,
                offset=offset,
            )
            totals.add(body["nombre_total"])
            page_uais = [hit["uai"] for hit in body["resultats"]]
            assert len(page_uais) == page_size
            seen.extend(page_uais)

        # 3 cluster (A, B, C) + 1 multi-site (E) + 5 fillers = 9. The
        # no-coordinates establishment (D) never enters a location search.
        assert totals == {9}
        assert len(seen) == len(set(seen)), "pages must not overlap"
        assert len(seen) == 9

    def test_search_response_carries_the_scope_disclaimer(
        self, client: TestClient
    ) -> None:
        body = self._search(client, lat=ORIGIN_LAT, lng=ORIGIN_LNG, rayon_km=100)
        assert body["rappel_de_portee"] == SCOPE_DISCLAIMER


class TestSearchRejectsSortParameters:
    @pytest.mark.parametrize("param", ["sort_by", "sort", "order_by", "tri"])
    def test_a_sort_parameter_is_rejected_with_400(
        self, client: TestClient, param: str
    ) -> None:
        response = client.get("/establishments/search", params={param: "asc"})
        assert response.status_code == 400


class TestSearchSourceIntegrity:
    def test_successful_search_carries_mandatory_directory_provenance(
        self, client: TestClient
    ) -> None:
        response = client.get("/establishments/search", params={"limit": 1})

        assert response.status_code == 200
        source = response.json()["source"]
        assert source["dataset_id"] == DATASET_DIRECTORY
        assert source["url"]
        assert source["derniere_synchronisation"]

    def test_missing_directory_source_returns_neutral_503_without_results(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        class MissingDirectorySourceUseCase:
            def run(self, criteria: object) -> None:
                raise MissingSearchSourceError(
                    f"Missing source reference for {DATASET_DIRECTORY}"
                )

        caplog.set_level(logging.ERROR, logger="src.interfaces.api.establishments")
        app.dependency_overrides[get_search_use_case] = MissingDirectorySourceUseCase
        try:
            response = client.get("/establishments/search", params={"limit": 1})
        finally:
            app.dependency_overrides.pop(get_search_use_case, None)

        assert response.status_code == 503
        body = response.json()
        assert body == {
            "detail": (
                "Une référence de source nécessaire à cette recherche est "
                "indisponible. Les résultats ne sont pas publiés afin de ne "
                "pas présenter de données sans origine."
            )
        }
        assert "resultats" not in body
        assert any(
            record.name == "src.interfaces.api.establishments"
            and record.getMessage()
            == "Establishment search withheld because provenance is missing"
            for record in caplog.records
        )


class TestOfficialCommuneSearch:
    @pytest.fixture(autouse=True)
    def _seed_communes(self, db_connection: psycopg.Connection) -> Iterator[None]:
        rows = [
            ("2B134", "L'Île-Rousse", ["20220"], "2B", 42.634, 8.937),
            ("99101", "Saint-Pierre", ["99100"], "99", 0.5, 0.5),
            ("99102", "Saint-Pierre", ["99101"], "99", 0.6, 0.6),
            ("99103", "Centre-Absent", [], "99", None, None),
        ]
        with db_connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO commune
                    (code, name, postal_codes, department_code, latitude, longitude)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    postal_codes = EXCLUDED.postal_codes,
                    department_code = EXCLUDED.department_code,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude
                """,
                rows,
            )
        yield
        with db_connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM commune WHERE code = ANY(%s)",
                ([row[0] for row in rows],),
            )

    @pytest.mark.parametrize("query", ["ile rousse", "ÎLE-ROUSSE", "2b134"])
    def test_accents_case_and_lowercase_corsican_code_resolve_the_same_commune(
        self, client: TestClient, query: str
    ) -> None:
        response = client.get("/communes/search", params={"q": query})

        assert response.status_code == 200
        assert response.json()["resultats"][0]["code"] == "2B134"
        assert response.json()["source"]["dataset_id"] == DATASET_COMMUNES

    def test_duplicate_names_are_returned_in_stable_code_order(
        self, client: TestClient
    ) -> None:
        response = client.get("/communes/search", params={"q": "Saint-Pierre"})

        assert response.status_code == 200
        hits = response.json()["resultats"]
        assert [hit["code"] for hit in hits[:2]] == ["99101", "99102"]

    def test_missing_official_centre_is_returned_as_null_not_guessed(
        self, client: TestClient
    ) -> None:
        response = client.get("/communes/search", params={"q": "Centre-Absent"})

        assert response.status_code == 200
        hit = response.json()["resultats"][0]
        assert hit["latitude"] is None
        assert hit["longitude"] is None
        assert hit["codes_postaux"] == []

    def test_punctuation_only_query_is_rejected(self, client: TestClient) -> None:
        response = client.get("/communes/search", params={"q": "---"})
        assert response.status_code == 400

    def test_missing_commune_source_returns_neutral_503_without_results(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        class MissingCommuneSourceUseCase:
            def run(self, query: str, limit: int) -> None:
                raise MissingCommuneSourceError(
                    f"Missing source reference for {DATASET_COMMUNES}"
                )

        caplog.set_level(logging.ERROR, logger="src.interfaces.api.communes")
        app.dependency_overrides[get_commune_search_use_case] = (
            MissingCommuneSourceUseCase
        )
        try:
            response = client.get("/communes/search", params={"q": "Chaville"})
        finally:
            app.dependency_overrides.pop(get_commune_search_use_case, None)

        assert response.status_code == 503
        body = response.json()
        assert body == {
            "detail": (
                "Une référence de source nécessaire à cette recherche est "
                "indisponible. Les résultats ne sont pas publiés afin de ne "
                "pas présenter de données sans origine."
            )
        }
        assert "resultats" not in body
        assert any(
            record.name == "src.interfaces.api.communes"
            and record.getMessage()
            == "Commune search withheld because provenance is missing"
            for record in caplog.records
        )


class TestTextAndPlaceEstablishmentSearch:
    @pytest.fixture(autouse=True)
    def _seed_search_rows(
        self,
        db_connection: psycopg.Connection,
        seeded_uais: list[str],
    ) -> None:
        specs = [
            (
                "9999801A",
                "École Jean-Jaurès",
                "L'Île-Rousse",
                "2B134",
                "20220",
                0.04,
            ),
            (
                "9999802B",
                "École Jean-Jaurès Annexe",
                "L'Île-Rousse",
                "2B134",
                "20220",
                0.0,
            ),
            (
                "9999803C",
                "Collège des Tests",
                "Autreville",
                "99103",
                "99199",
                0.01,
            ),
        ]
        for uai, name, city, city_code, postal_code, latitude in specs:
            seeded_uais.append(uai)
            insert_establishment(
                db_connection,
                uai,
                name=name,
                type_="ecole" if "École" in name else "college",
                sites=[
                    {
                        "sequence": 0,
                        "name": name,
                        "city": city,
                        "city_code": city_code,
                        "postal_code": postal_code,
                        "latitude": latitude,
                        "longitude": 0.0,
                    }
                ],
            )

        # This annexe deliberately contains the query while the canonical site
        # does not. Identity search must remain canonical-site-only.
        uai = "9999804D"
        seeded_uais.append(uai)
        insert_establishment(
            db_connection,
            uai,
            name="Canonical Identity",
            type_="college",
            sites=[
                {
                    "sequence": 0,
                    "name": "Canonical Identity",
                    "city": "Canonicalville",
                    "city_code": "99104",
                    "postal_code": "99104",
                    "latitude": 0.02,
                    "longitude": 0.0,
                },
                {
                    "sequence": 1,
                    "name": "Annexe",
                    "city": "AnnexeOnlyPlace",
                    "city_code": "99105",
                    "postal_code": "99105",
                    "latitude": 0.03,
                    "longitude": 0.0,
                },
            ],
        )

    def _search(self, client: TestClient, **params: Any) -> dict[str, Any]:
        response = client.get("/establishments/search", params=params)
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    @pytest.mark.parametrize("query", ["ecole jean jaures", "ÉCOLE JEAN-JAURÈS"])
    def test_name_search_is_accent_and_case_insensitive(
        self, client: TestClient, query: str
    ) -> None:
        body = self._search(client, q=query)
        assert [hit["uai"] for hit in body["resultats"][:2]] == [
            "9999801A",
            "9999802B",
        ]
        assert body["tri"] == "correspondance"

    def test_uai_search_accepts_lowercase_and_internal_spaces(
        self, client: TestClient
    ) -> None:
        body = self._search(client, q="999 9801a")
        assert [hit["uai"] for hit in body["resultats"]] == ["9999801A"]

    def test_commune_and_postal_code_filters_are_exact(
        self, client: TestClient
    ) -> None:
        by_commune = self._search(client, code_commune="2b134")
        by_postal = self._search(client, code_postal="20220")
        expected = {"9999801A", "9999802B"}
        assert {hit["uai"] for hit in by_commune["resultats"]} == expected
        assert {hit["uai"] for hit in by_postal["resultats"]} == expected

    def test_free_text_matches_canonical_commune_but_not_annexe_commune(
        self, client: TestClient
    ) -> None:
        canonical = self._search(client, q="ile rousse")
        annexe = self._search(client, q="AnnexeOnlyPlace")
        assert {hit["uai"] for hit in canonical["resultats"]} == {
            "9999801A",
            "9999802B",
        }
        assert annexe["resultats"] == []

    def test_exact_name_match_precedes_a_closer_prefix_match(
        self, client: TestClient
    ) -> None:
        body = self._search(
            client,
            q="École Jean-Jaurès",
            lat=ORIGIN_LAT,
            lng=ORIGIN_LNG,
            rayon_km=10,
        )
        hits = body["resultats"]
        assert [hit["uai"] for hit in hits[:2]] == ["9999801A", "9999802B"]
        assert hits[0]["distance_km"] > hits[1]["distance_km"]
        assert body["tri"] == "correspondance_puis_proximite"

    def test_text_paging_is_stable_and_non_overlapping(
        self, client: TestClient
    ) -> None:
        first = self._search(client, q="ecole", limit=1, offset=0)
        second = self._search(client, q="ecole", limit=1, offset=1)
        assert first["nombre_total"] == second["nombre_total"] == 2
        assert first["resultats"][0]["uai"] != second["resultats"][0]["uai"]

    def test_new_search_modes_still_refuse_caller_selected_sort(
        self, client: TestClient
    ) -> None:
        response = client.get(
            "/establishments/search",
            params={"q": "ecole", "sort_by": "taux_reussite"},
        )
        assert response.status_code == 400
