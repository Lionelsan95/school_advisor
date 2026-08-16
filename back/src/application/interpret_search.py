"""Bounded natural-language interpretation types and provider port."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Protocol

from src.application.ports import SourceReferenceReader
from src.domain.enums import EstablishmentType, Filiere, Sector


class InterpreterUnavailableError(RuntimeError):
    """The optional language-model interpreter cannot produce a valid intent."""


class LocationMode(StrEnum):
    EXACT_COMMUNE = "commune_exacte"
    AROUND = "autour"


@dataclass(frozen=True, slots=True)
class InterpretedSearch:
    """Only factual fields that the deterministic search boundary accepts."""

    text_query: str | None = None
    place_query: str | None = None
    postal_code: str | None = None
    establishment_type: EstablishmentType | None = None
    sector: Sector | None = None
    filiere: Filiere | None = None
    radius_km: float | None = None
    location_mode: LocationMode | None = None
    needs_location: bool = False


class QueryInterpreter(Protocol):
    @property
    def cache_identity(self) -> str: ...

    def interpret(self, query: str) -> InterpretedSearch: ...


class InterpretationCache(Protocol):
    def get(self, key: str) -> InterpretedSearch | None: ...

    def put(self, key: str, value: InterpretedSearch) -> None: ...


class InterpretationVersionProvider(Protocol):
    def current_version(self) -> str: ...


class SourceBackedInterpretationVersion:
    """Stable token that changes with provenance or approved content."""

    def __init__(
        self,
        sources: SourceReferenceReader,
        content_version: str,
    ) -> None:
        self._sources = sources
        self._content_version = content_version

    def current_version(self) -> str:
        references = self._sources.all_by_dataset_id()
        parts = [f"content:{self._content_version}"]
        for dataset_id, reference in sorted(references.items()):
            parts.append(
                "|".join(
                    (
                        dataset_id,
                        reference.url,
                        reference.last_synchronised_at.isoformat(),
                        (
                            reference.source_published_at.isoformat()
                            if reference.source_published_at is not None
                            else ""
                        ),
                    )
                )
            )
        return sha256("\n".join(parts).encode()).hexdigest()
