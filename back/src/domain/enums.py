"""Domain enumerations.

Values are the *source* labels, kept verbatim so that a value read from the
database can always be traced back to what the official dataset said. The
French wire labels required by docs/08_API_Contract.md are produced at the
serialization boundary, not here.
"""

from __future__ import annotations

from enum import StrEnum


class EstablishmentType(StrEnum):
    """Establishment types the product covers, plus a catch-all.

    Only COLLEGE, LYCEE and EREA can carry IVAC/IVAL indicators. The directory
    also contains ~48 000 primary schools and various administrative entities,
    which are ingested but are out of the product's indicator scope.
    """

    COLLEGE = "college"
    LYCEE = "lycee"
    EREA = "erea"
    SCHOOL = "ecole"
    OTHER = "autre"

    @property
    def can_have_indicators(self) -> bool:
        return self in _INDICATOR_BEARING_TYPES


_INDICATOR_BEARING_TYPES = frozenset(
    {EstablishmentType.COLLEGE, EstablishmentType.LYCEE, EstablishmentType.EREA}
)

# Source labels as they appear in `type_etablissement`.
_TYPE_BY_SOURCE_LABEL = {
    "collège": EstablishmentType.COLLEGE,
    "lycée": EstablishmentType.LYCEE,
    "erea": EstablishmentType.EREA,
    "ecole": EstablishmentType.SCHOOL,
    "école": EstablishmentType.SCHOOL,
}


def establishment_type_from_source(label: str | None) -> EstablishmentType:
    if label is None:
        return EstablishmentType.OTHER
    return _TYPE_BY_SOURCE_LABEL.get(label.strip().lower(), EstablishmentType.OTHER)


class Sector(StrEnum):
    """Public / private status. ~2.9% of directory rows leave this empty."""

    PUBLIC = "public"
    PRIVATE = "prive"


_SECTOR_BY_SOURCE_LABEL = {
    "public": Sector.PUBLIC,
    "privé": Sector.PRIVATE,
    "prive": Sector.PRIVATE,
}


def sector_from_source(label: str | None) -> Sector | None:
    """Return None rather than guessing — an unknown sector stays unknown."""
    if label is None:
        return None
    return _SECTOR_BY_SOURCE_LABEL.get(label.strip().lower())


class IndicatorType(StrEnum):
    """Which published indicator series a result row belongs to.

    IVAC covers collèges (2022-2025 only), IVAL the lycées (2012-2025). The
    difference in historical depth is a property of the sources, not a bug.
    """

    IVAC = "IVAC"
    IVAL_GT = "IVAL_GT"
    IVAL_PRO = "IVAL_PRO"
