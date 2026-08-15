"""Unit tests for DirectoryAdapter (DATA-3).

Two rules are protected here:

1. THE MANDATORY TEST — a schema mismatch must abort `fetch_establishments`
   before a single row is exported/parsed (see CLAUDE.md and
   docs/05_Resultats_Spike_Technique.md).
2. Multi-site grouping — one Establishment per UAI, carrying every site,
   with a deterministic (source-order-independent) site sequence.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from src.domain.enums import EstablishmentType, Sector
from src.infrastructure.ingestion.directory_adapter import (
    DIRECTORY_FIELDS,
    DirectoryAdapter,
)
from src.infrastructure.ingestion.errors import SourceSchemaMismatchError
from src.infrastructure.ingestion.ods_client import (
    DATASET_DIRECTORY,
    DEFAULT_BASE_URL,
    OdsClient,
)
from tests.unit.factories import directory_row

CATALOG_URL = f"{DEFAULT_BASE_URL}/catalog/datasets/{DATASET_DIRECTORY}"
EXPORTS_URL = f"{DEFAULT_BASE_URL}/catalog/datasets/{DATASET_DIRECTORY}/exports/json"


class TestSchemaMismatchAbortsBeforeParsing:
    """THE MANDATORY TEST, at the adapter boundary.

    A renamed/removed directory column must abort the whole run before a
    single row is parsed — never be silently read back as null.
    """

    def test_fetch_establishments_raises_and_never_calls_exports(
        self, respx_mock: respx.MockRouter
    ) -> None:
        missing_field = "identifiant_de_l_etablissement"
        catalog_fields = [name for name in DIRECTORY_FIELDS if name != missing_field]
        respx_mock.get(CATALOG_URL).mock(
            return_value=httpx.Response(
                200, json={"fields": [{"name": n} for n in catalog_fields]}
            )
        )
        exports_route = respx_mock.get(EXPORTS_URL).mock(
            return_value=httpx.Response(200, json=[directory_row()])
        )
        adapter = DirectoryAdapter(OdsClient())

        with pytest.raises(SourceSchemaMismatchError) as excinfo:
            adapter.fetch_establishments()

        assert missing_field in excinfo.value.missing
        assert excinfo.value.dataset_id == DATASET_DIRECTORY
        assert exports_route.call_count == 0, (
            "the export endpoint must never be reached once the schema "
            "check fails — a renamed column must never be read as null"
        )


class TestMultiSiteGrouping:
    """DATA-3 — one Establishment per UAI, no site ever dropped, and a
    deterministic ordering (docs/04_Journal_Decisions.md, "Modelling note").
    """

    def test_two_rows_sharing_a_uai_become_one_establishment_with_two_sites(
        self,
    ) -> None:
        uai = "0250047R"
        rows = [
            directory_row(
                uai,
                nom_etablissement="Collège Olympe de Gouges site de Pont de Roide",
                code_postal="25620",
            ),
            directory_row(
                uai,
                nom_etablissement="Collège Olympe de Gouges site de Saint-Hyppolyte",
                code_postal="25190",
            ),
        ]

        establishments = DirectoryAdapter.build_establishments(rows)

        assert len(establishments) == 1
        establishment = establishments[0]
        assert establishment.uai == uai
        assert len(establishment.sites) == 2
        assert establishment.is_multi_site is True

    def test_three_rows_sharing_a_uai_keep_all_three_sites(self) -> None:
        uai = "0250099Z"
        rows = [
            directory_row(uai, nom_etablissement="Site C", code_postal="25003"),
            directory_row(uai, nom_etablissement="Site A", code_postal="25001"),
            directory_row(uai, nom_etablissement="Site B", code_postal="25002"),
        ]

        establishments = DirectoryAdapter.build_establishments(rows)

        assert len(establishments) == 1
        assert len(establishments[0].sites) == 3
        assert {site.name for site in establishments[0].sites} == {
            "Site A",
            "Site B",
            "Site C",
        }

    def test_no_site_is_ever_dropped_across_several_uais(self) -> None:
        rows = [
            directory_row("0250047R", nom_etablissement="Site 1"),
            directory_row("0250047R", nom_etablissement="Site 2"),
            directory_row("0750001A", nom_etablissement="Single site school"),
        ]

        establishments = DirectoryAdapter.build_establishments(rows)

        assert sum(len(e.sites) for e in establishments) == len(rows)

    def test_grouping_and_canonical_site_are_stable_across_input_order(self) -> None:
        uai = "0250047R"
        site_1 = directory_row(uai, nom_etablissement="Site Alpha", code_postal="25001")
        site_2 = directory_row(uai, nom_etablissement="Site Beta", code_postal="25002")
        site_3 = directory_row(uai, nom_etablissement="Site Gamma", code_postal="25003")

        forward_run = DirectoryAdapter.build_establishments([site_1, site_2, site_3])
        shuffled_run = DirectoryAdapter.build_establishments([site_3, site_1, site_2])

        assert forward_run[0].sites == shuffled_run[0].sites
        assert forward_run[0].canonical_site == shuffled_run[0].canonical_site
        assert forward_run[0].canonical_site.name == "Site Alpha"

    def test_rerunning_on_identical_input_reproduces_the_same_grouping(self) -> None:
        rows = [
            directory_row("0250047R", nom_etablissement="Site Alpha"),
            directory_row("0250047R", nom_etablissement="Site Beta"),
        ]

        run_a = DirectoryAdapter.build_establishments(rows)
        run_b = DirectoryAdapter.build_establishments(list(rows))

        assert run_a[0].sites == run_b[0].sites


class TestFieldMapping:
    def test_maps_type_sector_and_open_state(self) -> None:
        row = directory_row(
            "0750001A",
            type_etablissement="lycée",
            statut_public_prive="privé",
            etat="FERME",
        )

        establishment = DirectoryAdapter.build_establishments([row])[0]

        assert establishment.type is EstablishmentType.LYCEE
        assert establishment.sector is Sector.PRIVATE
        assert establishment.is_open is False

    def test_only_ouvert_state_is_considered_open(self) -> None:
        row = directory_row("0750001A", etat="OUVERT")
        establishment = DirectoryAdapter.build_establishments([row])[0]
        assert establishment.is_open is True

    def test_missing_or_unparseable_coordinates_become_none(self) -> None:
        row = directory_row("0750001A", latitude="", longitude="not-a-number")
        site = DirectoryAdapter.build_establishments([row])[0].canonical_site
        assert site.latitude is None
        assert site.longitude is None


class TestInvalidUaiRowsAreSkippedNotRepaired:
    def test_a_malformed_uai_row_is_dropped_but_does_not_crash_the_import(
        self,
    ) -> None:
        rows = [
            directory_row("BAD-UAI"),
            directory_row("0750001A"),
        ]

        establishments = DirectoryAdapter.build_establishments(rows)

        assert len(establishments) == 1
        assert establishments[0].uai == "0750001A"
