"""Neutrality guardrail tests.

Not a generic code-quality lint: this exists because CLAUDE.md's non-
negotiable product principle ("the tool explains, it never judges") and
docs/09_Definition_of_Done_Quality_Gates.md §1 name a specific forbidden-word
list. A single evaluative adjective slipping into the static F3/F6/F7 content
or into the API's own rejection message would violate that principle even if
every other test passes — so it gets a dedicated, automated check rather than
relying on a human re-reading the strings on every change.

Scope: every user-facing string this backend can currently emit that is not
sourced verbatim from the official datasets — the editorial content in
`domain/explanatory_content.py`, the router's static rejection and
data-integrity messages in `interfaces/api/establishments.py`, and the
methodology-break note in `domain/methodology_break.py` (API-7 / F5), which
is new user-facing editorial content under the same human-review gate.
"""

from __future__ import annotations

import re

import pytest

from src.application.assistant_search import (
    AssistantSearchUnavailable,
    UnavailableReason,
)
from src.domain import assistant_content, glossary_content
from src.domain import explanatory_content as content
from src.domain.methodology_break import IVAL_BACCALAUREAT_REFORM
from src.interfaces.api.assistant import _MISSING_ASSISTANT_SOURCE_MESSAGE
from src.interfaces.api.communes import _MISSING_COMMUNE_SOURCE_MESSAGE
from src.interfaces.api.establishments import (
    _MISSING_PROVENANCE_MESSAGE,
    _MISSING_SEARCH_SOURCE_MESSAGE,
    _NO_RANKING_MESSAGE,
)
from src.interfaces.api.schemas import AssistantSearchUnavailableOut

# docs/09_Definition_of_Done_Quality_Gates.md §1 ("best", "good", "excellent",
# "top", "recommended", "better than", "bon", "meilleur", "recommandé",
# "excellent") plus the French forms CLAUDE.md's workflow section calls out
# explicitly, plus the charter's own "formulation interdite" vocabulary
# (docs/14_Charte_Neutralite_Editoriale.md §3: surperforme / sous-performe /
# classement / palmarès).
FORBIDDEN_WORDS = (
    "best",
    "good",
    "excellent",
    "top",
    "recommended",
    "better",
    "bon",
    "bonne",
    "meilleur",
    "meilleure",
    "recommandé",
    "recommandée",
    "recommandation",
    "classement",
    "palmarès",
    "performant",
    "performante",
    "surperforme",
    "sous-performe",
)

# Word-boundary + case-insensitive: a bare `in` check would flag "classe"
# inside "classement" backwards, or "top" inside "topographie" — neither of
# which is the evaluative word this list means to catch.
_FORBIDDEN_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(word) for word in FORBIDDEN_WORDS) + r")\b",
    re.IGNORECASE,
)

_CONTENT_TEXT_FIELDS = (
    "title",
    "simple_definition",
    "how_to_read",
    "what_it_measures",
    "what_it_does_not_measure",
    "source_note",
)


def _all_content_strings() -> list[tuple[str, str, str]]:
    """(content_id, field_name, text) for every editorial field in the store."""
    entries: list[tuple[str, str, str]] = []
    for block in content.CONTENT_BY_ID.values():
        for field in _CONTENT_TEXT_FIELDS:
            entries.append((block.content_id, field, getattr(block, field)))
        if block.method is not None:
            entries.append((block.content_id, "method", block.method))
    return entries


_CONTENT_STRINGS = _all_content_strings()
_CONTENT_STRING_IDS = [f"{cid}.{field}" for cid, field, _ in _CONTENT_STRINGS]

_ASSISTANT_CONTENT_STRINGS = (
    assistant_content.SUBJECTIVE_REQUEST_REFRAME,
    assistant_content.LOCATION_REQUIRED,
    assistant_content.LOCATION_UNKNOWN,
    assistant_content.LOCATION_AMBIGUOUS,
    assistant_content.LOCATION_HAS_NO_CENTRE,
    assistant_content.INTERPRETER_UNAVAILABLE,
)


class TestForbiddenWordPatternItself:
    """Guards the guard: a regex typo here would silently disable every check
    below, so its word-boundary behaviour gets its own tests.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "C'est le meilleur établissement",
            "This is the BEST school",
            "Un établissement recommandé",
            "L'établissement surperforme les attentes",
            "Voici notre classement",
        ],
    )
    def test_matches_an_evaluative_sentence(self, text: str) -> None:
        assert _FORBIDDEN_PATTERN.search(text) is not None

    @pytest.mark.parametrize(
        "text",
        [
            # "top" must not match inside an unrelated word.
            "La topographie du site n'est pas un critère.",
            # "bon" must not match inside an unrelated word.
            "Cet établissement est abonné aux données publiques.",
            # "classement" is absent; "classe" (a grade level) is not
            # forbidden and must not falsely trigger it.
            "Ce service ne classe pas les établissements.",
            # Neutral, factual sentences from the actual content should pass.
            "Résultat observé supérieur de 4 points au résultat attendu.",
        ],
    )
    def test_does_not_match_a_neutral_sentence(self, text: str) -> None:
        assert _FORBIDDEN_PATTERN.search(text) is None


class TestNoForbiddenWordInExplanatoryContent:
    @pytest.mark.parametrize(
        ("content_id", "field", "text"), _CONTENT_STRINGS, ids=_CONTENT_STRING_IDS
    )
    def test_field_carries_no_evaluative_wording(
        self, content_id: str, field: str, text: str
    ) -> None:
        match = _FORBIDDEN_PATTERN.search(text)
        assert match is None, (
            f"{content_id}.{field} contains evaluative wording "
            f"{match.group() if match else None!r} in: {text!r}"
        )


class TestNoForbiddenWordInScopeDisclaimer:
    def test_scope_disclaimer_carries_no_evaluative_wording(self) -> None:
        match = _FORBIDDEN_PATTERN.search(content.SCOPE_DISCLAIMER)
        assert match is None, (
            f"disclaimer contains {match.group() if match else None!r}: "
            f"{content.SCOPE_DISCLAIMER!r}"
        )


class TestNoForbiddenWordInApprovedAssistantContent:
    @pytest.mark.parametrize("text", _ASSISTANT_CONTENT_STRINGS)
    def test_assistant_string_carries_no_evaluative_wording(self, text: str) -> None:
        match = _FORBIDDEN_PATTERN.search(text)
        assert match is None, (
            "assistant content contains evaluative wording "
            f"{match.group() if match else None!r} in: {text!r}"
        )


class TestNoForbiddenWordInSortRejectionMessage:
    """The 400 a client gets back for asking to sort by a result is itself
    user-facing text — API-2's acceptance criteria requires it be "a clear
    message", which must not itself smuggle in a quality judgement.
    """

    def test_rejection_message_carries_no_evaluative_wording(self) -> None:
        rendered = _NO_RANKING_MESSAGE.format(name="sort_by")
        match = _FORBIDDEN_PATTERN.search(rendered)
        assert match is None, (
            f"rejection message contains {match.group() if match else None!r}: "
            f"{rendered!r}"
        )


class TestNoForbiddenWordInDataIntegrityMessage:
    def test_missing_provenance_message_carries_no_evaluative_wording(self) -> None:
        match = _FORBIDDEN_PATTERN.search(_MISSING_PROVENANCE_MESSAGE)
        assert match is None, (
            "missing provenance message contains "
            f"{match.group() if match else None!r}: {_MISSING_PROVENANCE_MESSAGE!r}"
        )

    @pytest.mark.parametrize(
        "message",
        [
            _MISSING_SEARCH_SOURCE_MESSAGE,
            _MISSING_COMMUNE_SOURCE_MESSAGE,
            _MISSING_ASSISTANT_SOURCE_MESSAGE,
        ],
        ids=["establishment-search", "commune-search", "assistant-search"],
    )
    def test_missing_search_source_messages_carry_no_evaluative_wording(
        self, message: str
    ) -> None:
        match = _FORBIDDEN_PATTERN.search(message)
        assert match is None, (
            "missing search source message contains "
            f"{match.group() if match else None!r}: {message!r}"
        )


class TestSubjectiveRefusalMessageIsTheApprovedConstantVerbatim:
    """docs/14_Charte_Neutralite_Editoriale.md §12 prescribes one exact
    sentence for a recommendation request. The refusal path must hand back
    that module constant untouched — never rebuilt via f-string,
    concatenation, or `.format()`, any of which could silently drift from the
    human-approved wording while still passing a plain string-equality check.
    `is` catches that drift; `==` would not.
    """

    def test_refusal_message_is_identity_equal_to_the_approved_constant(self) -> None:
        outcome = AssistantSearchUnavailable(
            reason=UnavailableReason.INTERPRETATION_REJECTED,
            subjective_request_reframed=True,
        )

        body = AssistantSearchUnavailableOut.of(outcome)

        assert body.message is assistant_content.SUBJECTIVE_REQUEST_REFRAME


class TestNoForbiddenWordInMethodologyBreakContent:
    """The 2021 baccalauréat-reform break (API-7 / F5) is editorial content
    shown verbatim on every history chart that spans it — it gets the same
    forbidden-word scan as the F3/F6/F7 static blocks above.
    """

    @pytest.mark.parametrize("field", ["title", "note"])
    def test_field_carries_no_evaluative_wording(self, field: str) -> None:
        text = getattr(IVAL_BACCALAUREAT_REFORM, field)
        match = _FORBIDDEN_PATTERN.search(text)
        assert match is None, (
            f"methodology_break.{field} contains evaluative wording "
            f"{match.group() if match else None!r} in: {text!r}"
        )


class TestMethodologyBreakNoteStatesNonComparabilityNotADirection:
    """docs/14_Charte_Neutralite_Editoriale.md §10 requires ruptures to be
    visible, but never characterised as an improvement or a decline — the
    reform changed what is being measured, not whether results got better or
    worse. The note must say the values are not comparable, never state a
    direction of change.
    """

    _DIRECTIONAL_WORDS = (
        "amélioration",
        "amélioré",
        "dégradation",
        "dégradé",
        "progrès",
        "progression",
        "recul",
        "hausse",
        "baisse",
        "augmente",
        "diminue",
    )

    def test_the_note_names_no_direction_of_change(self) -> None:
        note = IVAL_BACCALAUREAT_REFORM.note.lower()
        for word in self._DIRECTIONAL_WORDS:
            assert word not in note, (
                f"methodology break note asserts a direction ({word!r}): {note!r}"
            )

    def test_the_note_states_the_values_are_not_comparable(self) -> None:
        note = IVAL_BACCALAUREAT_REFORM.note.lower()
        assert "comparables" in note


class TestYearNotPublishedContentIsScannedAndNeverImpliesADeficiency:
    """API-8 / F4 — `YEAR_NOT_PUBLISHED` (content_id "annee_non_publiee") is
    the static block a comparison cell points at when one establishment has
    no row at all for a year the other one published. It is registered in
    `content.CONTENT_BY_ID`, so `_all_content_strings()` already picks it up
    and the parametrized `TestNoForbiddenWordInExplanatoryContent` above
    already scans it for evaluative wording — this class pins that inclusion
    explicitly, so a future refactor of `_all_content_strings()` cannot drop
    it silently, and adds the two checks the forbidden-word scan alone cannot
    make: that the wording states an absence *for this establishment*
    (never for the one placed next to it), and that it explicitly disclaims
    comparison rather than reading as a deficiency.
    """

    def test_the_block_is_registered_and_therefore_already_scanned_above(self) -> None:
        assert content.YEAR_NOT_PUBLISHED.content_id in content.CONTENT_BY_ID
        scanned_ids = {content_id for content_id, _, _ in _CONTENT_STRINGS}
        assert content.YEAR_NOT_PUBLISHED.content_id in scanned_ids

    def test_wording_explicitly_disclaims_comparison(self) -> None:
        how_to_read = content.YEAR_NOT_PUBLISHED.how_to_read.lower()
        assert "ne se compare pas" in how_to_read

    def test_wording_states_absence_for_this_establishment_not_a_deficiency(
        self,
    ) -> None:
        block = content.YEAR_NOT_PUBLISHED
        assert "cet établissement" in block.simple_definition.lower()
        what_it_does_not_measure = block.what_it_does_not_measure.lower()
        # It must say nothing about either establishment's results — not this
        # one's, and not the one placed alongside it in the comparison.
        assert "ne dit rien des résultats" in what_it_does_not_measure
        assert "établissement placé à côté" in what_it_does_not_measure


class TestGlossaryContentIsNeutral:
    """F9 — the glossary is new user-facing editorial content.

    A definition explains what a word means. It must never say whether the
    thing it names is desirable, which is easy to slip into when defining
    something like "valeur ajoutée".
    """

    def test_no_forbidden_word_in_any_term(self) -> None:
        for term in glossary_content.ALL_TERMS:
            for field in (term.term, term.definition, term.source_note, term.example):
                if field is None:
                    continue
                match = _FORBIDDEN_PATTERN.search(field)
                assert match is None, (
                    f"{term.term_id}: {match.group(0) if match else ''}"
                )

    def test_no_term_recommends_or_advises(self) -> None:
        advisory = re.compile(
            r"\b(?:choisir|choisissez|privil[ée]gi|[ée]viter|conseill)", re.IGNORECASE
        )
        for term in glossary_content.ALL_TERMS:
            body = " ".join(
                part for part in (term.definition, term.example) if part is not None
            )
            assert advisory.search(body) is None, term.term_id

    def test_the_absence_term_still_attributes_no_cause(self) -> None:
        """Same rule as the F6 block: absence is stated, never explained away."""
        term = glossary_content.get_term("valeur_non_disponible")
        body = f"{term.definition} {term.example or ''}"

        assert "ne permet aucune conclusion" in body
        # It may mention that reasons exist; it must not pick one.
        assert "parce que" not in body.lower()
