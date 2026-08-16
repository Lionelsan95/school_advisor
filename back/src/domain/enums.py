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


class Filiere(StrEnum):
    """A teaching pathway an establishment offers.

    Read from the directory's `voie_generale` / `voie_technologique` /
    `voie_professionnelle` flags. This describes what the establishment
    *offers*, not how it performs — it is a filter criterion, never a result.
    """

    GENERALE = "generale"
    TECHNOLOGIQUE = "technologique"
    PROFESSIONNELLE = "professionnelle"


class Section(StrEnum):
    """A specific section or provision hosted by the establishment.

    Also descriptive: the presence of a section says what is on offer, and
    carries no implication that one offering is preferable to another.
    """

    EUROPEENNE = "europeenne"
    INTERNATIONALE = "internationale"
    SPORT = "sport"
    ARTS = "arts"
    CINEMA = "cinema"
    THEATRE = "theatre"
    ULIS = "ulis"
    SEGPA = "segpa"


# Source flag field -> domain value. The directory publishes these as "0"/"1"
# strings, except `ulis` which is a plain integer — see `flag_is_set`.
FILIERE_BY_SOURCE_FIELD: dict[str, Filiere] = {
    "voie_generale": Filiere.GENERALE,
    "voie_technologique": Filiere.TECHNOLOGIQUE,
    "voie_professionnelle": Filiere.PROFESSIONNELLE,
}

SECTION_BY_SOURCE_FIELD: dict[str, Section] = {
    "section_europeenne": Section.EUROPEENNE,
    "section_internationale": Section.INTERNATIONALE,
    "section_sport": Section.SPORT,
    "section_arts": Section.ARTS,
    "section_cinema": Section.CINEMA,
    "section_theatre": Section.THEATRE,
    "ulis": Section.ULIS,
    "segpa": Section.SEGPA,
}


def flag_is_set(value: object) -> bool:
    """Whether a directory boolean-ish flag is set.

    The directory is not type-consistent here: `voie_*`, `section_*` and
    `segpa` arrive as the strings "0"/"1", while `ulis` arrives as the integer
    0/1. Both spellings are accepted; anything else (null, "", an unexpected
    label) reads as *not set* rather than raising, because an establishment
    that does not declare a section is the normal case, not a source defect.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    return str(value).strip() == "1"


class IndicatorType(StrEnum):
    """Which published indicator series a result row belongs to.

    IVAC covers collèges (2022-2025 only), IVAL the lycées (2012-2025). The
    difference in historical depth is a property of the sources, not a bug.
    """

    IVAC = "IVAC"
    IVAL_GT = "IVAL_GT"
    IVAL_PRO = "IVAL_PRO"
