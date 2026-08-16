"""Unit tests for GetEstablishmentHistory (API-7 / F5).

No database, no network: the readers are plain fakes implementing the ports
in `application/ports.py` directly, mirroring the pattern already used in
`test_get_establishment_fact_sheet.py`.

What this use case adds over the fact sheet — and what these tests protect:

- Points come back **ascending** by year, the opposite of the fact sheet's
  most-recent-first order (see the module docstring in
  `get_establishment_history.py`).
- A year the source never published is simply absent, never invented.
- A missing SourceReference is a hard failure (`MissingSourceReferenceError`),
  exactly as it is for the fact sheet — this use case must not swallow it.
"""

from __future__ import annotations

import pytest

from src.application.errors import MissingSourceReferenceError
from src.application.get_establishment_fact_sheet import GetEstablishmentFactSheet
from src.application.get_establishment_history import GetEstablishmentHistory
from src.application.ports import SearchCriteria, SearchResults
from src.domain.dataset_ids import DATASET_IVAC, DATASET_IVAL_GT, DATASET_IVAL_PRO
from src.domain.enums import IndicatorType
from src.domain.establishment import Establishment
from src.domain.indicator_result import IndicatorResult
from src.domain.methodology_break import IVAL_BACCALAUREAT_REFORM
from src.domain.source_reference import SourceReference
from tests.unit.factories import (
    make_establishment,
    make_indicator_result,
    make_source_reference,
)


class FakeEstablishmentReader:
    """Implements `EstablishmentReader`; `search` is unused by this use case."""

    def __init__(self, establishments: dict[str, Establishment]) -> None:
        self._establishments = establishments

    def get_by_uai(self, uai: str) -> Establishment | None:
        return self._establishments.get(uai)

    def search(self, criteria: SearchCriteria) -> SearchResults:
        raise NotImplementedError("not exercised by GetEstablishmentHistory")


class FakeIndicatorReader:
    def __init__(self, results: list[IndicatorResult]) -> None:
        self._results = results

    def list_for_establishment(self, uai: str) -> list[IndicatorResult]:
        # Mirrors the real Postgres reader: most recent year first. The use
        # case is responsible for re-ordering, so a fake that already
        # returned ascending order could hide a bug in that responsibility.
        return sorted(
            (result for result in self._results if result.uai == uai),
            key=lambda result: (-result.year, result.indicator_type.value),
        )


class FakeSourceReferenceReader:
    def __init__(self, references: dict[str, SourceReference]) -> None:
        self._references = references

    def all_by_dataset_id(self) -> dict[str, SourceReference]:
        return self._references


def _use_case(
    establishments: dict[str, Establishment],
    results: list[IndicatorResult],
    references: dict[str, SourceReference],
) -> GetEstablishmentHistory:
    return GetEstablishmentHistory(
        establishments=FakeEstablishmentReader(establishments),
        indicators=FakeIndicatorReader(results),
        sources=FakeSourceReferenceReader(references),
    )


class TestUnknownUai:
    def test_returns_none_for_an_unknown_uai(self) -> None:
        use_case = _use_case({}, [], {})
        assert use_case.run("0750001A") is None


class TestPointsAreOrderedAscendingUnlikeTheFactSheet:
    """The whole reason this use case exists rather than reusing the fact
    sheet directly — a chart reads left to right, a record reads
    most-recent-first. Assert the two use cases actually disagree.
    """

    def test_points_are_sorted_ascending_by_year(self) -> None:
        uai = "0750001A"
        establishment = make_establishment(uai=uai)
        results = [
            make_indicator_result(
                uai=uai, year=year, indicator_type=IndicatorType.IVAL_GT
            )
            for year in (2023, 2019, 2021)
        ]
        references = {DATASET_IVAL_GT: make_source_reference(DATASET_IVAL_GT)}

        history = _use_case({uai: establishment}, results, references).run(uai)

        assert history is not None
        assert [point.year for point in history.points] == [2019, 2021, 2023]

    def test_ascending_history_order_differs_from_the_descending_fact_sheet(
        self,
    ) -> None:
        uai = "0750001A"
        establishment = make_establishment(uai=uai)
        results = [
            make_indicator_result(
                uai=uai, year=year, indicator_type=IndicatorType.IVAL_GT
            )
            for year in (2023, 2019, 2021)
        ]
        references = {DATASET_IVAL_GT: make_source_reference(DATASET_IVAL_GT)}

        history = _use_case({uai: establishment}, results, references).run(uai)
        fact_sheet = GetEstablishmentFactSheet(
            establishments=FakeEstablishmentReader({uai: establishment}),
            indicators=FakeIndicatorReader(results),
            sources=FakeSourceReferenceReader(references),
        ).run(uai)

        assert history is not None
        assert fact_sheet is not None
        history_years = [point.year for point in history.points]
        fact_sheet_years = [row.year for row in fact_sheet.results]
        assert history_years == [2019, 2021, 2023]
        assert fact_sheet_years == [2023, 2021, 2019]
        assert history_years != fact_sheet_years
        assert history_years == list(reversed(fact_sheet_years))

    def test_same_year_different_indicator_types_are_ordered_by_type_too(
        self,
    ) -> None:
        uai = "0750001A"
        establishment = make_establishment(uai=uai)
        results = [
            make_indicator_result(
                uai=uai, year=2022, indicator_type=IndicatorType.IVAL_PRO
            ),
            make_indicator_result(
                uai=uai, year=2022, indicator_type=IndicatorType.IVAL_GT
            ),
        ]
        references = {
            DATASET_IVAL_GT: make_source_reference(DATASET_IVAL_GT),
            DATASET_IVAL_PRO: make_source_reference(DATASET_IVAL_PRO),
        }

        history = _use_case({uai: establishment}, results, references).run(uai)

        assert history is not None
        assert [point.indicator_type for point in history.points] == [
            IndicatorType.IVAL_GT,
            IndicatorType.IVAL_PRO,
        ]


class TestCoveredYears:
    def test_covered_years_is_sorted_and_deduplicated(self) -> None:
        uai = "0750001A"
        establishment = make_establishment(uai=uai)
        results = [
            make_indicator_result(
                uai=uai, year=2023, indicator_type=IndicatorType.IVAC
            ),
            make_indicator_result(
                uai=uai, year=2022, indicator_type=IndicatorType.IVAC
            ),
        ]
        references = {DATASET_IVAC: make_source_reference(DATASET_IVAC)}

        history = _use_case({uai: establishment}, results, references).run(uai)

        assert history is not None
        assert history.covered_years == (2022, 2023)


class TestMissingSourceReferencePropagates:
    def test_a_missing_source_reference_raises_instead_of_being_swallowed(
        self,
    ) -> None:
        uai = "0750001A"
        establishment = make_establishment(uai=uai)
        result = make_indicator_result(uai=uai, indicator_type=IndicatorType.IVAC)

        use_case = _use_case({uai: establishment}, [result], {})

        with pytest.raises(MissingSourceReferenceError):
            use_case.run(uai)


class TestGapYearsAreLeftAbsentNeverInvented:
    """docs/14_Charte_Neutralite_Editoriale.md §10: "années manquantes
    laissées vides" — a year the source never published must not appear as a
    placeholder or interpolated point.
    """

    def test_a_year_never_published_is_simply_not_in_points(self) -> None:
        uai = "0750001A"
        establishment = make_establishment(uai=uai)
        results = [
            make_indicator_result(
                uai=uai, year=2019, indicator_type=IndicatorType.IVAL_GT
            ),
            # 2020 is deliberately absent from the source.
            make_indicator_result(
                uai=uai, year=2021, indicator_type=IndicatorType.IVAL_GT
            ),
        ]
        references = {DATASET_IVAL_GT: make_source_reference(DATASET_IVAL_GT)}

        history = _use_case({uai: establishment}, results, references).run(uai)

        assert history is not None
        assert history.covered_years == (2019, 2021)
        assert 2020 not in history.covered_years
        assert len(history.points) == 2


class TestMethodologyBreakIsAttachedWhenTheHistorySpansIt:
    def test_break_present_when_years_span_2021(self) -> None:
        uai = "0750001A"
        establishment = make_establishment(uai=uai)
        results = [
            make_indicator_result(
                uai=uai, year=year, indicator_type=IndicatorType.IVAL_GT
            )
            for year in (2019, 2020, 2021, 2022)
        ]
        references = {DATASET_IVAL_GT: make_source_reference(DATASET_IVAL_GT)}

        history = _use_case({uai: establishment}, results, references).run(uai)

        assert history is not None
        assert history.methodology_breaks == (IVAL_BACCALAUREAT_REFORM,)

    def test_no_break_when_only_ivac_years_are_present(self) -> None:
        uai = "0750001A"
        establishment = make_establishment(uai=uai)
        results = [
            make_indicator_result(uai=uai, year=year, indicator_type=IndicatorType.IVAC)
            for year in (2022, 2023, 2024, 2025)
        ]
        references = {DATASET_IVAC: make_source_reference(DATASET_IVAC)}

        history = _use_case({uai: establishment}, results, references).run(uai)

        assert history is not None
        assert history.methodology_breaks == ()
