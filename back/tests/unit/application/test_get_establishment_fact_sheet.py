"""Unit tests for GetEstablishmentFactSheet and its helpers (API-1).

No database, no network: the readers are plain fakes implementing the ports
in `application/ports.py` directly. Two rules are protected here, both
called out in the module docstring of `get_establishment_fact_sheet.py`:

- `expected_rate` never partially reconstructs a figure from one term alone.
- `last_synchronised_at` must still reflect the directory sync even when an
  establishment carries zero indicator results — this was a real bug, caught
  by an integration test rather than by reading the code, so it gets a
  regression test here too.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.application.errors import MissingSourceReferenceError
from src.application.get_establishment_fact_sheet import (
    Figure,
    GetEstablishmentFactSheet,
    expected_rate,
)
from src.application.ports import SearchCriteria, SearchResults
from src.domain.dataset_ids import DATASET_DIRECTORY, DATASET_IVAC
from src.domain.enums import IndicatorType
from src.domain.establishment import Establishment
from src.domain.indicator_result import IndicatorResult
from src.domain.source_reference import SourceReference
from tests.unit.factories import make_establishment, make_indicator_result


class FakeEstablishmentReader:
    """Implements `EstablishmentReader`; `search` is unused by this use case."""

    def __init__(self, establishments: dict[str, Establishment]) -> None:
        self._establishments = establishments

    def get_by_uai(self, uai: str) -> Establishment | None:
        return self._establishments.get(uai)

    def search(self, criteria: SearchCriteria) -> SearchResults:
        raise NotImplementedError("not exercised by GetEstablishmentFactSheet")


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


def _reference(dataset_id: str, synced_at: datetime) -> SourceReference:
    return SourceReference(
        dataset_id=dataset_id,
        url=f"https://example.invalid/{dataset_id}",
        last_synchronised_at=synced_at,
    )


class TestExpectedRateArithmetic:
    def test_correct_arithmetic(self) -> None:
        figure = expected_rate(observed=94.0, value_added=-3.0)
        assert figure.value == 97.0

    def test_a_positive_value_added_lowers_the_expected_rate(self) -> None:
        figure = expected_rate(observed=90.0, value_added=4.0)
        assert figure.value == 86.0


class TestExpectedRateAbsence:
    def test_absent_when_observed_is_none(self) -> None:
        figure = expected_rate(observed=None, value_added=-3.0)
        assert figure.value is None

    def test_absent_when_value_added_is_none(self) -> None:
        figure = expected_rate(observed=94.0, value_added=None)
        assert figure.value is None

    def test_absent_when_both_terms_are_none(self) -> None:
        figure = expected_rate(observed=None, value_added=None)
        assert figure.value is None

    def test_an_absent_result_is_never_flagged_computed(self) -> None:
        """It must never be partially reconstructed from the one term present."""
        figure = expected_rate(observed=94.0, value_added=None)
        assert figure.computed is False
        assert figure.computation_note is None


class TestExpectedRateIsFlaggedComputed:
    def test_a_present_result_is_computed_with_a_note(self) -> None:
        figure = expected_rate(observed=94.0, value_added=-3.0)
        assert figure.computed is True
        assert figure.computation_note
        assert isinstance(figure.computation_note, str)


class TestFigureInvariants:
    def test_computed_without_a_note_raises(self) -> None:
        with pytest.raises(ValueError, match="computation note"):
            Figure(value=1.0, computed=True, computation_note=None)

    def test_a_note_without_computed_raises(self) -> None:
        with pytest.raises(ValueError, match="must not carry"):
            Figure(value=1.0, computed=False, computation_note="some note")

    def test_a_raw_present_figure_is_valid(self) -> None:
        figure = Figure(value=1.0)
        assert figure.is_present is True
        assert figure.computed is False

    def test_an_absent_figure_is_valid(self) -> None:
        figure = Figure(value=None)
        assert figure.is_present is False


class TestUnknownUai:
    def test_returns_none_for_an_unknown_uai(self) -> None:
        use_case = GetEstablishmentFactSheet(
            establishments=FakeEstablishmentReader({}),
            indicators=FakeIndicatorReader([]),
            sources=FakeSourceReferenceReader({}),
        )
        assert use_case.run("0750001A") is None


class TestSourceMappingPerIndicatorType:
    def test_a_result_row_carries_the_source_for_its_dataset_via_indicator_type(
        self,
    ) -> None:
        establishment = make_establishment(uai="0750001A")
        result = make_indicator_result(
            uai="0750001A", indicator_type=IndicatorType.IVAC
        )
        references = {
            DATASET_IVAC: _reference(DATASET_IVAC, datetime(2026, 1, 1, tzinfo=UTC)),
        }
        use_case = GetEstablishmentFactSheet(
            establishments=FakeEstablishmentReader({"0750001A": establishment}),
            indicators=FakeIndicatorReader([result]),
            sources=FakeSourceReferenceReader(references),
        )

        sheet = use_case.run("0750001A")

        assert sheet is not None
        assert len(sheet.results) == 1
        assert sheet.results[0].source is not None
        assert sheet.results[0].source.dataset_id == DATASET_IVAC

    def test_missing_dataset_reference_fails_instead_of_returning_an_orphan_number(
        self,
    ) -> None:
        establishment = make_establishment(uai="0750001A")
        result = make_indicator_result(
            uai="0750001A", indicator_type=IndicatorType.IVAC
        )
        use_case = GetEstablishmentFactSheet(
            establishments=FakeEstablishmentReader({"0750001A": establishment}),
            indicators=FakeIndicatorReader([result]),
            sources=FakeSourceReferenceReader({}),
        )

        with pytest.raises(
            MissingSourceReferenceError,
            match="fr-en-indicateurs-valeur-ajoutee-colleges",
        ):
            use_case.run("0750001A")


class TestLastSynchronisedAtIncludesDirectoryEvenWithZeroResults:
    """Regression test — see the docstring in get_establishment_fact_sheet.py.

    Roughly two thirds of the directory (primary schools) carries no
    indicator at all. Without the directory reference in the `max()`, those
    fact sheets would report "never synchronised" for data that was in fact
    synced, indistinguishable from a broken pipeline.
    """

    def test_directory_timestamp_is_used_when_there_are_no_indicator_results(
        self,
    ) -> None:
        establishment = make_establishment(uai="0750001A")
        directory_synced_at = datetime(2026, 3, 1, tzinfo=UTC)
        references = {
            DATASET_DIRECTORY: _reference(DATASET_DIRECTORY, directory_synced_at),
        }
        use_case = GetEstablishmentFactSheet(
            establishments=FakeEstablishmentReader({"0750001A": establishment}),
            indicators=FakeIndicatorReader([]),
            sources=FakeSourceReferenceReader(references),
        )

        sheet = use_case.run("0750001A")

        assert sheet is not None
        assert sheet.results == ()
        assert sheet.last_synchronised_at == directory_synced_at

    def test_the_freshest_timestamp_wins_between_directory_and_indicator_sources(
        self,
    ) -> None:
        establishment = make_establishment(uai="0750001A")
        result = make_indicator_result(
            uai="0750001A", indicator_type=IndicatorType.IVAC
        )
        older = datetime(2026, 1, 1, tzinfo=UTC)
        newer = datetime(2026, 6, 1, tzinfo=UTC)
        references = {
            DATASET_DIRECTORY: _reference(DATASET_DIRECTORY, older),
            DATASET_IVAC: _reference(DATASET_IVAC, newer),
        }
        use_case = GetEstablishmentFactSheet(
            establishments=FakeEstablishmentReader({"0750001A": establishment}),
            indicators=FakeIndicatorReader([result]),
            sources=FakeSourceReferenceReader(references),
        )

        sheet = use_case.run("0750001A")

        assert sheet is not None
        assert sheet.last_synchronised_at == newer

    def test_none_when_there_is_no_source_reference_at_all(self) -> None:
        establishment = make_establishment(uai="0750001A")
        use_case = GetEstablishmentFactSheet(
            establishments=FakeEstablishmentReader({"0750001A": establishment}),
            indicators=FakeIndicatorReader([]),
            sources=FakeSourceReferenceReader({}),
        )

        sheet = use_case.run("0750001A")

        assert sheet is not None
        assert sheet.last_synchronised_at is None


class TestAbsentValueAddedYieldsAFigureWithNoValue:
    def test_absent_value_added_becomes_a_figure_with_value_none(self) -> None:
        establishment = make_establishment(uai="0750001A")
        result = make_indicator_result(uai="0750001A", value_added_success=None)
        references = {
            DATASET_IVAC: _reference(DATASET_IVAC, datetime(2026, 1, 1, tzinfo=UTC)),
        }
        use_case = GetEstablishmentFactSheet(
            establishments=FakeEstablishmentReader({"0750001A": establishment}),
            indicators=FakeIndicatorReader([result]),
            sources=FakeSourceReferenceReader(references),
        )

        sheet = use_case.run("0750001A")

        assert sheet is not None
        figure = sheet.results[0].value_added_success
        assert figure.value is None
        assert figure.is_present is False
        # And the figure derived from it (the expected rate) must also stay
        # absent, per TestExpectedRateAbsence above.
        assert sheet.results[0].expected_success_rate.value is None
