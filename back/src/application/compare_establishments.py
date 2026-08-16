"""API-8 / F4 — placing establishments side by side.

The editorial charter (§11) is unusually specific about this feature. The word
"comparaison" means putting data in parallel, not evaluating it, and the
product must not compute: a count of criteria won, an average of indicators, an
overall gap, a weighted score, a textual verdict, or a final recommendation.

The design answer is the same one used for `Figure`'s missing `variant` prop:
make the forbidden thing un-buildable rather than merely absent.

**Rows are aligned here, in the backend.** The obvious alternative — return two
fact sheets and let the frontend zip them by year — puts the two values for a
year side by side in client code, which is precisely where subtracting them
becomes the natural next line. Pre-aligning server-side means the frontend
receives cells it can render but has no pair to difference: there is no step in
which A and B are both in hand as numbers awaiting an operation.

A year one establishment published and the other did not is a real and common
case (IVAC covers 2022-2025, IVAL 2012-2025). It is represented explicitly, so
an absence never renders as a blank that reads like a loss.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.get_establishment_fact_sheet import ResultRow, to_result_row
from src.application.ports import (
    EstablishmentReader,
    IndicatorReader,
    SourceReferenceReader,
)
from src.domain.establishment import Establishment

# Two, per docs/01_Vision_Produit.md (F4) and docs/13_Inventaire_Ecrans_Etats.md
# §9, whose acceptance criterion and fixed A/B mobile layout both assume two.
# docs/07 says "two (max three)"; the two more detailed specifications win, and
# nothing anywhere describes a three-column layout.
MAX_COMPARED = 2
MIN_COMPARED = 2


class InvalidComparisonError(ValueError):
    """The requested comparison cannot be honoured as asked.

    Surfaced as a 400. Never silently truncated to a valid list: a caller who
    asked for three establishments and received two would reasonably believe
    they were looking at all three.
    """


@dataclass(frozen=True, slots=True)
class ComparisonCell:
    """One establishment's data for one year.

    `row is None` means this establishment published nothing for this year at
    all — distinct from a published row whose individual figures are absent.
    Conflating the two would misstate what is known.
    """

    uai: str
    row: ResultRow | None

    @property
    def has_published_year(self) -> bool:
        return self.row is not None


@dataclass(frozen=True, slots=True)
class ComparisonRow:
    """One year, with one cell per compared establishment, in request order."""

    year: int
    cells: tuple[ComparisonCell, ...]


@dataclass(frozen=True, slots=True)
class Comparison:
    establishments: tuple[Establishment, ...]
    rows: tuple[ComparisonRow, ...]


class CompareEstablishments:
    def __init__(
        self,
        establishments: EstablishmentReader,
        indicators: IndicatorReader,
        sources: SourceReferenceReader,
    ) -> None:
        self._establishments = establishments
        self._indicators = indicators
        self._sources = sources

    def run(self, uais: list[str]) -> Comparison | None:
        self._validate(uais)

        found: list[Establishment] = []
        for uai in uais:
            establishment = self._establishments.get_by_uai(uai)
            if establishment is None:
                return None
            found.append(establishment)

        sources = self._sources.all_by_dataset_id()
        rows_by_uai: dict[str, dict[int, ResultRow]] = {}
        for uai in uais:
            rows_by_uai[uai] = {
                row.year: row
                for row in (
                    to_result_row(result, sources)
                    for result in self._indicators.list_for_establishment(uai)
                )
            }

        # The union of years, most recent first. Using the union rather than
        # the intersection is deliberate: dropping a year one establishment
        # published, because the other did not, would hide real published data
        # to make the table tidy.
        years = sorted(
            {year for rows in rows_by_uai.values() for year in rows}, reverse=True
        )

        return Comparison(
            establishments=tuple(found),
            rows=tuple(
                ComparisonRow(
                    year=year,
                    cells=tuple(
                        ComparisonCell(uai=uai, row=rows_by_uai[uai].get(year))
                        for uai in uais
                    ),
                )
                for year in years
            ),
        )

    def _validate(self, uais: list[str]) -> None:
        if len(uais) < MIN_COMPARED or len(uais) > MAX_COMPARED:
            raise InvalidComparisonError(
                f"exactly {MAX_COMPARED} establishments must be supplied to compare"
            )
        if len(set(uais)) != len(uais):
            # Comparing an establishment with itself produces two identical
            # columns, which looks like a result and is not one.
            raise InvalidComparisonError(
                "the establishments to compare must be different"
            )
