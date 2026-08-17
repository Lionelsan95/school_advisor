"""API-10 / F9 — the glossary endpoint.

Pure static content, so these tests need neither a database nor a network.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.domain import glossary_content
from src.domain.explanatory_content import VALUE_ADDED
from src.interfaces.api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_returns_every_term_alphabetically(client: TestClient) -> None:
    body = client.get("/glossary").json()

    names = [term["terme"] for term in body["termes"]]
    assert names == sorted(names, key=str.lower)
    assert len(names) == len(glossary_content.ALL_TERMS)


def test_every_term_has_a_definition_and_a_source(client: TestClient) -> None:
    for term in client.get("/glossary").json()["termes"]:
        assert term["definition"].strip(), term["term_id"]
        # F10 applies to words as well as figures: a definition with no stated
        # origin is exactly the orphan content the traceability rule forbids.
        assert term["source"].strip(), term["term_id"]


def test_every_cross_link_resolves(client: TestClient) -> None:
    """A link to a term that does not exist is a bug to surface, not to ship."""
    terms = client.get("/glossary").json()["termes"]
    known = {term["term_id"] for term in terms}

    broken = {
        (term["term_id"], related)
        for term in terms
        for related in term["termes_associes"]
        if related not in known
    }
    assert broken == set()


def test_indicator_terms_are_derived_not_retyped() -> None:
    """The glossary must not hold a second copy of an indicator's definition.

    Two authored copies of "what value added is" would drift, and only one of
    them would be under the review gate.
    """
    derived = glossary_content.get_term(VALUE_ADDED.content_id)

    assert derived.definition == VALUE_ADDED.simple_definition
    assert derived.source_note == VALUE_ADDED.source_note


def test_a_term_always_returns_the_same_text(client: TestClient) -> None:
    first = client.get("/glossary").json()
    second = client.get("/glossary").json()
    assert first == second


def test_the_glossary_carries_the_scope_reminder(client: TestClient) -> None:
    assert client.get("/glossary").json()["rappel_de_portee"].strip()


def test_unknown_term_raises_rather_than_returning_a_placeholder() -> None:
    with pytest.raises(KeyError):
        glossary_content.get_term("pas_un_terme")
