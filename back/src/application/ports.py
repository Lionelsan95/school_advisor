"""Ports — the interfaces the application layer depends on.

Adapters live in `infrastructure/` and are injected. Nothing in this module
may import from `infrastructure/`; that direction of dependency is what keeps
the domain testable without a database or a network.
"""

from __future__ import annotations

from typing import Protocol

from src.domain.establishment import Establishment
from src.domain.indicator_result import IndicatorResult


class DirectorySource(Protocol):
    """Reads establishments from the national education directory."""

    def fetch_establishments(self) -> list[Establishment]:
        """Return every establishment, one entry per UAI, sites grouped.

        Implementations must raise `SourceSchemaMismatchError` rather than return a
        partial or silently-wrong result when the upstream shape changes.
        """
        ...


class IndicatorSource(Protocol):
    """Reads published result indicators (IVAC / IVAL GT / IVAL PRO)."""

    def fetch_indicators(self) -> list[IndicatorResult]: ...


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
