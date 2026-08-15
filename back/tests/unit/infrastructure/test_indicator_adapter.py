"""Unit tests for IndicatorAdapter (DATA-4).

Rules protected here:

1. THE MANDATORY TEST — a schema mismatch must abort `fetch_indicators`
   before a single row is exported/parsed.
2. Year parsing — ISO date strings (current datasets) and plain integers
   (legacy datasets) both parse; garbage never becomes a coerced year.
3. No-reason-inferred — nothing may derive the presence/absence of a
   value-added figure from `candidates_present`. This is the project's most
   important correctness constraint (docs/05_Resultats_Spike_Technique.md,
   section 3.2).
"""

from __future__ import annotations

import httpx
import pytest
import respx

from src.domain.enums import IndicatorType, Sector
from src.infrastructure.ingestion.errors import SourceSchemaMismatchError
from src.infrastructure.ingestion.indicator_adapter import (
    IVAC_SPEC,
    IVAL_GT_SPEC,
    IndicatorAdapter,
    parse_year,
)
from src.infrastructure.ingestion.ods_client import DEFAULT_BASE_URL, OdsClient
from tests.unit.factories import ivac_row, ival_gt_row

IVAC_CATALOG_URL = f"{DEFAULT_BASE_URL}/catalog/datasets/{IVAC_SPEC.dataset_id}"
IVAC_EXPORTS_URL = (
    f"{DEFAULT_BASE_URL}/catalog/datasets/{IVAC_SPEC.dataset_id}/exports/json"
)


class TestSchemaMismatchAbortsBeforeParsing:
    """THE MANDATORY TEST, at the adapter boundary."""

    def test_fetch_indicators_raises_and_never_calls_exports(
        self, respx_mock: respx.MockRouter
    ) -> None:
        missing_field = IVAC_SPEC.value_added_success_field
        catalog_fields = [name for name in IVAC_SPEC.fields if name != missing_field]
        respx_mock.get(IVAC_CATALOG_URL).mock(
            return_value=httpx.Response(
                200, json={"fields": [{"name": n} for n in catalog_fields]}
            )
        )
        exports_route = respx_mock.get(IVAC_EXPORTS_URL).mock(
            return_value=httpx.Response(200, json=[ivac_row()])
        )
        # Isolate to a single spec so the assertion is unambiguous about
        # which dataset triggered the abort.
        adapter = IndicatorAdapter(OdsClient(), specs=(IVAC_SPEC,))

        with pytest.raises(SourceSchemaMismatchError) as excinfo:
            adapter.fetch_indicators()

        assert missing_field in excinfo.value.missing
        assert excinfo.value.dataset_id == IVAC_SPEC.dataset_id
        assert exports_route.call_count == 0, (
            "the export endpoint must never be reached once the schema "
            "check fails — a renamed column must never be read as null"
        )


class TestYearParsing:
    def test_parses_current_dataset_iso_date_strings(self) -> None:
        assert parse_year("2025-01-01T00:00:00+00:00") == 2025

    def test_parses_legacy_plain_integers(self) -> None:
        assert parse_year(2018) == 2018

    @pytest.mark.parametrize(
        "garbage",
        [None, "", "abcd", "20", "   ", "not-a-year-at-all"],
    )
    def test_unparseable_values_return_none_rather_than_a_coerced_year(
        self, garbage: object
    ) -> None:
        assert parse_year(garbage) is None

    def test_a_row_with_an_unparseable_year_is_skipped_not_stored_wrongly(
        self,
    ) -> None:
        rows = [
            ivac_row("0750001A", session="not-a-date"),
            ivac_row("0750002B"),
        ]

        results = IndicatorAdapter.build_results(IVAC_SPEC, rows)

        assert len(results) == 1
        assert results[0].uai == "0750002B"


class TestNoReasonIsEverInferredForAnAbsentValue:
    """DATA-4 — the project's most important correctness constraint.

    docs/05_Resultats_Spike_Technique.md, section 3.2: the spike found IVAL
    GT rows *below* the documented 20-candidate threshold that still carry a
    value-added figure (75 of them, all 2016), and 457 rows *above* it with
    none — of which 186 have 50 candidates or more, and 113 of those are in
    Mayotte, where value-added is not computed at all. Nothing in the adapter
    may derive absence — or presence — from `candidates_present`.
    """

    def test_a_low_candidate_count_with_a_present_value_keeps_the_value(
        self,
    ) -> None:
        row = ival_gt_row("0750001A", presents_total=2, va_reu_total=-3.1)

        result = IndicatorAdapter.build_results(IVAL_GT_SPEC, [row])[0]

        assert result.candidates_present == 2
        assert result.value_added_success == -3.1
        assert result.has_value_added is True

    def test_a_high_candidate_count_with_an_absent_value_stays_absent(self) -> None:
        # Mirrors the Mayotte case (976xxxx UAIs): value-added is simply not
        # computed there, independently of the candidate count.
        row = ival_gt_row("9760001Z", presents_total=415, va_reu_total=None)

        result = IndicatorAdapter.build_results(IVAL_GT_SPEC, [row])[0]

        assert result.candidates_present == 415
        assert result.value_added_success is None
        assert result.has_value_added is False

    def test_candidate_count_and_value_presence_vary_independently(self) -> None:
        rows = [
            ival_gt_row("0750001A", presents_total=2, va_reu_total=-3.1),
            ival_gt_row("9760001Z", presents_total=415, va_reu_total=None),
            ival_gt_row("0750002B", presents_total=200, va_reu_total=1.5),
            ival_gt_row("0750003C", presents_total=5, va_reu_total=None),
        ]

        results = IndicatorAdapter.build_results(IVAL_GT_SPEC, rows)
        by_uai = {r.uai: r for r in results}

        assert by_uai["0750001A"].has_value_added is True  # low count, present
        assert by_uai["9760001Z"].has_value_added is False  # high count, absent
        assert by_uai["0750002B"].has_value_added is True  # high count, present
        assert by_uai["0750003C"].has_value_added is False  # low count, absent


class TestFieldMapping:
    def test_maps_ivac_row_to_the_right_indicator_type_and_sector(self) -> None:
        row = ivac_row("0750001A", secteur="privé")
        result = IndicatorAdapter.build_results(IVAC_SPEC, [row])[0]

        assert result.indicator_type is IndicatorType.IVAC
        assert result.sector is Sector.PRIVATE

    def test_maps_ival_gt_row_to_the_right_indicator_type(self) -> None:
        row = ival_gt_row("0750001A")
        result = IndicatorAdapter.build_results(IVAL_GT_SPEC, [row])[0]
        assert result.indicator_type is IndicatorType.IVAL_GT


class TestInvalidUaiRowsAreSkippedNotRepaired:
    def test_a_malformed_uai_row_is_dropped_but_does_not_crash_the_import(
        self,
    ) -> None:
        rows = [ivac_row("NOT-A-UAI"), ivac_row("0750001A")]

        results = IndicatorAdapter.build_results(IVAC_SPEC, rows)

        assert len(results) == 1
        assert results[0].uai == "0750001A"
