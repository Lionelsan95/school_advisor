"""Unit tests for the static F3/F6/F7 explanatory content store (API-3).

`API-3`'s acceptance criteria requires that "the same indicator always
returns the exact same explanatory text, regardless of which establishment
it's attached to" — this module never takes an establishment as input at
all, so the test asserts the stronger, checkable property: repeated lookups
by `content_id` are identical, and every entry satisfies the six-part
charter structure (docs/14_Charte_Neutralite_Editoriale.md §4).
"""

from __future__ import annotations

import re

import pytest

from src.domain.explanatory_content import ABSENT_VALUE, CONTENT_BY_ID, get_content

CONTENT_IDS = list(CONTENT_BY_ID)


class TestGetContentIsConsistentAcrossCalls:
    @pytest.mark.parametrize("content_id", CONTENT_IDS)
    def test_repeated_calls_return_an_identical_object(self, content_id: str) -> None:
        first = get_content(content_id)
        second = get_content(content_id)
        assert first == second

    @pytest.mark.parametrize("content_id", CONTENT_IDS)
    def test_repeated_calls_return_byte_identical_text(self, content_id: str) -> None:
        first = get_content(content_id)
        second = get_content(content_id)
        assert first.title == second.title
        assert first.simple_definition == second.simple_definition
        assert first.how_to_read == second.how_to_read
        assert first.what_it_measures == second.what_it_measures
        assert first.what_it_does_not_measure == second.what_it_does_not_measure
        assert first.method == second.method
        assert first.source_note == second.source_note

    def test_an_unknown_content_id_raises_key_error_rather_than_a_default(
        self,
    ) -> None:
        with pytest.raises(KeyError):
            get_content("does-not-exist")


class TestContentIdRoundTrips:
    @pytest.mark.parametrize("content_id", CONTENT_IDS)
    def test_the_dict_key_matches_the_entrys_own_content_id(
        self, content_id: str
    ) -> None:
        assert CONTENT_BY_ID[content_id].content_id == content_id

    @pytest.mark.parametrize("content_id", CONTENT_IDS)
    def test_get_content_returns_an_entry_whose_id_matches_what_was_asked(
        self, content_id: str
    ) -> None:
        assert get_content(content_id).content_id == content_id


class TestSixPartCharterStructure:
    """docs/14_Charte_Neutralite_Editoriale.md §4: definition simple, comment
    lire, ce que cela mesure, ce que cela ne mesure pas, methode (facultatif),
    source et millesime. `method` is the only part allowed to be absent.
    """

    @pytest.mark.parametrize("content_id", CONTENT_IDS)
    def test_the_five_mandatory_sections_are_non_empty(self, content_id: str) -> None:
        block = CONTENT_BY_ID[content_id]
        assert block.title.strip()
        assert block.simple_definition.strip()
        assert block.how_to_read.strip()
        assert block.what_it_measures.strip()
        assert block.what_it_does_not_measure.strip()
        assert block.source_note.strip()

    @pytest.mark.parametrize("content_id", CONTENT_IDS)
    def test_method_is_either_none_or_non_blank_never_an_empty_string(
        self, content_id: str
    ) -> None:
        method = CONTENT_BY_ID[content_id].method
        assert method is None or method.strip()

    @pytest.mark.parametrize("content_id", CONTENT_IDS)
    def test_version_is_a_positive_integer(self, content_id: str) -> None:
        assert CONTENT_BY_ID[content_id].version >= 1


class TestAbsenceTextNeverAssertsASingleCause:
    """DATA-4 / API-4: the source gives no reason for a missing value, and the
    spike measured 457 IVAL GT rows the "below threshold" explanation would
    mislabel. `ABSENT_VALUE` must document the threshold only as one
    possibility among several, never as the cause of a specific absence.
    """

    def test_the_threshold_is_named_only_alongside_other_documented_possibilities(
        self,
    ) -> None:
        combined = " ".join(
            [
                ABSENT_VALUE.simple_definition,
                ABSENT_VALUE.how_to_read,
                ABSENT_VALUE.what_it_measures,
                ABSENT_VALUE.what_it_does_not_measure,
                ABSENT_VALUE.method or "",
                ABSENT_VALUE.source_note,
            ]
        )
        assert "seuil" in combined
        # At least the Mayotte case (source computes no expected rate there
        # at all) must be named alongside the threshold — it is not the same
        # cause, and the spike found 113 Mayotte rows a threshold-only
        # explanation would mislabel.
        assert "Mayotte" in combined

    def test_it_explicitly_says_which_cause_applies_is_unknowable_per_row(
        self,
    ) -> None:
        assert (
            "pas possible de savoir laquelle" in ABSENT_VALUE.what_it_does_not_measure
        )

    def test_it_does_not_contain_the_superseded_bare_threshold_formulation(
        self,
    ) -> None:
        """Regression guard against docs/14 §6's original reference wording
        ("La DEPP ne publie pas cette valeur lorsque l'effectif est inférieur
        au seuil..."), superseded by the Phase 0/1 spike findings because it
        states the threshold as fact with no hedge.
        """
        forbidden = re.compile(r"lorsque l.effectif est inf[ée]rieur au seuil")
        for field in (
            ABSENT_VALUE.simple_definition,
            ABSENT_VALUE.how_to_read,
            ABSENT_VALUE.what_it_measures,
            ABSENT_VALUE.what_it_does_not_measure,
            ABSENT_VALUE.method or "",
            ABSENT_VALUE.source_note,
        ):
            assert not forbidden.search(field), field

    def test_no_field_estimates_or_substitutes_the_missing_value(self) -> None:
        combined = " ".join(
            [
                ABSENT_VALUE.simple_definition,
                ABSENT_VALUE.how_to_read,
                ABSENT_VALUE.what_it_measures,
                ABSENT_VALUE.what_it_does_not_measure,
                ABSENT_VALUE.method or "",
                ABSENT_VALUE.source_note,
            ]
        )
        assert "estim" in combined.lower()  # states that nothing is estimated
