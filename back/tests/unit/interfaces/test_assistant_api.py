"""HTTP contract tests for the bounded assistant with dependencies overridden."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.application.assistant_search import (
    AssistantSearchClarification,
    AssistantSearchSuccess,
    AssistantSearchUnavailable,
    ClarificationKind,
    InvalidAssistantQueryError,
    UnavailableReason,
)
from src.application.ports import (
    CommuneSearchHit,
    SearchCriteria,
    SearchHit,
    SearchResults,
)
from src.application.search_communes import (
    CommuneSearchResults,
    MissingCommuneSourceError,
)
from src.application.search_establishments import (
    EstablishmentSearchResponse,
    MissingSearchSourceError,
)
from src.domain import assistant_content
from src.domain.commune import Commune
from src.domain.dataset_ids import DATASET_COMMUNES, DATASET_DIRECTORY
from src.domain.source_reference import SourceReference
from src.interfaces.api import assistant as assistant_router
from src.interfaces.api.assistant import get_assistant_search_use_case
from tests.unit.factories import make_establishment


def _source(dataset_id: str) -> SourceReference:
    return SourceReference(
        dataset_id=dataset_id,
        url=f"https://example.invalid/{dataset_id}",
        last_synchronised_at=datetime(2026, 8, 15, tzinfo=UTC),
        source_published_at=None,
    )


def _place_results(*communes: Commune) -> CommuneSearchResults:
    return CommuneSearchResults(
        hits=tuple(
            CommuneSearchHit(commune=commune, match_tier=1) for commune in communes
        ),
        source=_source(DATASET_COMMUNES),
    )


def _commune(code: str, name: str) -> Commune:
    return Commune(
        code=code,
        name=name,
        postal_codes=("75001",),
        department_code=code[:2],
        latitude=48.8566,
        longitude=2.3522,
    )


def _success(*, subjective: bool = False) -> AssistantSearchSuccess:
    place = _place_results(_commune("75056", "Paris"))
    criteria = SearchCriteria(
        commune_code="75056",
        establishment_type=None,
    )
    return AssistantSearchSuccess(
        search=EstablishmentSearchResponse(
            results=SearchResults(
                hits=(SearchHit(make_establishment()),),
                total_count=1,
            ),
            source=_source(DATASET_DIRECTORY),
        ),
        criteria=criteria,
        subjective_request_reframed=subjective,
        resolved_place=place,
    )


class ScriptedUseCase:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[str] = []

    def run(self, query: str) -> object:
        self.calls.append(query)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def client_for():
    clients: list[TestClient] = []

    def build(outcome: object) -> tuple[TestClient, ScriptedUseCase]:
        api = FastAPI()
        api.include_router(assistant_router.router)
        use_case = ScriptedUseCase(outcome)
        api.dependency_overrides[get_assistant_search_use_case] = lambda: use_case
        client = TestClient(api)
        clients.append(client)
        return client, use_case

    yield build
    for client in clients:
        client.close()


def test_success_exposes_resolved_official_place_provenance_and_static_reframe(
    client_for,
) -> None:
    client, use_case = client_for(_success(subjective=True))

    response = client.post(
        "/assistant/search",
        json={"requete": "Quel est le meilleur collège à Paris ?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert use_case.calls == ["Quel est le meilleur collège à Paris ?"]
    assert body["etat"] == "resultats"
    assert body["lieu_resolu"]["code"] == "75056"
    assert body["source_lieu"]["dataset_id"] == DATASET_COMMUNES
    assert body["recherche"]["source"]["dataset_id"] == DATASET_DIRECTORY
    assert body["reformulation_neutre"] == (
        assistant_content.SUBJECTIVE_REQUEST_REFRAME
    )
    assert set(body["recherche"]["resultats"][0]).isdisjoint(
        {"score", "rang", "classement", "recommandation"}
    )


def test_ambiguity_returns_one_approved_question_and_only_official_options(
    client_for,
) -> None:
    options = _place_results(
        _commune("75056", "Paris"),
        _commune("97123", "Paris"),
    )
    outcome = AssistantSearchClarification(
        ClarificationKind.LOCATION_AMBIGUOUS,
        options=options,
    )
    client, _ = client_for(outcome)

    response = client.post("/assistant/search", json={"requete": "collèges à Paris"})

    assert response.status_code == 200
    body = response.json()
    assert body["etat"] == "clarification"
    assert body["type_clarification"] == "lieu_ambigu"
    assert body["question"] == assistant_content.LOCATION_AMBIGUOUS
    assert [option["code"] for option in body["options"]] == ["75056", "97123"]
    assert body["source"]["dataset_id"] == DATASET_COMMUNES
    assert "message" not in body


@pytest.mark.parametrize(
    ("kind", "options", "question", "source_expected"),
    [
        (
            ClarificationKind.LOCATION_REQUIRED,
            None,
            assistant_content.LOCATION_REQUIRED,
            False,
        ),
        (
            ClarificationKind.LOCATION_UNKNOWN,
            _place_results(),
            assistant_content.LOCATION_UNKNOWN,
            True,
        ),
        (
            ClarificationKind.LOCATION_HAS_NO_CENTRE,
            _place_results(_commune("75056", "Paris")),
            assistant_content.LOCATION_HAS_NO_CENTRE,
            True,
        ),
    ],
)
def test_other_clarifications_use_only_the_approved_static_question(
    client_for,
    kind: ClarificationKind,
    options: CommuneSearchResults | None,
    question: str,
    source_expected: bool,
) -> None:
    client, _ = client_for(AssistantSearchClarification(kind, options=options))

    body = client.post("/assistant/search", json={"requete": "recherche"}).json()

    assert body["question"] == question
    assert (body["source"] is not None) is source_expected


def test_provider_unavailable_uses_the_approved_static_fallback(client_for) -> None:
    client, _ = client_for(AssistantSearchUnavailable())

    response = client.post(
        "/assistant/search", json={"requete": "collèges publics autour de Paris"}
    )

    assert response.status_code == 200
    # A neutral query, so there is no ranking stance to restate alongside.
    assert response.json() == {
        "etat": "indisponible",
        "message": assistant_content.INTERPRETER_UNAVAILABLE,
        "reformulation_neutre": None,
    }


@pytest.mark.parametrize(
    ("reason", "subjective", "expected_message", "expected_reformulation"),
    [
        (
            UnavailableReason.INTERPRETATION_REJECTED,
            True,
            assistant_content.SUBJECTIVE_REQUEST_REFRAME,
            None,
        ),
        (
            UnavailableReason.INTERPRETATION_REJECTED,
            False,
            assistant_content.INTERPRETER_UNAVAILABLE,
            None,
        ),
        (
            UnavailableReason.PROVIDER_UNAVAILABLE,
            True,
            assistant_content.INTERPRETER_UNAVAILABLE,
            assistant_content.SUBJECTIVE_REQUEST_REFRAME,
        ),
        (
            UnavailableReason.PROVIDER_UNAVAILABLE,
            False,
            assistant_content.INTERPRETER_UNAVAILABLE,
            None,
        ),
    ],
    ids=[
        "rejected-subjective-is-the-charter-refusal",
        "rejected-neutral-reports-unavailable",
        "provider-outage-subjective-keeps-the-no-ranking-stance",
        "provider-outage-neutral-reports-unavailable",
    ],
)
def test_unavailable_reason_and_subjective_flag_select_the_exact_wire_body(
    client_for,
    reason: UnavailableReason,
    subjective: bool,
    expected_message: str,
    expected_reformulation: str | None,
) -> None:
    """The four (reason x subjective) combinations must each produce exactly
    the wire body the charter and the fix intend — in particular, a real
    provider outage on a subjective query still carries the no-ranking stance
    in `reformulation_neutre` rather than dropping it (case 3), and only the
    rejected+subjective combination gets the charter's §12 refusal as the
    leading `message` (case 1).
    """
    outcome = AssistantSearchUnavailable(
        reason=reason, subjective_request_reframed=subjective
    )
    client, _ = client_for(outcome)

    response = client.post(
        "/assistant/search", json={"requete": "Quel est le meilleur collège ?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["etat"] == "indisponible"
    assert body["message"] == expected_message
    assert body["reformulation_neutre"] == expected_reformulation
    assert "resultats" not in body
    assert "recherche" not in body


@pytest.mark.parametrize(
    "error",
    [
        MissingSearchSourceError("directory provenance missing"),
        MissingCommuneSourceError("commune provenance missing"),
    ],
)
def test_missing_factual_provenance_withholds_the_whole_answer_with_503(
    client_for, error: Exception
) -> None:
    client, _ = client_for(error)

    response = client.post("/assistant/search", json={"requete": "recherche"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Une référence de source nécessaire à cette recherche est "
            "indisponible. Les résultats ne sont pas publiés afin de ne pas "
            "présenter de données sans origine."
        )
    }


def test_application_validation_error_is_a_400(client_for) -> None:
    client, _ = client_for(InvalidAssistantQueryError("invalid query"))

    response = client.post("/assistant/search", json={"requete": " "})

    assert response.status_code == 400
    assert response.json() == {"detail": "invalid query"}


@pytest.mark.parametrize("payload", [{}, {"requete": ""}, {"requete": "x" * 501}])
def test_wire_shape_validation_is_a_422_before_the_use_case(
    client_for, payload: dict[str, str]
) -> None:
    client, use_case = client_for(_success())

    response = client.post("/assistant/search", json=payload)

    assert response.status_code == 422
    assert use_case.calls == []
