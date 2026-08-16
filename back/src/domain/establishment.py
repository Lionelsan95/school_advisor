"""The Establishment entity and its sites.

Modelling note (decided 2026-08-15, see docs/04_Journal_Decisions.md):
the UAI identifies one *administrative* establishment, which may occupy
several physical sites. The Phase 0 spike found 74 such cases (68 with two
sites, 6 with three). The directory publishes one row per site, so a naive
"one row per UAI" import would silently drop a site — which the product must
never do.

Hence: one `Establishment` per UAI, holding an ordered tuple of `Site`s.
Indicators join on the UAI, because the published IVAC/IVAL data does not
distinguish sites either.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import EstablishmentType, Filiere, Section, Sector


@dataclass(frozen=True, slots=True)
class Site:
    """One physical location of an establishment.

    `sequence` is a stable ordinal assigned at ingestion time so that the same
    source data always yields the same ordering, and so the canonical site can
    be picked deterministically rather than by whatever order the API returned.

    Caveat established by the spike: for multi-site establishments the annexe
    sites carry the *parent's* coordinates in the source. Two sites 30 km apart
    can therefore share a latitude/longitude. Proximity search must not treat
    annexe coordinates as precise.
    """

    sequence: int
    name: str
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    city_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None


@dataclass(frozen=True, slots=True)
class Establishment:
    """An establishment as identified by its UAI.

    Attributes are those that hold for the establishment as a whole; anything
    that varies between physical locations lives on `Site`.
    """

    uai: str
    name: str
    type: EstablishmentType
    sector: Sector | None
    department_code: str | None
    is_open: bool
    sites: tuple[Site, ...]
    # What the establishment offers. Descriptive only — these are search
    # criteria and fact-sheet content, never inputs to any ordering.
    filieres: tuple[Filiere, ...] = ()
    sections: tuple[Section, ...] = ()
    source_updated_at: str | None = None

    def __post_init__(self) -> None:
        if not self.sites:
            raise ValueError(f"Establishment {self.uai} must have at least one site")

    @property
    def is_multi_site(self) -> bool:
        return len(self.sites) > 1

    @property
    def canonical_site(self) -> Site:
        """The site used to represent the establishment in a single line.

        Deterministic by construction: the lowest sequence. No site is ever
        discarded — the others remain available on `sites`.
        """
        return min(self.sites, key=lambda site: site.sequence)

    @property
    def can_have_indicators(self) -> bool:
        return self.type.can_have_indicators
