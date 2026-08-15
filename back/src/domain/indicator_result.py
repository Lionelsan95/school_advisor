"""A published indicator result for one establishment, one year, one series.

Two domain rules are load-bearing here, both established by the Phase 0 spike
and recorded in docs/04_Journal_Decisions.md:

1. **Append-only.** `(uai, year, indicator_type)` was verified strictly unique
   across all 87 612 published rows. A new ingestion run adds years; it never
   rewrites a past one.

2. **A missing value carries no asserted reason.** None of the three source
   datasets publishes *why* a value is absent — the field is simply null. The
   documented DEPP non-diffusion threshold (<20 candidates GT, <10 PRO) does
   NOT predict the nulls: the spike measured 457 IVAL GT rows above the
   threshold with no value (113 of them in Mayotte, where value-added is not
   computed at all) and 75 below-threshold rows that do carry one.

   Therefore this entity has no `below_publication_threshold` flag, and nothing
   in the codebase may derive one from a candidate count. Absence is absence.
   Saying more than the source says would be a factual claim the data does not
   support — and the editorial charter forbids attributing to an absence a
   cause the source does not give.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import IndicatorType, Sector


@dataclass(frozen=True, slots=True)
class IndicatorResult:
    """One row of published results.

    Every rate is expressed as the source publishes it (percentage points).
    Value-added figures are differences in percentage points between the
    observed result and the statistically expected one; the sign is part of
    the data and is never translated into a judgement.
    """

    uai: str
    year: int
    indicator_type: IndicatorType
    sector: Sector | None = None

    candidates_present: int | None = None
    success_rate: float | None = None
    value_added_success: float | None = None
    access_rate: float | None = None
    value_added_access: float | None = None
    mention_rate: float | None = None
    value_added_mention: float | None = None

    def __post_init__(self) -> None:
        # A result must be attributable to a year; anything else is a source
        # defect worth surfacing rather than storing.
        if self.year < 2000 or self.year > 2100:
            raise ValueError(f"Implausible indicator year for {self.uai}: {self.year}")

    @property
    def has_value_added(self) -> bool:
        """Whether a value-added figure was published for this row.

        Deliberately *not* named `below_threshold`: the source does not tell us
        why a figure is absent, and this property must not be read as implying
        a reason.
        """
        return self.value_added_success is not None

    @property
    def is_empty(self) -> bool:
        """True when the row exists but publishes no usable figure at all."""
        return all(
            value is None
            for value in (
                self.success_rate,
                self.value_added_success,
                self.access_rate,
                self.mention_rate,
            )
        )

    @property
    def key(self) -> tuple[str, int, IndicatorType]:
        """The append-only natural key."""
        return (self.uai, self.year, self.indicator_type)
