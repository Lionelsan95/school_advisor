"""Unit tests for `search_establishments.validate` (API-2).

`SearchCriteria` cannot express a result-based sort at all (see
`ports.py`), so there is nothing to test for that here — the guarantee is
structural. What `validate` protects is well-formedness: limits, offsets,
and a location that is either fully specified or absent, never partial.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.application.ports import SearchCriteria, SearchHit, SearchResults
from src.application.search_establishments import (
    MAX_LIMIT,
    InvalidSearchError,
    MissingSearchSourceError,
    SearchEstablishments,
    validate,
)
from src.domain.dataset_ids import DATASET_DIRECTORY
from src.domain.source_reference import SourceReference
from tests.unit.factories import make_establishment


class FakeEstablishmentReader:
    def __init__(self) -> None:
        self.calls: list[SearchCriteria] = []
        self.results = SearchResults(
            hits=(SearchHit(establishment=make_establishment()),),
            total_count=1,
        )

    def search(self, criteria: SearchCriteria) -> SearchResults:
        self.calls.append(criteria)
        return self.results


class FakeSourceReader:
    def __init__(self, include_directory: bool = True) -> None:
        self.reference = SourceReference(
            dataset_id=DATASET_DIRECTORY,
            url="https://data.education.gouv.fr/explore/dataset/fr-en-annuaire-education/",
            last_synchronised_at=datetime(2026, 8, 15, tzinfo=UTC),
            source_published_at=None,
        )
        self.include_directory = include_directory

    def all_by_dataset_id(self) -> dict[str, SourceReference]:
        return {DATASET_DIRECTORY: self.reference} if self.include_directory else {}


def _criteria(**overrides: Any) -> SearchCriteria:
    return SearchCriteria(**overrides)


class TestLimitValidation:
    def test_limit_below_one_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="limit"):
            validate(_criteria(limit=0))

    def test_negative_limit_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="limit"):
            validate(_criteria(limit=-5))

    def test_limit_above_the_maximum_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="limit"):
            validate(_criteria(limit=MAX_LIMIT + 1))

    def test_limit_at_the_boundaries_is_accepted(self) -> None:
        validate(_criteria(limit=1))
        validate(_criteria(limit=MAX_LIMIT))


class TestOffsetValidation:
    def test_negative_offset_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="offset"):
            validate(_criteria(offset=-1))

    def test_zero_offset_is_accepted(self) -> None:
        validate(_criteria(offset=0))

    def test_a_large_offset_is_accepted(self) -> None:
        validate(_criteria(offset=10_000))


class TestPartialLocationIsRejected:
    def test_latitude_alone_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="together"):
            validate(_criteria(latitude=48.85))

    def test_latitude_and_longitude_without_radius_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="together"):
            validate(_criteria(latitude=48.85, longitude=2.35))

    def test_radius_alone_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="together"):
            validate(_criteria(radius_km=10.0))

    def test_longitude_and_radius_without_latitude_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="together"):
            validate(_criteria(longitude=2.35, radius_km=10.0))


class TestOutOfRangeLocationValuesAreRejected:
    def test_latitude_above_90_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="lat"):
            validate(_criteria(latitude=90.1, longitude=2.35, radius_km=10.0))

    def test_latitude_below_minus_90_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="lat"):
            validate(_criteria(latitude=-90.1, longitude=2.35, radius_km=10.0))

    def test_longitude_above_180_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="lng"):
            validate(_criteria(latitude=48.85, longitude=180.1, radius_km=10.0))

    def test_longitude_below_minus_180_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="lng"):
            validate(_criteria(latitude=48.85, longitude=-180.1, radius_km=10.0))

    def test_zero_radius_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="radius_km"):
            validate(_criteria(latitude=48.85, longitude=2.35, radius_km=0))

    def test_negative_radius_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="radius_km"):
            validate(_criteria(latitude=48.85, longitude=2.35, radius_km=-1.0))

    def test_radius_above_100_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="radius_km"):
            validate(_criteria(latitude=48.85, longitude=2.35, radius_km=100.1))


class TestValidCriteriaAreAccepted:
    def test_a_valid_full_location_criteria_raises_nothing(self) -> None:
        validate(_criteria(latitude=48.85, longitude=2.35, radius_km=10.0))

    def test_a_valid_location_at_the_extreme_bounds_raises_nothing(self) -> None:
        validate(_criteria(latitude=90.0, longitude=180.0, radius_km=100.0))
        validate(_criteria(latitude=-90.0, longitude=-180.0, radius_km=0.1))

    def test_no_location_at_all_raises_nothing(self) -> None:
        validate(_criteria())


class TestTextAndLocalityValidation:
    @pytest.mark.parametrize("query", ["", " ", "a", "-", "---", "' ! '"])
    def test_blank_short_or_punctuation_only_text_is_rejected(self, query: str) -> None:
        with pytest.raises(InvalidSearchError, match="q must contain"):
            validate(_criteria(text_query=query))

    @pytest.mark.parametrize("query", ["École", "2B134", "92370", "Jean-Jaurès"])
    def test_meaningful_text_is_accepted(self, query: str) -> None:
        validate(_criteria(text_query=query))

    def test_blank_commune_code_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="commune_code"):
            validate(_criteria(commune_code="  "))

    def test_blank_postal_code_is_rejected(self) -> None:
        with pytest.raises(InvalidSearchError, match="code_postal"):
            validate(_criteria(postal_code="  "))


class TestSearchProvenance:
    def test_success_returns_results_with_the_exact_directory_source(self) -> None:
        reader = FakeEstablishmentReader()
        sources = FakeSourceReader()
        criteria = _criteria(text_query="Test school")

        response = SearchEstablishments(reader, sources).run(criteria)

        assert reader.calls == [criteria]
        assert response.results is reader.results
        assert response.source is sources.reference
        assert response.source.dataset_id == DATASET_DIRECTORY

    def test_missing_directory_source_withholds_results_before_searching(self) -> None:
        reader = FakeEstablishmentReader()

        with pytest.raises(MissingSearchSourceError, match=DATASET_DIRECTORY):
            SearchEstablishments(
                reader,
                FakeSourceReader(include_directory=False),
            ).run(_criteria(text_query="Test school"))

        assert reader.calls == []
