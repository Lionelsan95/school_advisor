"""API-1 — assemble the full fact sheet for one establishment.

Framework-free: it takes readers (ports) and returns plain dataclasses with
English field names. The French wire format is produced later, at the single
serialization boundary in `interfaces/api/schemas.py` — see the journal entry
"Identifiants de code en anglais, format JSON en français".

Two rules shape everything here:

- Nothing is ranked, scored, or compared against another establishment. The
  only comparison present is the one the source itself publishes: the observed
  result against the statistically expected one.
- No absent figure acquires a reason. `Figure` distinguishes *present* from
  *absent*; it has no field in which a cause could be recorded, so a future
  edit cannot casually add one without changing the type.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.application.errors import MissingSourceReferenceError
from src.application.ports import (
    EstablishmentReader,
    IndicatorReader,
    SourceReferenceReader,
)
from src.domain.dataset_ids import DATASET_DIRECTORY, INDICATOR_DATASET_IDS
from src.domain.enums import IndicatorType
from src.domain.establishment import Establishment
from src.domain.indicator_result import IndicatorResult
from src.domain.source_reference import SourceReference


@dataclass(frozen=True, slots=True)
class Figure:
    """One number in a fact sheet, or the documented absence of one.

    `computed` marks a value this service derived rather than copied from the
    source (F10). A derived figure always carries `computation_note`, so a
    reader can tell official data from arithmetic we performed.

    There is deliberately no `absence_reason` field. When `value is None` the
    only thing that can be said is that nothing was published — the sources
    mark no reason, as both the Phase 0 spike and the DEPP methodology
    confirm. The explanatory block for an absence is static content looked up
    by the serializer, identical for every absent figure.
    """

    value: float | None
    computed: bool = False
    computation_note: str | None = None

    @property
    def is_present(self) -> bool:
        return self.value is not None

    def __post_init__(self) -> None:
        if self.computed and not self.computation_note:
            raise ValueError("A computed figure must carry a computation note")
        if not self.computed and self.computation_note:
            raise ValueError("A raw source figure must not carry a computation note")


_EXPECTED_RATE_NOTE = (
    "Calculé par ce service : taux constaté − valeur ajoutée. "
    "La source publie les deux termes, pas leur différence."
)


def expected_rate(observed: float | None, value_added: float | None) -> Figure:
    """Derive the expected rate from the two figures the source publishes.

    The DEPP defines the value added as `taux constaté − taux attendu`, so the
    expected rate is recoverable exactly, with no modelling on our side. It is
    returned flagged as computed so it can never be mistaken for a published
    number.

    Both terms are required. If either is absent the expected rate is absent
    too — it is never partially reconstructed.
    """
    if observed is None or value_added is None:
        return Figure(value=None)
    return Figure(
        value=round(observed - value_added, 2),
        computed=True,
        computation_note=_EXPECTED_RATE_NOTE,
    )


@dataclass(frozen=True, slots=True)
class ResultRow:
    """One year of one indicator series, ready to serialize."""

    year: int
    indicator_type: IndicatorType
    candidates_present: int | None
    success_rate: Figure
    expected_success_rate: Figure
    value_added_success: Figure
    access_rate: Figure
    value_added_access: Figure
    mention_rate: Figure
    value_added_mention: Figure
    source: SourceReference


@dataclass(frozen=True, slots=True)
class FactSheet:
    establishment: Establishment
    results: tuple[ResultRow, ...]
    last_synchronised_at: datetime | None


def _to_result_row(
    result: IndicatorResult, sources: dict[str, SourceReference]
) -> ResultRow:
    dataset_id = INDICATOR_DATASET_IDS[result.indicator_type]
    source = sources.get(dataset_id)
    if source is None:
        raise MissingSourceReferenceError(dataset_id, result.uai, result.year)
    return ResultRow(
        year=result.year,
        indicator_type=result.indicator_type,
        candidates_present=result.candidates_present,
        success_rate=Figure(result.success_rate),
        expected_success_rate=expected_rate(
            result.success_rate, result.value_added_success
        ),
        value_added_success=Figure(result.value_added_success),
        access_rate=Figure(result.access_rate),
        value_added_access=Figure(result.value_added_access),
        mention_rate=Figure(result.mention_rate),
        value_added_mention=Figure(result.value_added_mention),
        source=source,
    )


class GetEstablishmentFactSheet:
    """Reads one establishment and every published result attached to it."""

    def __init__(
        self,
        establishments: EstablishmentReader,
        indicators: IndicatorReader,
        sources: SourceReferenceReader,
    ) -> None:
        self._establishments = establishments
        self._indicators = indicators
        self._sources = sources

    def run(self, uai: str) -> FactSheet | None:
        establishment = self._establishments.get_by_uai(uai)
        if establishment is None:
            return None

        sources = self._sources.all_by_dataset_id()
        results = tuple(
            _to_result_row(result, sources)
            for result in self._indicators.list_for_establishment(uai)
        )

        # The freshest synchronisation among the sources actually used. The
        # directory counts even when there are no results: the identity block
        # comes from it, and roughly two thirds of the directory (primary
        # schools) carries no indicator at all. Without it those fact sheets
        # would report "never synchronised" for data that was in fact synced,
        # which a reader could not tell apart from a broken pipeline.
        directory = sources.get(DATASET_DIRECTORY)
        timestamps = [row.source.last_synchronised_at for row in results]
        if directory is not None:
            timestamps.append(directory.last_synchronised_at)
        return FactSheet(
            establishment=establishment,
            results=results,
            last_synchronised_at=max(timestamps) if timestamps else None,
        )
