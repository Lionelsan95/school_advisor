"""Application rules for deterministic official-commune lookup."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.application.ports import CommuneSearchHit
from src.application.search_communes import (
    MAX_COMMUNE_LIMIT,
    InvalidCommuneSearchError,
    MissingCommuneSourceError,
    SearchCommunes,
)
from src.domain.commune import Commune
from src.domain.dataset_ids import DATASET_COMMUNES
from src.domain.source_reference import SourceReference


class FakeCommuneReader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.hits = (
            CommuneSearchHit(
                commune=Commune(
                    code="92022",
                    name="Chaville",
                    postal_codes=("92370",),
                    department_code="92",
                    latitude=48.8091,
                    longitude=2.191,
                ),
                match_tier=2,
            ),
        )

    def search(self, query: str, limit: int) -> tuple[CommuneSearchHit, ...]:
        self.calls.append((query, limit))
        return self.hits


class FakeSourceReader:
    def __init__(self, include_communes: bool = True) -> None:
        self.reference = SourceReference(
            dataset_id=DATASET_COMMUNES,
            url="https://geo.api.gouv.fr/decoupage-administratif/communes",
            last_synchronised_at=datetime(2026, 8, 15, tzinfo=UTC),
            source_published_at=None,
        )
        self.include_communes = include_communes

    def all_by_dataset_id(self) -> dict[str, SourceReference]:
        return {DATASET_COMMUNES: self.reference} if self.include_communes else {}


@pytest.mark.parametrize("query", ["", " ", "a", "-", "---", "' ! '"])
def test_blank_short_or_punctuation_only_queries_are_rejected(query: str) -> None:
    reader = FakeCommuneReader()

    with pytest.raises(InvalidCommuneSearchError, match="q must contain"):
        SearchCommunes(reader, FakeSourceReader()).run(query)

    assert reader.calls == []


@pytest.mark.parametrize("limit", [0, -1, MAX_COMMUNE_LIMIT + 1])
def test_out_of_range_limit_is_rejected_before_reading(limit: int) -> None:
    reader = FakeCommuneReader()

    with pytest.raises(InvalidCommuneSearchError, match="limit"):
        SearchCommunes(reader, FakeSourceReader()).run("Chaville", limit)

    assert reader.calls == []


def test_success_returns_hits_and_the_exact_official_provenance() -> None:
    reader = FakeCommuneReader()
    sources = FakeSourceReader()

    results = SearchCommunes(reader, sources).run("  Chaville  ", limit=5)

    assert reader.calls == [("Chaville", 5)]
    assert results.hits == reader.hits
    assert results.source is sources.reference


def test_missing_provenance_withholds_lookup_before_querying_places() -> None:
    reader = FakeCommuneReader()

    with pytest.raises(MissingCommuneSourceError, match=DATASET_COMMUNES):
        SearchCommunes(reader, FakeSourceReader(include_communes=False)).run("Chaville")

    assert reader.calls == []
