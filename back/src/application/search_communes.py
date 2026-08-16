"""Deterministic official-place lookup used before establishment search."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.ports import (
    CommuneReader,
    CommuneSearchHit,
    SourceReferenceReader,
)
from src.domain.dataset_ids import DATASET_COMMUNES
from src.domain.source_reference import SourceReference

MAX_COMMUNE_LIMIT = 20
DEFAULT_COMMUNE_LIMIT = 10


class InvalidCommuneSearchError(ValueError):
    """The place query is too broad or its page size is invalid."""


class MissingCommuneSourceError(RuntimeError):
    """The locality reference exists without its required provenance."""


@dataclass(frozen=True, slots=True)
class CommuneSearchResults:
    hits: tuple[CommuneSearchHit, ...]
    source: SourceReference


class SearchCommunes:
    def __init__(self, communes: CommuneReader, sources: SourceReferenceReader) -> None:
        self._communes = communes
        self._sources = sources

    def run(
        self, query: str, limit: int = DEFAULT_COMMUNE_LIMIT
    ) -> CommuneSearchResults:
        cleaned = query.strip()
        if len(cleaned) < 2 or not any(char.isalnum() for char in cleaned):
            raise InvalidCommuneSearchError(
                "q must contain at least 2 characters, including a letter or digit"
            )
        if not 1 <= limit <= MAX_COMMUNE_LIMIT:
            raise InvalidCommuneSearchError(
                f"limit must be between 1 and {MAX_COMMUNE_LIMIT}"
            )
        source = self._sources.all_by_dataset_id().get(DATASET_COMMUNES)
        if source is None:
            raise MissingCommuneSourceError(
                f"Missing source reference for {DATASET_COMMUNES}"
            )
        return CommuneSearchResults(
            hits=self._communes.search(cleaned, limit), source=source
        )
