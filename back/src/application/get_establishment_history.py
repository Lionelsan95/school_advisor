"""API-7 / F5 — the multi-year series behind the history chart.

Deliberately thin. Everything it returns already exists on the fact sheet; what
this use case adds is ordering and the methodology-break annotation, both of
which exist for the chart's sake:

- Years come back **ascending**, because a chart is read left to right, while
  the fact sheet lists most-recent-first as a reader of a record expects.
- Breaks are attached only when this establishment's own history spans one.

Nothing here computes a trend, a slope, a moving average or a projection, and
there is no field in which one could be returned. The charter (§10) forbids
them, and the shape is what makes them absent rather than merely unused.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.get_establishment_fact_sheet import ResultRow, to_result_row
from src.application.ports import (
    EstablishmentReader,
    IndicatorReader,
    SourceReferenceReader,
)
from src.domain.enums import IndicatorType
from src.domain.establishment import Establishment
from src.domain.methodology_break import MethodologyBreak, breaks_spanned_by


@dataclass(frozen=True, slots=True)
class EstablishmentHistory:
    establishment: Establishment
    # Ascending by year. One row per (year, indicator series) actually
    # published — a year the source never published is simply absent, never
    # filled in with a placeholder point.
    points: tuple[ResultRow, ...]
    methodology_breaks: tuple[MethodologyBreak, ...]

    @property
    def covered_years(self) -> tuple[int, ...]:
        return tuple(sorted({row.year for row in self.points}))


class GetEstablishmentHistory:
    def __init__(
        self,
        establishments: EstablishmentReader,
        indicators: IndicatorReader,
        sources: SourceReferenceReader,
    ) -> None:
        self._establishments = establishments
        self._indicators = indicators
        self._sources = sources

    def run(self, uai: str) -> EstablishmentHistory | None:
        establishment = self._establishments.get_by_uai(uai)
        if establishment is None:
            return None

        sources = self._sources.all_by_dataset_id()
        results = self._indicators.list_for_establishment(uai)

        points = tuple(
            sorted(
                (to_result_row(result, sources) for result in results),
                key=lambda row: (row.year, row.indicator_type.value),
            )
        )

        years_by_type: dict[IndicatorType, set[int]] = {}
        for row in points:
            years_by_type.setdefault(row.indicator_type, set()).add(row.year)

        return EstablishmentHistory(
            establishment=establishment,
            points=points,
            methodology_breaks=breaks_spanned_by(years_by_type),
        )
