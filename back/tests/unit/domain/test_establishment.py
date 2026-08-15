"""Unit tests for the Establishment/Site domain entities.

Covers the invariants documented in `src/domain/establishment.py`: an
establishment always has at least one site, and the canonical site is
picked deterministically (lowest `sequence`), never by source order.
"""

from __future__ import annotations

import pytest

from src.domain.enums import EstablishmentType, Sector
from src.domain.establishment import Establishment
from tests.unit.factories import make_establishment, make_site


def test_establishment_with_zero_sites_raises() -> None:
    with pytest.raises(ValueError, match="at least one site"):
        Establishment(
            uai="0750001A",
            name="Ghost school",
            type=EstablishmentType.COLLEGE,
            sector=Sector.PUBLIC,
            department_code="75",
            is_open=True,
            sites=(),
        )


def test_canonical_site_is_the_lowest_sequence_regardless_of_tuple_order() -> None:
    site_0 = make_site(sequence=0, name="Main site")
    site_1 = make_site(sequence=1, name="Annexe")
    establishment = make_establishment(sites=(site_1, site_0))

    assert establishment.canonical_site is site_0


def test_canonical_site_never_depends_on_source_order() -> None:
    site_a = make_site(sequence=0, name="A")
    site_b = make_site(sequence=1, name="B")
    site_c = make_site(sequence=2, name="C")

    in_source_order = make_establishment(sites=(site_a, site_b, site_c))
    reversed_order = make_establishment(sites=(site_c, site_b, site_a))

    assert in_source_order.canonical_site == reversed_order.canonical_site == site_a


def test_no_site_is_discarded_when_picking_the_canonical_one() -> None:
    sites = (make_site(sequence=0, name="A"), make_site(sequence=1, name="B"))
    establishment = make_establishment(sites=sites)

    establishment.canonical_site  # noqa: B018 - trigger the property

    assert len(establishment.sites) == 2


def test_is_multi_site_true_with_more_than_one_site() -> None:
    establishment = make_establishment(sites=(make_site(0), make_site(1)))
    assert establishment.is_multi_site is True


def test_is_multi_site_false_with_a_single_site() -> None:
    establishment = make_establishment(sites=(make_site(0),))
    assert establishment.is_multi_site is False


@pytest.mark.parametrize(
    ("establishment_type", "expected"),
    [
        (EstablishmentType.COLLEGE, True),
        (EstablishmentType.LYCEE, True),
        (EstablishmentType.EREA, True),
        (EstablishmentType.SCHOOL, False),
        (EstablishmentType.OTHER, False),
    ],
)
def test_can_have_indicators_matches_the_indicator_bearing_types(
    establishment_type: EstablishmentType, expected: bool
) -> None:
    establishment = make_establishment(type=establishment_type)
    assert establishment.can_have_indicators is expected


def test_site_has_coordinates_requires_both_latitude_and_longitude() -> None:
    assert make_site(latitude=48.8, longitude=2.3).has_coordinates is True
    assert make_site(latitude=None, longitude=2.3).has_coordinates is False
    assert make_site(latitude=48.8, longitude=None).has_coordinates is False
    assert make_site(latitude=None, longitude=None).has_coordinates is False
