"""Unit tests for the IndicatorResult domain entity.

The load-bearing rule here (see the module docstring in
`src/domain/indicator_result.py` and docs/04_Journal_Decisions.md) is that a
missing value carries no asserted reason: nothing may derive a
"below publication threshold" flag from a candidate count.
"""

from __future__ import annotations

import pytest

from src.domain.enums import IndicatorType
from tests.unit.factories import make_indicator_result


@pytest.mark.parametrize("year", [1999, 2101, 0, -1])
def test_implausible_year_is_rejected(year: int) -> None:
    with pytest.raises(ValueError, match="Implausible"):
        make_indicator_result(year=year)


@pytest.mark.parametrize("year", [2000, 2100])
def test_boundary_years_are_accepted(year: int) -> None:
    assert make_indicator_result(year=year).year == year


def test_has_value_added_false_when_value_is_null() -> None:
    result = make_indicator_result(value_added_success=None)
    assert result.has_value_added is False


def test_has_value_added_true_when_value_is_published() -> None:
    result = make_indicator_result(value_added_success=-1.4)
    assert result.has_value_added is True


def test_is_empty_true_when_no_figure_is_published_at_all() -> None:
    result = make_indicator_result(
        candidates_present=100,  # a candidate count alone is not a "figure"
        success_rate=None,
        value_added_success=None,
        access_rate=None,
        mention_rate=None,
    )
    assert result.is_empty is True


def test_is_empty_false_when_a_single_figure_is_published() -> None:
    result = make_indicator_result(
        success_rate=None,
        value_added_success=None,
        access_rate=None,
        mention_rate=42.0,
    )
    assert result.is_empty is False


def test_key_is_the_natural_append_only_key() -> None:
    result = make_indicator_result(
        uai="0750001A", year=2024, indicator_type=IndicatorType.IVAL_GT
    )
    assert result.key == ("0750001A", 2024, IndicatorType.IVAL_GT)


def test_no_threshold_reason_is_ever_attached_to_an_absent_value() -> None:
    """DATA-4 / spike finding: the source never says *why* a value is absent
    (docs/05_Resultats_Spike_Technique.md, section 3.2). This entity must not
    grow a `below_threshold` / `sous_seuil_diffusion` flag.
    """
    result = make_indicator_result(candidates_present=415, value_added_success=None)

    for forbidden_attribute in (
        "below_threshold",
        "below_publication_threshold",
        "sous_seuil_diffusion",
        "under_threshold",
    ):
        assert not hasattr(result, forbidden_attribute)
