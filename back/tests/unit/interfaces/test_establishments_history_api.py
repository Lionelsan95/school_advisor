"""HTTP contract tests for GET /establishments/{uai}/history (API-7, F5).

Bare FastAPI app carrying only the establishments router, with
`get_history_use_case` overridden — no database, following the pattern in
`test_assistant_api.py`. Error semantics mirror the fact sheet endpoint
exactly (400 malformed / 404 unknown / 503 missing provenance), and the
charter's chart rules (docs/14_Charte_Neutralite_Editoriale.md §10) are
checked at the wire level: no trend/projection field, and the rupture note
only when this establishment's own history spans it.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.application.errors import MissingSourceReferenceError
from src.application.get_establishment_fact_sheet import to_result_row
from src.application.get_establishment_history import EstablishmentHistory
from src.domain.dataset_ids import DATASET_IVAC, DATASET_IVAL_GT
from src.domain.enums import IndicatorType
from src.domain.methodology_break import IVAL_BACCALAUREAT_REFORM, breaks_spanned_by
from src.interfaces.api import establishments as establishments_router
from src.interfaces.api.establishments import (
    _MISSING_PROVENANCE_MESSAGE,
    get_history_use_case,
)
from tests.unit.factories import (
    make_establishment,
    make_indicator_result,
    make_source_reference,
)

UAI = "0750001A"


def _history(
    *,
    uai: str = UAI,
    years: tuple[int, ...] = (2025,),
    indicator_type: IndicatorType = IndicatorType.IVAC,
    dataset_id: str = DATASET_IVAC,
) -> EstablishmentHistory:
    establishment = make_establishment(uai=uai)
    sources = {dataset_id: make_source_reference(dataset_id)}
    points = tuple(
        to_result_row(
            make_indicator_result(uai=uai, year=year, indicator_type=indicator_type),
            sources,
        )
        for year in sorted(years)
    )
    years_by_type = {indicator_type: set(years)} if years else {}

    return EstablishmentHistory(
        establishment=establishment,
        points=points,
        methodology_breaks=breaks_spanned_by(years_by_type),
    )


class ScriptedUseCase:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[str] = []

    def run(self, uai: str) -> object:
        self.calls.append(uai)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def client_for() -> Iterator[object]:
    clients: list[TestClient] = []

    def build(outcome: object) -> tuple[TestClient, ScriptedUseCase]:
        api = FastAPI()
        api.include_router(establishments_router.router)
        use_case = ScriptedUseCase(outcome)
        api.dependency_overrides[get_history_use_case] = lambda: use_case
        client = TestClient(api)
        clients.append(client)
        return client, use_case

    yield build
    for client in clients:
        client.close()


class TestMalformedUai:
    def test_a_malformed_uai_is_a_400(self, client_for) -> None:
        client, use_case = client_for(_history())

        response = client.get("/establishments/not-a-uai/history")

        assert response.status_code == 400
        assert use_case.calls == []


class TestUnknownUai:
    def test_a_well_formed_unknown_uai_is_a_404(self, client_for) -> None:
        client, use_case = client_for(None)

        response = client.get(f"/establishments/{UAI}/history")

        assert response.status_code == 404
        assert use_case.calls == [UAI]


class TestMissingProvenance:
    def test_missing_source_reference_is_a_503_with_the_neutral_message(
        self, client_for
    ) -> None:
        client, _ = client_for(MissingSourceReferenceError(DATASET_IVAC, UAI, 2025))

        response = client.get(f"/establishments/{UAI}/history")

        assert response.status_code == 503
        body = response.json()
        assert body == {"detail": _MISSING_PROVENANCE_MESSAGE}
        # A neutral French sentence, not a stack trace or an exception repr.
        assert "Traceback" not in body["detail"]
        assert "MissingSourceReferenceError" not in body["detail"]


class TestMethodologyBreakOnTheWire:
    def test_a_span_crossing_2021_carries_the_static_break_note(
        self, client_for
    ) -> None:
        history = _history(
            years=(2019, 2020, 2021, 2022),
            indicator_type=IndicatorType.IVAL_GT,
            dataset_id=DATASET_IVAL_GT,
        )
        client, _ = client_for(history)

        response = client.get(f"/establishments/{UAI}/history")

        assert response.status_code == 200
        body = response.json()
        assert len(body["ruptures_methodologiques"]) == 1
        rupture = body["ruptures_methodologiques"][0]
        assert rupture["annee"] == IVAL_BACCALAUREAT_REFORM.year
        assert rupture["content_id"] == IVAL_BACCALAUREAT_REFORM.content_id
        assert rupture["note"] == IVAL_BACCALAUREAT_REFORM.note

    def test_a_span_not_crossing_2021_carries_an_empty_list(self, client_for) -> None:
        history = _history(
            years=(2022, 2023),
            indicator_type=IndicatorType.IVAL_GT,
            dataset_id=DATASET_IVAL_GT,
        )
        client, _ = client_for(history)

        response = client.get(f"/establishments/{UAI}/history")

        assert response.status_code == 200
        assert response.json()["ruptures_methodologiques"] == []


class TestPointsAndCoveredYearsOnTheWire:
    def test_points_are_ascending_and_covered_years_match(self, client_for) -> None:
        history = _history(years=(2023, 2021, 2022), indicator_type=IndicatorType.IVAC)
        client, _ = client_for(history)

        response = client.get(f"/establishments/{UAI}/history")

        assert response.status_code == 200
        body = response.json()
        assert [point["annee"] for point in body["points"]] == [2021, 2022, 2023]
        assert body["annees_couvertes"] == [2021, 2022, 2023]


_FORBIDDEN_CHART_FIELD_NAMES = {
    "tendance",
    "trend",
    "projection",
    "pente",
    "slope",
    "moyenne",
    "average",
    "moyenne_nationale",
    "moyenne_locale",
}


def _all_keys(value: object) -> set[str]:
    """Every dict key anywhere in a JSON-decoded body, recursively."""
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(key)
            keys |= _all_keys(nested)
    elif isinstance(value, list):
        for item in value:
            keys |= _all_keys(item)
    return keys


class TestNeutralityOfTheHistoryResponse:
    """docs/14_Charte_Neutralite_Editoriale.md §10: "aucune courbe de
    projection", no unexplained average, and — per CLAUDE.md — the tool
    explains, it never judges. Nothing in this response may carry a computed
    trend, slope, projection or average.
    """

    def test_no_trend_projection_slope_or_average_field_anywhere_in_the_body(
        self, client_for
    ) -> None:
        history = _history(
            years=(2019, 2020, 2021, 2022),
            indicator_type=IndicatorType.IVAL_GT,
            dataset_id=DATASET_IVAL_GT,
        )
        client, _ = client_for(history)

        response = client.get(f"/establishments/{UAI}/history")

        assert response.status_code == 200
        keys = _all_keys(response.json())
        offenders = keys & _FORBIDDEN_CHART_FIELD_NAMES
        assert not offenders, f"forbidden chart field(s) present: {offenders}"

    def test_the_rupture_note_states_non_comparability_not_a_direction(
        self, client_for
    ) -> None:
        """The break must say the values are not comparable across the
        reform, never that results improved or declined."""
        history = _history(
            years=(2019, 2020, 2021, 2022),
            indicator_type=IndicatorType.IVAL_GT,
            dataset_id=DATASET_IVAL_GT,
        )
        client, _ = client_for(history)

        response = client.get(f"/establishments/{UAI}/history")

        note = response.json()["ruptures_methodologiques"][0]["note"].lower()
        for directional_word in (
            "amélioration",
            "dégradation",
            "progrès",
            "recul",
            "hausse",
            "baisse",
            "meilleur",
            "moins bon",
        ):
            assert directional_word not in note, (
                f"rupture note asserts a direction ({directional_word!r}): {note!r}"
            )
        assert "comparable" in note
