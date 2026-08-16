"""API-2 — filtered, factual list of establishments.

Thin by design: the reader does the filtering in SQL, and this use case exists
to hold the one rule that must not live in a router or in an adapter — that a
search may be ordered by proximity or by name, and by nothing else.

`SearchCriteria` cannot express a result-based sort, so the guarantee is
structural rather than a check that a future caller could forget to run. The
router additionally rejects an explicit `sort_by` request with 400 instead of
ignoring it, so a consumer asking for a ranking is told no rather than served
a list they may read as one.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.ports import (
    EstablishmentReader,
    SearchCriteria,
    SearchResults,
    SourceReferenceReader,
)
from src.domain.dataset_ids import DATASET_DIRECTORY
from src.domain.source_reference import SourceReference

# A single page must stay small enough that the result set reads as "some
# establishments matching your filters", not as a leaderboard to scroll.
MAX_LIMIT = 100
DEFAULT_LIMIT = 20


class InvalidSearchError(ValueError):
    """The criteria cannot be honoured as asked. Surfaced as 400, not ignored."""


class MissingSearchSourceError(RuntimeError):
    """The directory facts exist without their required provenance."""


@dataclass(frozen=True, slots=True)
class EstablishmentSearchResponse:
    results: SearchResults
    source: SourceReference


def validate(criteria: SearchCriteria) -> None:
    """Reject criteria that are incoherent rather than quietly repairing them."""
    if criteria.limit < 1 or criteria.limit > MAX_LIMIT:
        raise InvalidSearchError(f"limit must be between 1 and {MAX_LIMIT}")
    if criteria.offset < 0:
        raise InvalidSearchError("offset must not be negative")
    if criteria.text_query is not None:
        text_query = criteria.text_query.strip()
        if len(text_query) < 2 or not any(char.isalnum() for char in text_query):
            raise InvalidSearchError(
                "q must contain at least 2 characters, including a letter or digit"
            )
    if criteria.commune_code is not None and not criteria.commune_code.strip():
        raise InvalidSearchError("commune_code must not be empty")
    if criteria.postal_code is not None and not criteria.postal_code.strip():
        raise InvalidSearchError("code_postal must not be empty")

    located = (criteria.latitude, criteria.longitude, criteria.radius_km)
    if any(value is not None for value in located) and not criteria.has_location:
        raise InvalidSearchError(
            "lat, lng and radius_km must be provided together to filter by location"
        )
    if criteria.latitude is not None and not -90 <= criteria.latitude <= 90:
        raise InvalidSearchError("lat must be between -90 and 90")
    if criteria.longitude is not None and not -180 <= criteria.longitude <= 180:
        raise InvalidSearchError("lng must be between -180 and 180")
    if criteria.radius_km is not None and not 0 < criteria.radius_km <= 100:
        raise InvalidSearchError("radius_km must be between 0 and 100")


class SearchEstablishments:
    def __init__(
        self,
        establishments: EstablishmentReader,
        sources: SourceReferenceReader,
    ) -> None:
        self._establishments = establishments
        self._sources = sources

    def run(self, criteria: SearchCriteria) -> EstablishmentSearchResponse:
        validate(criteria)
        source = self._sources.all_by_dataset_id().get(DATASET_DIRECTORY)
        if source is None:
            raise MissingSearchSourceError(
                f"Missing source reference for {DATASET_DIRECTORY}"
            )
        return EstablishmentSearchResponse(
            results=self._establishments.search(criteria), source=source
        )
