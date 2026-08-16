"""Ports — the interfaces the application layer depends on.

Adapters live in `infrastructure/` and are injected. Nothing in this module
may import from `infrastructure/`; that direction of dependency is what keeps
the domain testable without a database or a network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.domain.commune import Commune
from src.domain.enums import EstablishmentType, Filiere, Sector
from src.domain.establishment import Establishment
from src.domain.indicator_result import IndicatorResult
from src.domain.source_reference import SourceReference


class DirectorySource(Protocol):
    """Reads establishments from the national education directory."""

    def fetch_establishments(self) -> list[Establishment]:
        """Return every establishment, one entry per UAI, sites grouped.

        Implementations must raise `SourceSchemaMismatchError` rather than return a
        partial or silently-wrong result when the upstream shape changes.
        """
        ...

    def source_references(self) -> list[SourceReference]:
        """Provenance of the datasets this source read (F10)."""
        ...


class IndicatorSource(Protocol):
    """Reads published result indicators (IVAC / IVAL GT / IVAL PRO)."""

    def fetch_indicators(self) -> list[IndicatorResult]: ...

    def source_references(self) -> list[SourceReference]: ...


class CommuneSource(Protocol):
    """Reads the official commune reference before request time."""

    def fetch_communes(self) -> list[Commune]: ...

    def source_references(self) -> list[SourceReference]: ...


class EstablishmentRepository(Protocol):
    def replace_all(self, establishments: list[Establishment]) -> int:
        """Load a full new snapshot. Returns the number of establishments."""
        ...

    def count(self) -> int: ...


class IndicatorRepository(Protocol):
    def append(self, indicators: list[IndicatorResult]) -> int:
        """Insert rows, ignoring any (uai, year, type) already stored.

        Never updates an existing row: history is append-only so that a past
        year cannot be rewritten by a later ingestion run.
        """
        ...

    def count(self) -> int: ...


class CommuneRepository(Protocol):
    def replace_all(self, communes: list[Commune]) -> int: ...

    def count(self) -> int: ...


class SourceReferenceRepository(Protocol):
    """Write side for F10 provenance, populated at the end of each run."""

    def snapshot(self) -> None: ...

    def upsert(self, reference: SourceReference) -> None: ...


# ---------------------------------------------------------------------------
# Read side (Phase 2). Kept separate from the ingestion write ports above:
# they have different lifetimes, different callers, and nothing that serves an
# HTTP request should be able to reach a `replace_all`.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SearchCriteria:
    """Filters accepted by `GET /establishments/search`.

    Note what this deliberately cannot express: there is no sort field and no
    result-indicator filter. Ordering is decided by the reader implementation
    from the criteria below (proximity when a location is given, alphabetical
    otherwise), so no caller — including a future LLM agent — can ask for an
    establishment list ordered by results.
    """

    text_query: str | None = None
    commune_code: str | None = None
    postal_code: str | None = None
    establishment_type: EstablishmentType | None = None
    sector: Sector | None = None
    filiere: Filiere | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float | None = None
    limit: int = 20
    offset: int = 0

    @property
    def has_location(self) -> bool:
        return (
            self.latitude is not None
            and self.longitude is not None
            and self.radius_km is not None
        )


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One search result, with its distance when a location filter applied."""

    establishment: Establishment
    distance_km: float | None = None


@dataclass(frozen=True, slots=True)
class SearchResults:
    hits: tuple[SearchHit, ...]
    total_count: int


class EstablishmentReader(Protocol):
    def get_by_uai(self, uai: str) -> Establishment | None: ...

    def search(self, criteria: SearchCriteria) -> SearchResults: ...


class IndicatorReader(Protocol):
    def list_for_establishment(self, uai: str) -> list[IndicatorResult]:
        """Every published row for this UAI, most recent year first."""
        ...


class SourceReferenceReader(Protocol):
    def all_by_dataset_id(self) -> dict[str, SourceReference]: ...


@dataclass(frozen=True, slots=True)
class CommuneSearchHit:
    commune: Commune
    match_tier: int


class CommuneReader(Protocol):
    def search(self, query: str, limit: int) -> tuple[CommuneSearchHit, ...]: ...
