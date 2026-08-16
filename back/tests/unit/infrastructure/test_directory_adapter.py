"""Unit tests for DirectoryAdapter (DATA-3).

Rules protected here:

1. THE MANDATORY TEST — a schema mismatch must abort `fetch_establishments`
   before a single row is exported/parsed (see CLAUDE.md and
   docs/05_Resultats_Spike_Technique.md). Covered both for the original
   directory fields and, separately, for the offer-descriptor fields added
   in Phase 2 (ticket API-2) — a schema-mismatch test must never be skipped
   for a data source / ingestion change, per CLAUDE.md's workflow section.
2. Multi-site grouping — one Establishment per UAI, carrying every site,
   with a deterministic (source-order-independent) site sequence.
3. Filiere/section flag parsing — the directory types these inconsistently
   (`voie_*`/`section_*`/`segpa` as "0"/"1" strings, `ulis` as a plain
   integer), unions them across every site of a multi-site UAI, and must
   serialize them in a stable (enum declaration) order regardless of input
   order.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from src.domain.enums import EstablishmentType, Filiere, Section, Sector
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


class TestSchemaMismatchOnOfferDescriptorFields:
    """DATA source / ingestion change — the schema-mismatch case is required
    by CLAUDE.md for any change touching a source field, including the
    Phase 2 `voie_*`/`section_*`/`ulis` offer descriptors. A missing offer
    field must abort ingestion exactly like a missing identity field would —
    it must never be silently read back as "this establishment offers
    nothing", which would be a fabricated fact, not an absence.
    """

    def test_fetch_establishments_raises_when_voie_generale_disappears(
        self, respx_mock: respx.MockRouter
    ) -> None:
        missing_field = "voie_generale"
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
        assert exports_route.call_count == 0

    def test_fetch_establishments_raises_when_ulis_disappears(
        self, respx_mock: respx.MockRouter
    ) -> None:
        # `ulis` is the one integer-typed flag among the offer descriptors —
        # worth its own case since it is handled by a different branch of
        # `flag_is_set` than the "0"/"1" string fields.
        missing_field = "ulis"
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
        assert exports_route.call_count == 0


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


class TestFilieresAndSectionsParsing:
    """API-2's `filiere` search filter and the fact-sheet identity block both
    depend on this. The directory is not type-consistent: `voie_*` /
    `section_*` / `segpa` publish "0"/"1" strings, `ulis` publishes a plain
    integer 0/1 — both must parse via `flag_is_set`.
    """

    def test_voie_string_flags_parse_when_set(self) -> None:
        row = directory_row("0750001A", voie_generale="1")
        establishment = DirectoryAdapter.build_establishments([row])[0]
        assert establishment.filieres == (Filiere.GENERALE,)

    def test_section_string_flags_parse_when_set(self) -> None:
        row = directory_row("0750001A", section_europeenne="1")
        establishment = DirectoryAdapter.build_establishments([row])[0]
        assert establishment.sections == (Section.EUROPEENNE,)

    def test_the_integer_typed_ulis_field_parses_when_set(self) -> None:
        row = directory_row("0750001A", ulis=1)
        establishment = DirectoryAdapter.build_establishments([row])[0]
        assert establishment.sections == (Section.ULIS,)

    def test_ulis_set_to_the_integer_zero_reads_as_not_set(self) -> None:
        row = directory_row("0750001A", ulis=0)
        establishment = DirectoryAdapter.build_establishments([row])[0]
        assert Section.ULIS not in establishment.sections

    @pytest.mark.parametrize("absent_value", [None, "", "0"])
    def test_absent_null_and_zero_string_flags_read_as_not_set(
        self, absent_value: object
    ) -> None:
        row = directory_row("0750001A", voie_generale=absent_value)
        establishment = DirectoryAdapter.build_establishments([row])[0]
        assert Filiere.GENERALE not in establishment.filieres

    def test_an_unexpected_flag_label_reads_as_not_set_rather_than_raising(
        self,
    ) -> None:
        row = directory_row("0750001A", voie_generale="oui")
        establishment = DirectoryAdapter.build_establishments([row])[0]
        assert Filiere.GENERALE not in establishment.filieres

    def test_flags_are_unioned_across_every_site_of_a_multi_site_uai(self) -> None:
        uai = "0250047R"
        rows = [
            directory_row(
                uai,
                nom_etablissement="Site A",
                voie_generale="1",
                voie_professionnelle="0",
            ),
            directory_row(
                uai,
                nom_etablissement="Site B",
                voie_generale="0",
                voie_professionnelle="1",
            ),
        ]

        establishment = DirectoryAdapter.build_establishments(rows)[0]

        assert set(establishment.filieres) == {
            Filiere.GENERALE,
            Filiere.PROFESSIONNELLE,
        }

    def test_a_flag_present_at_only_one_annexe_site_is_not_lost(self) -> None:
        uai = "0250047R"
        rows = [
            directory_row(uai, nom_etablissement="Main site", ulis=0),
            directory_row(uai, nom_etablissement="Annexe", ulis=1),
        ]

        establishment = DirectoryAdapter.build_establishments(rows)[0]

        assert Section.ULIS in establishment.sections

    def test_filieres_serialize_in_enum_declaration_order_regardless_of_input(
        self,
    ) -> None:
        row = directory_row(
            "0750001A",
            voie_professionnelle="1",
            voie_generale="1",
            voie_technologique="1",
        )

        establishment = DirectoryAdapter.build_establishments([row])[0]

        assert establishment.filieres == (
            Filiere.GENERALE,
            Filiere.TECHNOLOGIQUE,
            Filiere.PROFESSIONNELLE,
        )

    def test_sections_serialize_in_enum_declaration_order_regardless_of_input(
        self,
    ) -> None:
        row = directory_row(
            "0750001A",
            segpa="1",
            ulis=1,
            section_theatre="1",
            section_cinema="1",
            section_arts="1",
            section_sport="1",
            section_internationale="1",
            section_europeenne="1",
        )

        establishment = DirectoryAdapter.build_establishments([row])[0]

        assert establishment.sections == (
            Section.EUROPEENNE,
            Section.INTERNATIONALE,
            Section.SPORT,
            Section.ARTS,
            Section.CINEMA,
            Section.THEATRE,
            Section.ULIS,
            Section.SEGPA,
        )

    def test_no_flags_set_yields_empty_tuples(self) -> None:
        row = directory_row("0750001A")
        establishment = DirectoryAdapter.build_establishments([row])[0]
        assert establishment.filieres == ()
        assert establishment.sections == ()
