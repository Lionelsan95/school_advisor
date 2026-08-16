"""HTTP contract tests for GET /establishments/compare (API-8, F4).

Bare FastAPI app carrying only the establishments router, with
`get_compare_use_case` (and, for two tests that need both endpoints at once,
`get_fact_sheet_use_case`) overridden — no database, following the pattern in
`test_assistant_api.py` and `test_establishments_history_api.py`.

Two things get more scrutiny here than a typical endpoint test would:

- Route resolution order (`/compare` must be matched before `/{uai}`, since
  the router registers it first deliberately — see
  `interfaces/api/establishments.py`).
- Neutrality (docs/14_Charte_Neutralite_Editoriale.md §11): this response
  must be structurally incapable of expressing a comparison outcome — no
  count of criteria won, no average, no gap between the two establishments,
  no score, no verdict, no recommendation.
"""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.application.compare_establishments import (
    Comparison,
    ComparisonCell,
    ComparisonRow,
    InvalidComparisonError,
)
from src.application.errors import MissingSourceReferenceError
from src.application.get_establishment_fact_sheet import FactSheet, to_result_row
from src.domain import explanatory_content as content
from src.domain.dataset_ids import DATASET_IVAL_GT
from src.domain.enums import IndicatorType
from src.interfaces.api import establishments as establishments_router
from src.interfaces.api.establishments import (
    _MISSING_PROVENANCE_MESSAGE,
    get_compare_use_case,
    get_fact_sheet_use_case,
)
from src.interfaces.api.schemas import ExplanationOut
from tests.unit.factories import (
    make_establishment,
    make_indicator_result,
    make_source_reference,
)

UAI_A = "0750001A"
UAI_B = "0750002B"


def _comparison(
    *,
    uai_a: str = UAI_A,
    uai_b: str = UAI_B,
    years_a: tuple[int, ...] = (2025,),
    years_b: tuple[int, ...] = (2025,),
    indicator_type: IndicatorType = IndicatorType.IVAL_GT,
    dataset_id: str = DATASET_IVAL_GT,
) -> Comparison:
    establishment_a = make_establishment(uai=uai_a)
    establishment_b = make_establishment(uai=uai_b)
    sources = {dataset_id: make_source_reference(dataset_id)}

    rows_a = {
        year: to_result_row(
            make_indicator_result(uai=uai_a, year=year, indicator_type=indicator_type),
            sources,
        )
        for year in years_a
    }
    rows_b = {
        year: to_result_row(
            make_indicator_result(uai=uai_b, year=year, indicator_type=indicator_type),
            sources,
        )
        for year in years_b
    }
    years = sorted(set(years_a) | set(years_b), reverse=True)
    return Comparison(
        establishments=(establishment_a, establishment_b),
        rows=tuple(
            ComparisonRow(
                year=year,
                cells=(
                    ComparisonCell(uai=uai_a, row=rows_a.get(year)),
                    ComparisonCell(uai=uai_b, row=rows_b.get(year)),
                ),
            )
            for year in years
        ),
    )


class ScriptedUseCase:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[object] = []

    def run(self, argument: object) -> object:
        self.calls.append(argument)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def client_for():
    clients: list[TestClient] = []

    def build(outcome: object) -> tuple[TestClient, ScriptedUseCase]:
        api = FastAPI()
        api.include_router(establishments_router.router)
        use_case = ScriptedUseCase(outcome)
        api.dependency_overrides[get_compare_use_case] = lambda: use_case
        client = TestClient(api)
        clients.append(client)
        return client, use_case

    yield build
    for client in clients:
        client.close()


class TestSuccessfulComparison:
    def test_two_valid_uais_return_200_with_both_establishments_in_request_order(
        self, client_for
    ) -> None:
        client, use_case = client_for(_comparison())

        response = client.get(
            "/establishments/compare", params=[("uai", UAI_A), ("uai", UAI_B)]
        )

        assert response.status_code == 200
        body = response.json()
        assert [e["uai"] for e in body["etablissements"]] == [UAI_A, UAI_B]
        assert use_case.calls == [[UAI_A, UAI_B]]


class TestValidationErrorsAre400:
    """The route just maps `InvalidComparisonError` to a 400 — the business
    rule itself (exactly two, no duplicates) is unit-tested against the real
    use case in `test_compare_establishments.py`. What matters here is that
    each of these query shapes actually reaches the use case with the right
    argument, and that the use case's rejection surfaces as a 400.
    """

    def test_a_single_uai_is_a_400(self, client_for) -> None:
        client, use_case = client_for(
            InvalidComparisonError(
                "exactly 2 establishments must be supplied to compare"
            )
        )

        response = client.get("/establishments/compare", params={"uai": UAI_A})

        assert response.status_code == 400
        assert use_case.calls == [[UAI_A]]

    def test_three_uais_is_a_400(self, client_for) -> None:
        client, use_case = client_for(
            InvalidComparisonError(
                "exactly 2 establishments must be supplied to compare"
            )
        )

        response = client.get(
            "/establishments/compare",
            params=[("uai", UAI_A), ("uai", UAI_B), ("uai", "0750003C")],
        )

        assert response.status_code == 400
        assert use_case.calls == [[UAI_A, UAI_B, "0750003C"]]

    def test_the_same_uai_twice_is_a_400(self, client_for) -> None:
        client, use_case = client_for(
            InvalidComparisonError("the establishments to compare must be different")
        )

        response = client.get(
            "/establishments/compare", params=[("uai", UAI_A), ("uai", UAI_A)]
        )

        assert response.status_code == 400
        assert use_case.calls == [[UAI_A, UAI_A]]

    def test_a_malformed_uai_is_a_400_before_the_use_case_is_called(
        self, client_for
    ) -> None:
        client, use_case = client_for(_comparison())

        response = client.get(
            "/establishments/compare", params=[("uai", UAI_A), ("uai", "not-a-uai")]
        )

        assert response.status_code == 400
        assert use_case.calls == []


class TestUnknownEstablishmentIs404:
    def test_a_well_formed_but_unknown_uai_pair_returns_404(self, client_for) -> None:
        client, use_case = client_for(None)

        response = client.get(
            "/establishments/compare", params=[("uai", UAI_A), ("uai", UAI_B)]
        )

        assert response.status_code == 404
        assert use_case.calls == [[UAI_A, UAI_B]]


class TestMissingProvenanceIs503:
    def test_missing_source_reference_is_a_503_with_the_neutral_message(
        self, client_for
    ) -> None:
        client, _ = client_for(
            MissingSourceReferenceError(DATASET_IVAL_GT, UAI_A, 2025)
        )

        response = client.get(
            "/establishments/compare", params=[("uai", UAI_A), ("uai", UAI_B)]
        )

        assert response.status_code == 503
        body = response.json()
        assert body == {"detail": _MISSING_PROVENANCE_MESSAGE}
        # A neutral French sentence, not a stack trace or an exception repr.
        assert "Traceback" not in body["detail"]
        assert "MissingSourceReferenceError" not in body["detail"]


class TestSortParameterIsRejected:
    @pytest.mark.parametrize("param", ["sort_by", "sort", "order_by", "tri"])
    def test_a_sort_parameter_is_a_400_before_the_use_case_is_called(
        self, client_for, param: str
    ) -> None:
        client, use_case = client_for(_comparison())

        response = client.get(
            "/establishments/compare",
            params=[("uai", UAI_A), ("uai", UAI_B), (param, "asc")],
        )

        assert response.status_code == 400
        assert use_case.calls == []


class TestCompareRouteResolvesBeforeTheUaiCatchAll:
    """`/compare` is registered before `/{uai}` in the router deliberately.
    Registered after it, "compare" would be captured as a path parameter and
    rejected as a malformed UAI — this pins that it is not.
    """

    def test_compare_query_is_not_captured_as_a_uai_lookup(self) -> None:
        api = FastAPI()
        api.include_router(establishments_router.router)
        api.dependency_overrides[get_compare_use_case] = lambda: ScriptedUseCase(
            _comparison()
        )
        client = TestClient(api)
        try:
            response = client.get(
                "/establishments/compare", params=[("uai", UAI_A), ("uai", UAI_B)]
            )
        finally:
            client.close()

        assert response.status_code == 200
        body = response.json()
        # A fact-sheet 400 for the literal string "compare" would read this
        # way; a genuine comparison response never does.
        assert "Not a valid UAI" not in response.text
        assert "etablissements" in body
        assert "identite" not in body


def _all_keys(value: object) -> set[str]:
    """Every dict key anywhere in a JSON-decoded body, recursively."""
    if isinstance(value, dict):
        keys = set(value.keys())
        for nested in value.values():
            keys |= _all_keys(nested)
        return keys
    if isinstance(value, list):
        keys = set()
        for item in value:
            keys |= _all_keys(item)
        return keys
    return set()


def _all_string_values(value: object) -> set[str]:
    """Every string leaf anywhere in a JSON-decoded body, recursively."""
    if isinstance(value, dict):
        strings: set[str] = set()
        for nested in value.values():
            strings |= _all_string_values(nested)
        return strings
    if isinstance(value, list):
        strings = set()
        for item in value:
            strings |= _all_string_values(item)
        return strings
    if isinstance(value, str):
        return {value}
    return set()


# docs/14_Charte_Neutralite_Editoriale.md §11: the product computes no count
# of criteria won, average, overall gap, weighted score, textual verdict, or
# recommendation between the two compared establishments. This is the
# comparison-specific vocabulary for that outcome — distinct from (and in
# addition to) the general evaluative-wording list in `test_neutrality.py`.
_FORBIDDEN_COMPARISON_WORDS = (
    "ecart",
    "écart",
    "difference",
    "différence",
    "delta",
    "score",
    "gagnant",
    "winner",
    "verdict",
    "classement",
    "meilleur",
    "moyenne_generale",
    "moyenne_générale",
    "total_criteres",
    "total_critères",
)
_FORBIDDEN_COMPARISON_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _FORBIDDEN_COMPARISON_WORDS) + r")\b",
    re.IGNORECASE,
)


class TestNoComparisonOutcomeIsExpressibleInTheResponseShape:
    """The most important tests in this module.

    The string-value scan below deliberately carves out the top-level
    `explications` block. That block is reviewed editorial content served
    verbatim from `domain/explanatory_content.py` (see CLAUDE.md's rule that
    F3/F6/F7 content is static and human-reviewed, never generated or edited
    at request time) — not composed by the comparison code — and it
    legitimately contains "écart" three times inside the `valeur_ajoutee`
    block. That is the DEPP's own definition of value added: the gap between
    *one* establishment's own observed and statistically expected result, not
    a gap between the two establishments being compared here. Banning "écart"
    unconditionally would fail on the project's own human-approved
    vocabulary — the same false-positive trap a blanket word ban always
    risks.

    The carve-out is only safe because `TestExplicationsBlockIsByteIdentical
    ToTheFactSheet` below independently proves the comparison path serves
    that exact static content, unmodified, rather than composing its own
    text under cover of the exemption. Do not remove the carve-out to
    "tighten" this test without keeping that guarantee — and note the key
    scan just below still runs over the *whole* body, `explications`
    included: no key may ever be *named* for a comparison outcome, which is
    the assertion that matters most.
    """

    def test_no_key_anywhere_names_a_comparison_outcome(self, client_for) -> None:
        client, _ = client_for(_comparison())

        response = client.get(
            "/establishments/compare", params=[("uai", UAI_A), ("uai", UAI_B)]
        )

        assert response.status_code == 200
        offenders = {
            key
            for key in _all_keys(response.json())
            if _FORBIDDEN_COMPARISON_PATTERN.search(key)
        }
        assert not offenders, f"forbidden comparison key(s) present: {offenders}"

    def test_no_string_value_outside_explications_names_a_comparison_outcome(
        self, client_for
    ) -> None:
        client, _ = client_for(_comparison())

        response = client.get(
            "/establishments/compare", params=[("uai", UAI_A), ("uai", UAI_B)]
        )

        assert response.status_code == 200
        body = response.json()
        body_without_explications = {
            key: value for key, value in body.items() if key != "explications"
        }
        offenders = {
            text
            for text in _all_string_values(body_without_explications)
            if _FORBIDDEN_COMPARISON_PATTERN.search(text)
        }
        assert not offenders, f"forbidden comparison string(s) present: {offenders}"


class TestNoRowLevelFieldPairsTheTwoEstablishmentsValuesTogether:
    """Every numeric value must belong to exactly one establishment's cell —
    there must be no field that hands the frontend both establishments'
    figures for the same indicator/year already paired up, which is the
    shape a difference would be computed from.
    """

    def test_a_row_carries_only_year_and_a_list_of_independent_cells(
        self, client_for
    ) -> None:
        client, _ = client_for(_comparison())

        response = client.get(
            "/establishments/compare", params=[("uai", UAI_A), ("uai", UAI_B)]
        )

        assert response.status_code == 200
        rows = response.json()["lignes"]
        assert rows, "expected at least one row to inspect"
        for row in rows:
            assert set(row.keys()) == {"annee", "cellules"}
            assert len(row["cellules"]) == 2
            cell_uais = [cell["uai"] for cell in row["cellules"]]
            assert len(set(cell_uais)) == 2, "cells must not collapse two uais into one"
            for cell in row["cellules"]:
                assert set(cell.keys()) == {
                    "uai",
                    "annee_publiee",
                    "resultat",
                    "explication_absence",
                }


class TestExplicationsBlockIsByteIdenticalToTheFactSheet:
    """Guards the carve-out used by `TestNoComparisonOutcomeIsExpressibleIn
    TheResponseShape` above: the comparison path must serve the exact same
    static explanatory blocks the fact sheet does, for the same content ids —
    never a reworded or comparison-specific version of them.
    """

    def test_shared_explanation_blocks_match_the_fact_sheet_verbatim(self) -> None:
        comparison = _comparison()
        fact_sheet_rows = tuple(
            cell.row
            for row in comparison.rows
            for cell in row.cells
            if cell.uai == UAI_A and cell.row is not None
        )
        fact_sheet = FactSheet(
            establishment=comparison.establishments[0],
            results=fact_sheet_rows,
            last_synchronised_at=None,
        )

        api = FastAPI()
        api.include_router(establishments_router.router)
        api.dependency_overrides[get_compare_use_case] = lambda: ScriptedUseCase(
            comparison
        )
        api.dependency_overrides[get_fact_sheet_use_case] = lambda: ScriptedUseCase(
            fact_sheet
        )
        client = TestClient(api)
        try:
            compare_body = client.get(
                "/establishments/compare",
                params=[("uai", UAI_A), ("uai", UAI_B)],
            ).json()
            fact_sheet_body = client.get(f"/establishments/{UAI_A}").json()
        finally:
            client.close()

        shared_ids = set(fact_sheet_body["explications"])
        assert shared_ids <= set(compare_body["explications"])
        for content_id in shared_ids:
            assert (
                compare_body["explications"][content_id]
                == fact_sheet_body["explications"][content_id]
            ), f"{content_id} drifted between /compare and the fact sheet"

        # The one block the fact sheet never carries — checked against the
        # static source directly, since there is no second endpoint to diff
        # it against.
        assert compare_body["explications"]["annee_non_publiee"] == (
            ExplanationOut.of(content.YEAR_NOT_PUBLISHED).model_dump()
        )
