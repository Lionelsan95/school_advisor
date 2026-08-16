"""Unit tests for CompareEstablishments (API-8 / F4).

No database, no network — mirrors the fake-reader pattern already used in
`test_get_establishment_history.py` and `test_get_establishment_fact_sheet.py`.
What this use case adds over those two, and what these tests protect:

- Rows are the UNION of the two establishments' years, never the intersection.
  Dropping a year one establishment published because the other did not would
  hide real published data to make the table tidy — see the module docstring
  in `compare_establishments.py`.
- Cells within a row follow the *requested* uai order, never database or
  alphabetical order — a caller must be able to rely on which column is
  which.
- Comparing fewer or more than two establishments, or the same establishment
  twice, is rejected outright (`InvalidComparisonError`) rather than silently
  truncated or deduplicated.
- An unknown uai and a missing source reference are handled exactly as the
  fact sheet and history use cases handle them: `None` for the former,
  propagation for the latter — this use case must not swallow either.
"""

from __future__ import annotations

import pytest

from src.application.compare_establishments import (
    MAX_COMPARED,
    MIN_COMPARED,
    CompareEstablishments,
    InvalidComparisonError,
)
from src.application.errors import MissingSourceReferenceError
from src.application.ports import SearchCriteria, SearchResults
from src.domain.dataset_ids import DATASET_IVAC, DATASET_IVAL_GT
from src.domain.enums import EstablishmentType, IndicatorType
from src.domain.establishment import Establishment
from src.domain.indicator_result import IndicatorResult
from src.domain.source_reference import SourceReference
from tests.unit.factories import (
    make_establishment,
    make_indicator_results,
    make_source_reference,
)

UAI_A = "0750001A"
UAI_B = "0750002B"


class FakeEstablishmentReader:
    """Implements `EstablishmentReader`; `search` is unused by this use case."""

    def __init__(self, establishments: dict[str, Establishment]) -> None:
        self._establishments = establishments

    def get_by_uai(self, uai: str) -> Establishment | None:
        return self._establishments.get(uai)

    def search(self, criteria: SearchCriteria) -> SearchResults:
        raise NotImplementedError("not exercised by CompareEstablishments")


class FakeIndicatorReader:
    def __init__(self, results: list[IndicatorResult]) -> None:
        self._results = results

    def list_for_establishment(self, uai: str) -> list[IndicatorResult]:
        return [result for result in self._results if result.uai == uai]


class FakeSourceReferenceReader:
    def __init__(self, references: dict[str, SourceReference]) -> None:
        self._references = references

    def all_by_dataset_id(self) -> dict[str, SourceReference]:
        return self._references


def _use_case(
    establishments: dict[str, Establishment],
    results: list[IndicatorResult],
    references: dict[str, SourceReference],
) -> CompareEstablishments:
    return CompareEstablishments(
        establishments=FakeEstablishmentReader(establishments),
        indicators=FakeIndicatorReader(results),
        sources=FakeSourceReferenceReader(references),
    )


class TestYearAlignmentIsTheUnionNotTheIntersection:
    """The heart of API-8. A (a lycée) publishes IVAL GT 2012-2025 (14 years);
    B (a collège) publishes IVAC 2022-2025 only (4 years) — the realistic case
    per CLAUDE.md's IVAC/IVAL depth gotcha. The comparison must show 14 rows,
    not 4, with B's cell explicitly unpublished for the 10 years it has none.
    """

    def _comparison(self):
        establishments = {
            UAI_A: make_establishment(uai=UAI_A, type=EstablishmentType.LYCEE),
            UAI_B: make_establishment(uai=UAI_B, type=EstablishmentType.COLLEGE),
        }
        results = [
            *make_indicator_results(UAI_A, range(2012, 2026), IndicatorType.IVAL_GT),
            *make_indicator_results(UAI_B, range(2022, 2026), IndicatorType.IVAC),
        ]
        references = {
            DATASET_IVAL_GT: make_source_reference(DATASET_IVAL_GT),
            DATASET_IVAC: make_source_reference(DATASET_IVAC),
        }
        comparison = _use_case(establishments, results, references).run([UAI_A, UAI_B])
        assert comparison is not None
        return comparison

    def test_rows_are_the_union_of_years_fourteen_not_four(self) -> None:
        comparison = self._comparison()
        assert len(comparison.rows) == 14
        assert {row.year for row in comparison.rows} == set(range(2012, 2026))

    def test_rows_are_ordered_most_recent_year_first(self) -> None:
        comparison = self._comparison()
        years = [row.year for row in comparison.rows]
        assert years == sorted(years, reverse=True)
        assert years[0] == 2025
        assert years[-1] == 2012

    def test_a_year_only_a_published_leaves_bs_cell_unpublished_not_dropped(
        self,
    ) -> None:
        comparison = self._comparison()
        row_2013 = next(row for row in comparison.rows if row.year == 2013)
        cell_a, cell_b = row_2013.cells

        assert cell_a.uai == UAI_A
        assert cell_a.row is not None
        assert cell_a.has_published_year is True

        assert cell_b.uai == UAI_B
        assert cell_b.row is None
        assert cell_b.has_published_year is False

    def test_a_year_both_published_carries_two_populated_cells(self) -> None:
        comparison = self._comparison()
        row_2023 = next(row for row in comparison.rows if row.year == 2023)

        assert all(cell.row is not None for cell in row_2023.cells)
        assert all(cell.has_published_year for cell in row_2023.cells)


class TestCellOrderFollowsRequestedUaiOrder:
    """A caller must be able to rely on which column is which — the shape
    does not sort by UAI value or by whatever order the database happened to
    return establishments in.
    """

    def test_cells_follow_the_requested_order_not_alphabetical(self) -> None:
        # UAI_B > UAI_A alphabetically; requesting [B, A] is the reverse of
        # alphabetical order, so a sort-based bug would flip this back.
        establishments = {
            UAI_A: make_establishment(uai=UAI_A),
            UAI_B: make_establishment(uai=UAI_B),
        }
        results = [
            *make_indicator_results(UAI_A, [2025]),
            *make_indicator_results(UAI_B, [2025]),
        ]
        references = {DATASET_IVAC: make_source_reference(DATASET_IVAC)}

        comparison = _use_case(establishments, results, references).run([UAI_B, UAI_A])

        assert comparison is not None
        assert [e.uai for e in comparison.establishments] == [UAI_B, UAI_A]
        for row in comparison.rows:
            assert [cell.uai for cell in row.cells] == [UAI_B, UAI_A]


class TestValidationRejectsRatherThanSilentlyTruncating:
    """Every case here must raise `InvalidComparisonError` with a message a
    caller can actually understand — never truncate a list of three down to
    two, and never silently drop a duplicate.
    """

    def test_min_and_max_compared_are_both_exactly_two(self) -> None:
        assert MIN_COMPARED == MAX_COMPARED == 2

    def test_a_single_uai_raises_with_a_comprehensible_message(self) -> None:
        use_case = _use_case({}, [], {})
        with pytest.raises(InvalidComparisonError, match="2 establishments"):
            use_case.run([UAI_A])

    def test_zero_uais_also_raises(self) -> None:
        use_case = _use_case({}, [], {})
        with pytest.raises(InvalidComparisonError, match="2 establishments"):
            use_case.run([])

    def test_three_uais_raises_with_a_comprehensible_message(self) -> None:
        use_case = _use_case({}, [], {})
        with pytest.raises(InvalidComparisonError, match="2 establishments"):
            use_case.run([UAI_A, UAI_B, "0750003C"])

    def test_the_same_uai_twice_raises_a_distinct_duplicate_message(self) -> None:
        use_case = _use_case({}, [], {})
        with pytest.raises(InvalidComparisonError, match="must be different"):
            use_case.run([UAI_A, UAI_A])


class TestUnknownUaiReturnsNone:
    def test_returns_none_when_the_first_uai_is_unknown(self) -> None:
        establishments = {UAI_B: make_establishment(uai=UAI_B)}
        use_case = _use_case(establishments, [], {})
        assert use_case.run([UAI_A, UAI_B]) is None

    def test_returns_none_when_the_second_uai_is_unknown(self) -> None:
        establishments = {UAI_A: make_establishment(uai=UAI_A)}
        use_case = _use_case(establishments, [], {})
        assert use_case.run([UAI_A, UAI_B]) is None

    def test_returns_none_when_both_uais_are_unknown(self) -> None:
        use_case = _use_case({}, [], {})
        assert use_case.run([UAI_A, UAI_B]) is None


class TestMissingSourceReferencePropagates:
    def test_a_missing_source_reference_raises_instead_of_being_swallowed(
        self,
    ) -> None:
        establishments = {
            UAI_A: make_establishment(uai=UAI_A),
            UAI_B: make_establishment(uai=UAI_B),
        }
        results = [
            *make_indicator_results(UAI_A, [2025], IndicatorType.IVAC),
            *make_indicator_results(UAI_B, [2025], IndicatorType.IVAC),
        ]
        # No source references at all: to_result_row must raise rather than
        # return a row with no traceable provenance.
        use_case = _use_case(establishments, results, {})

        with pytest.raises(MissingSourceReferenceError, match=DATASET_IVAC):
            use_case.run([UAI_A, UAI_B])
