"""Unit tests for `breaks_spanned_by` (API-7 / F5).

This is the heart of the ticket: the charter (§10) requires a methodology
break to be visible whenever a chart would otherwise draw an unbroken line
through the 2021 baccalauréat reform, but only when an establishment's own
data actually straddles it — see the module docstring in
`src/domain/methodology_break.py` and docs/05_Resultats_Spike_Technique.md.
"""

from __future__ import annotations

from src.domain.enums import IndicatorType
from src.domain.methodology_break import IVAL_BACCALAUREAT_REFORM, breaks_spanned_by


class TestIvalGtSpanningTheReform:
    def test_years_before_and_after_2021_trigger_the_break(self) -> None:
        breaks = breaks_spanned_by({IndicatorType.IVAL_GT: {2019, 2020, 2021, 2022}})
        assert breaks == (IVAL_BACCALAUREAT_REFORM,)


class TestIvalGtEntirelyBeforeTheReform:
    def test_no_break_when_nothing_comes_after(self) -> None:
        breaks = breaks_spanned_by({IndicatorType.IVAL_GT: {2018, 2019, 2020}})
        assert breaks == ()


class TestIvalGtEntirelyFromTheReformOnward:
    def test_no_break_when_nothing_comes_before(self) -> None:
        breaks = breaks_spanned_by({IndicatorType.IVAL_GT: {2021, 2022, 2023}})
        assert breaks == ()


class TestExactBoundary:
    """`breaks_spanned_by` pins `any(year < 2021) and any(year >= 2021)` —
    2021 itself counts as "after", not "before".
    """

    def test_2020_and_2021_together_trigger_the_break(self) -> None:
        breaks = breaks_spanned_by({IndicatorType.IVAL_GT: {2020, 2021}})
        assert breaks == (IVAL_BACCALAUREAT_REFORM,)

    def test_2021_and_2022_together_do_not_trigger_the_break(self) -> None:
        breaks = breaks_spanned_by({IndicatorType.IVAL_GT: {2021, 2022}})
        assert breaks == ()


class TestIvac:
    """IVAC begins in 2022, after the reform, and carries no registered
    break at all in `BREAKS_BY_INDICATOR_TYPE` — it must never be annotated,
    whatever span of years is passed in.
    """

    def test_no_break_for_the_real_ivac_range(self) -> None:
        breaks = breaks_spanned_by({IndicatorType.IVAC: {2022, 2023, 2024, 2025}})
        assert breaks == ()

    def test_no_break_even_for_a_span_that_would_trigger_it_for_ival(self) -> None:
        # Same shape of span as the IVAL_GT case that does trigger a break —
        # proves the absence is because of the indicator type, not the years.
        breaks = breaks_spanned_by({IndicatorType.IVAC: {2019, 2020, 2021, 2022}})
        assert breaks == ()


class TestMixedIndicatorTypes:
    def test_an_establishment_with_ivac_and_ival_gt_gets_the_break_once(self) -> None:
        breaks = breaks_spanned_by(
            {
                IndicatorType.IVAC: {2022, 2023, 2024, 2025},
                IndicatorType.IVAL_GT: {2019, 2020, 2021, 2022},
            }
        )
        assert breaks == (IVAL_BACCALAUREAT_REFORM,)

    def test_ival_gt_and_ival_pro_both_spanning_still_return_one_break(self) -> None:
        # Both series carry the same registered break; it must be
        # de-duplicated rather than appearing twice.
        breaks = breaks_spanned_by(
            {
                IndicatorType.IVAL_GT: {2020, 2021},
                IndicatorType.IVAL_PRO: {2020, 2021},
            }
        )
        assert breaks == (IVAL_BACCALAUREAT_REFORM,)


class TestEmptyInput:
    def test_no_indicator_types_yields_no_breaks(self) -> None:
        assert breaks_spanned_by({}) == ()

    def test_an_indicator_type_with_no_years_yields_no_breaks(self) -> None:
        assert breaks_spanned_by({IndicatorType.IVAL_GT: set()}) == ()
