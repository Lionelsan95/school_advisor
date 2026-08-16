"""Methodology breaks in a published indicator series (feature F5).

**This module is editorial content**, under the same human-review gate as
`explanatory_content.py`: the note below is shown to readers verbatim.

Why this exists at all is the important part. The Phase 0 spike established
that the 2021 baccalauréat reform broke the *per-stream* IVAL indicators
(L/ES/S replaced by a single general stream) while the total-level indicators
this product stores stayed continuous. Verified again on the loaded data: 2019
through 2023 each carry ~2 300 IVAL GT rows with a value added, with no gap at
2021.

That continuity is exactly the problem. A chart of those points draws an
unbroken line straight through a change in how the underlying examination
worked, and a reader will naturally take the points on either side as
comparable. Nothing in the data hints otherwise, so the annotation has to carry
the warning by itself — which is why the charter (§10) requires ruptures to be
visible rather than smoothed over.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .enums import IndicatorType


@dataclass(frozen=True, slots=True)
class MethodologyBreak:
    """A year from which a series is no longer strictly comparable."""

    year: int
    content_id: str
    version: int
    title: str
    note: str


IVAL_BACCALAUREAT_REFORM: Final = MethodologyBreak(
    year=2021,
    content_id="rupture_bac_2021",
    version=1,
    title="Changement de méthode en 2021",
    note=(
        "La réforme du baccalauréat s'applique à partir de la session 2021 : "
        "les séries L, ES et S sont remplacées par une voie générale unique. "
        "Les valeurs affichées avant et après cette date ne reposent donc pas "
        "sur exactement le même examen. Elles restent publiées telles quelles "
        "par la source ; aucune n'a été recalculée pour les rendre "
        "comparables."
    ),
)


# Which series each break applies to. IVAC begins in 2022, after the reform, so
# no IVAC series spans it and none is annotated.
BREAKS_BY_INDICATOR_TYPE: Final[dict[IndicatorType, tuple[MethodologyBreak, ...]]] = {
    IndicatorType.IVAL_GT: (IVAL_BACCALAUREAT_REFORM,),
    IndicatorType.IVAL_PRO: (IVAL_BACCALAUREAT_REFORM,),
    IndicatorType.IVAC: (),
}


def breaks_spanned_by(
    years_by_type: dict[IndicatorType, set[int]],
) -> tuple[MethodologyBreak, ...]:
    """The breaks an establishment's own history actually straddles.

    A break is only worth showing to someone whose data spans it. An
    establishment with results only from 2022 onward has nothing before the
    reform to be misled into comparing against, and annotating its chart would
    raise a question its own figures do not pose.
    """
    spanned: list[MethodologyBreak] = []
    for indicator_type, years in years_by_type.items():
        for methodology_break in BREAKS_BY_INDICATOR_TYPE.get(indicator_type, ()):
            before = any(year < methodology_break.year for year in years)
            after = any(year >= methodology_break.year for year in years)
            if before and after and methodology_break not in spanned:
                spanned.append(methodology_break)
    return tuple(sorted(spanned, key=lambda item: item.year))
