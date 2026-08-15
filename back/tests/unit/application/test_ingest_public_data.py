"""Unit tests for IngestPublicData (DATA-5) — the quality gates.

Uses fake in-memory implementations of the ports (no database, no network).
docs/02_Architecture_Decisions.md calls silent ingestion failure the
project's most critical blind spot, so every gate here must (a) raise a
loud, typed exception and (b) leave both repositories completely untouched.
"""

from __future__ import annotations

import pytest

from src.application.errors import SuspiciousIngestionError
from src.application.ingest_public_data import IngestPublicData, QualityGates
from src.domain.establishment import Establishment
from src.domain.indicator_result import IndicatorResult
from tests.unit.factories import make_establishment, make_indicator_result


class FakeDirectorySource:
    def __init__(self, establishments: list[Establishment]) -> None:
        self._establishments = establishments
        self.call_count = 0

    def fetch_establishments(self) -> list[Establishment]:
        self.call_count += 1
        return self._establishments


class FakeIndicatorSource:
    def __init__(self, indicators: list[IndicatorResult]) -> None:
        self._indicators = indicators
        self.call_count = 0

    def fetch_indicators(self) -> list[IndicatorResult]:
        self.call_count += 1
        return self._indicators


class FakeEstablishmentRepository:
    def __init__(self) -> None:
        self.replace_all_calls: list[list[Establishment]] = []

    def replace_all(self, establishments: list[Establishment]) -> int:
        self.replace_all_calls.append(establishments)
        return len(establishments)

    def count(self) -> int:
        return len(self.replace_all_calls[-1]) if self.replace_all_calls else 0

    def known_uais(self) -> set[str]:
        return {e.uai for call in self.replace_all_calls for e in call}


class FakeIndicatorRepository:
    def __init__(self) -> None:
        self.append_calls: list[list[IndicatorResult]] = []

    def append(self, indicators: list[IndicatorResult]) -> int:
        self.append_calls.append(indicators)
        return len(indicators)

    def count(self) -> int:
        return sum(len(call) for call in self.append_calls)


def _establishments(uais: list[str]) -> list[Establishment]:
    return [make_establishment(uai=uai) for uai in uais]


def _indicators(uais: list[str]) -> list[IndicatorResult]:
    return [make_indicator_result(uai=uai) for uai in uais]


# Small thresholds so tests don't need to fabricate tens of thousands of
# fixtures to exercise the gates.
TEST_GATES = QualityGates(min_establishments=3, min_indicators=3, min_match_rate=0.5)


def _build(
    establishments: list[Establishment],
    indicators: list[IndicatorResult],
    gates: QualityGates = TEST_GATES,
) -> tuple[
    IngestPublicData,
    FakeEstablishmentRepository,
    FakeIndicatorRepository,
    FakeIndicatorSource,
]:
    directory = FakeDirectorySource(establishments)
    indicator_source = FakeIndicatorSource(indicators)
    establishment_repo = FakeEstablishmentRepository()
    indicator_repo = FakeIndicatorRepository()
    use_case = IngestPublicData(
        directory, indicator_source, establishment_repo, indicator_repo, gates
    )
    return use_case, establishment_repo, indicator_repo, indicator_source


class TestCollapsedDirectoryIsRefused:
    def test_raises_and_persists_nothing(self) -> None:
        establishments = _establishments(["0750001A", "0750002B"])  # 2 < min 3
        indicators = _indicators(["0750001A", "0750002B", "0750003C"])
        use_case, establishment_repo, indicator_repo, indicator_source = _build(
            establishments, indicators
        )

        with pytest.raises(SuspiciousIngestionError):
            use_case.run()

        assert establishment_repo.replace_all_calls == []
        assert indicator_repo.append_calls == []
        # The run must abort before even fetching indicators.
        assert indicator_source.call_count == 0


class TestLowIndicatorVolumeIsRefused:
    def test_raises_and_persists_nothing(self) -> None:
        establishments = _establishments(["0750001A", "0750002B", "0750003C"])
        indicators = _indicators(["0750001A", "0750002B"])  # 2 < min 3
        use_case, establishment_repo, indicator_repo, _ = _build(
            establishments, indicators
        )

        with pytest.raises(SuspiciousIngestionError):
            use_case.run()

        assert establishment_repo.replace_all_calls == []
        assert indicator_repo.append_calls == []


class TestLowMatchRateIsRefused:
    def test_raises_and_persists_nothing(self) -> None:
        establishments = _establishments(["0750001A", "0750002B", "0750003C"])
        # 1 matched of 4 total = 25%, below the 50% floor used by these tests.
        indicators = _indicators(["0750001A", "9990001A", "9990002B", "9990003C"])
        use_case, establishment_repo, indicator_repo, _ = _build(
            establishments, indicators
        )

        with pytest.raises(SuspiciousIngestionError):
            use_case.run()

        assert establishment_repo.replace_all_calls == []
        assert indicator_repo.append_calls == []


class TestMatchRateBoundary:
    """The gate compares with `<`, not `<=` — protect that exact behaviour."""

    def test_match_rate_exactly_at_the_floor_is_accepted(self) -> None:
        establishments = _establishments(["0750001A", "0750002B", "0750003C"])
        # 3 matched of 4 total = exactly 0.75, equal to the floor below.
        indicators = _indicators(["0750001A", "0750002B", "0750003C", "9990001A"])
        gates = QualityGates(
            min_establishments=3, min_indicators=3, min_match_rate=0.75
        )
        use_case, establishment_repo, indicator_repo, _ = _build(
            establishments, indicators, gates=gates
        )

        report = use_case.run()

        assert report.succeeded is True
        assert report.match_rate == pytest.approx(0.75)
        assert len(establishment_repo.replace_all_calls) == 1
        assert len(indicator_repo.append_calls) == 1

    def test_match_rate_just_below_the_floor_is_refused(self) -> None:
        establishments = _establishments(["0750001A", "0750002B", "0750003C"])
        # 3 matched of 5 total = 0.6, below a 0.75 floor.
        indicators = _indicators(
            ["0750001A", "0750002B", "0750003C", "9990001A", "9990002B"]
        )
        gates = QualityGates(
            min_establishments=3, min_indicators=3, min_match_rate=0.75
        )
        use_case, establishment_repo, indicator_repo, _ = _build(
            establishments, indicators, gates=gates
        )

        with pytest.raises(SuspiciousIngestionError):
            use_case.run()

        assert establishment_repo.replace_all_calls == []
        assert indicator_repo.append_calls == []


class TestHealthyRunPersistsAndReports:
    def test_persists_and_reports_the_correct_match_rate_and_unmatched_uais(
        self,
    ) -> None:
        establishments = _establishments(["0750001A", "0750002B", "0750003C"])
        indicators = _indicators(["0750001A", "0750002B", "0750003C", "9990001A"])
        use_case, establishment_repo, indicator_repo, _ = _build(
            establishments, indicators
        )

        report = use_case.run()

        assert report.succeeded is True
        assert report.failure_reason is None
        assert report.establishments_loaded == 3
        assert report.indicators_loaded == 4
        assert report.indicators_seen == 4
        assert report.match_rate == pytest.approx(3 / 4)
        assert report.unmatched_uais == ["9990001A"]
        assert len(establishment_repo.replace_all_calls) == 1
        assert len(indicator_repo.append_calls) == 1
        assert establishment_repo.replace_all_calls[0] == establishments
        assert indicator_repo.append_calls[0] == indicators

    def test_unmatched_uais_are_reported_never_silently_dropped(self) -> None:
        establishments = _establishments(["0750001A", "0750002B", "0750003C"])
        # 6 matched rows (2 per known UAI) + 2 unmatched = 8 total, rate 0.75.
        indicators = _indicators(
            [
                "0750001A",
                "0750001A",
                "0750002B",
                "0750002B",
                "0750003C",
                "0750003C",
                "9990001A",
                "9990002B",
            ]
        )
        use_case, _establishment_repo, indicator_repo, _ = _build(
            establishments, indicators
        )

        report = use_case.run()

        assert report.succeeded is True
        assert set(report.unmatched_uais) == {"9990001A", "9990002B"}
        assert report.indicators_loaded == len(indicators)
        # Every row, matched or not, is still persisted — unmatched means
        # "no directory entry to join against", not "discarded".
        assert len(indicator_repo.append_calls[0]) == len(indicators)
