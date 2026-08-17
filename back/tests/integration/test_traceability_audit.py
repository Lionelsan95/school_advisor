"""OPS-4 — the automatable half of the data traceability audit.

`docs/02_Architecture_Decisions.md` ("Contrainte spécifique : traçabilité des
réponses") requires that everything shown to a user traces to one of exactly
three origins:

  1. raw official data,
  2. a documented deterministic calculation,
  3. versioned static editorial content.

This walks real API responses and asserts every value resolves to one of them.
It is a standing audit rather than a feature test: it makes no assumptions about
*which* fields exist, so a field added later is caught by it without anyone
remembering to extend a list.

**What this cannot check, and what therefore stays manual:** whether the prose
is accurate and neutral, as opposed to merely present and versioned. A block
could be correctly registered, correctly versioned, correctly attached — and
wrong. The manual procedure for that lives in `docs/deployment-notes.md`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from src.domain import explanatory_content as content
from src.domain import glossary_content
from src.interfaces.api.main import app
from tests.integration.helpers import (
    insert_establishment,
    insert_indicator,
)

pytestmark = pytest.mark.integration

# Every content_id the backend can legitimately reference, from the real
# registries rather than a list copied into the test.
KNOWN_CONTENT_IDS = frozenset(content.CONTENT_BY_ID) | frozenset(
    glossary_content.TERMS_BY_ID
)

# Keys that carry a figure object. Anything matching this shape is audited
# wherever it appears, at any depth.
FIGURE_KEYS = frozenset({"valeur", "calcule", "note_de_calcul", "explication_absence"})


def _is_figure(node: Any) -> bool:
    return isinstance(node, dict) and FIGURE_KEYS.issubset(node.keys())


def _walk(node: Any, path: str) -> list[tuple[str, Any]]:
    """Every (path, node) pair in a response, so nothing can hide in a nest."""
    found = [(path, node)]
    if isinstance(node, dict):
        for key, value in node.items():
            found.extend(_walk(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_walk(value, f"{path}[{index}]"))
    return found


@pytest.fixture
def client(database_url: str) -> Iterator[TestClient]:
    del database_url  # depended on so the disposable-database guard runs first
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded_traceable_uai(
    db_connection: psycopg.Connection, seeded_uais: list[str]
) -> str:
    """One establishment exercising all three origins at once.

    2023 publishes a rate and a value added, so the derived expected rate is
    present too (origin 2). 2022 publishes a rate but no value added — the real
    Mayotte-shaped case — so the audit sees an absence pointing at versioned
    content (origin 3) beside raw published data (origin 1).
    """
    uai = "9990101T"
    insert_establishment(db_connection, uai, name="Lycée de contrôle")
    insert_indicator(
        db_connection,
        uai,
        2023,
        indicator_type="IVAL_GT",
        success_rate=94.0,
        value_added_success=3.0,
    )
    insert_indicator(
        db_connection,
        uai,
        2022,
        indicator_type="IVAL_GT",
        success_rate=57.0,
        value_added_success=None,
    )
    seeded_uais.append(uai)
    return uai


class TestEveryFigureHasAnOrigin:
    """Origins 1 and 2: a number is either published or derived, never bare."""

    def test_every_figure_resolves_to_one_of_the_three_origins(
        self, client: TestClient, seeded_traceable_uai: str
    ) -> None:
        body = client.get(f"/establishments/{seeded_traceable_uai}").json()

        figures = [(p, n) for p, n in _walk(body, "$") if _is_figure(n)]
        assert figures, "the sample response must contain figures to audit"

        for path, figure in figures:
            if figure["valeur"] is None:
                # An absence is origin 3: it must point at versioned content
                # explaining what an absence means, and nothing else.
                assert figure["explication_absence"] in KNOWN_CONTENT_IDS, path
                assert figure["note_de_calcul"] is None, path
            elif figure["calcule"]:
                # Origin 2: a derived value must state its calculation, or a
                # reader cannot tell it from an official figure.
                assert figure["note_de_calcul"], path
            else:
                # Origin 1: raw official data. It must not claim a calculation.
                assert figure["note_de_calcul"] is None, path

    def test_every_result_row_carries_its_source(
        self, client: TestClient, seeded_traceable_uai: str
    ) -> None:
        body = client.get(f"/establishments/{seeded_traceable_uai}").json()

        for row in body["resultats"]:
            source = row["source"]
            assert source["dataset_id"], row["annee"]
            assert source["url"].startswith("http"), row["annee"]
            assert source["derniere_synchronisation"], row["annee"]


class TestEveryExplanationIsVersionedContent:
    """Origin 3: prose is registered and versioned, never composed."""

    def test_fact_sheet_explanations_are_all_registered(
        self, client: TestClient, seeded_traceable_uai: str
    ) -> None:
        body = client.get(f"/establishments/{seeded_traceable_uai}").json()

        for content_id, block in body["explications"].items():
            assert content_id in KNOWN_CONTENT_IDS
            assert block["content_id"] == content_id
            # A version is what lets a later reader tell whether the text they
            # reviewed is the text being served.
            assert isinstance(block["version"], int) and block["version"] >= 1

    def test_served_text_is_identical_to_the_registry(
        self, client: TestClient, seeded_traceable_uai: str
    ) -> None:
        """The registry is the source of truth, not a suggestion.

        If the API could reword a block in flight, versioning it would prove
        nothing.
        """
        body = client.get(f"/establishments/{seeded_traceable_uai}").json()

        for content_id, block in body["explications"].items():
            registered = content.CONTENT_BY_ID[content_id]
            assert block["definition_simple"] == registered.simple_definition
            assert block["comment_lire"] == registered.how_to_read
            assert block["ce_que_cela_ne_mesure_pas"] == (
                registered.what_it_does_not_measure
            )

    def test_the_scope_disclaimer_is_the_registered_constant(
        self, client: TestClient, seeded_traceable_uai: str
    ) -> None:
        body = client.get(f"/establishments/{seeded_traceable_uai}").json()
        assert body["rappel_de_portee"] == content.SCOPE_DISCLAIMER

    def test_glossary_terms_are_all_registered_and_sourced(
        self, client: TestClient
    ) -> None:
        for term in client.get("/glossary").json()["termes"]:
            assert term["term_id"] in glossary_content.TERMS_BY_ID
            # F10 applies to words too: a definition with no stated origin is
            # the same orphan content the traceability rule forbids for figures.
            assert term["source"].strip(), term["term_id"]


class TestNoOrphanValues:
    """The audit's real question: could anything reach a reader untraceable?"""

    def test_no_string_field_outside_the_registries_reads_as_prose(
        self, client: TestClient, seeded_traceable_uai: str
    ) -> None:
        """Catches a future field quietly carrying composed explanatory text.

        Identity strings, ids, dates and labels are short. A long sentence
        appearing somewhere other than a registered content block is the shape
        of the mistake this audit exists to catch, so it must be justified
        rather than merely allowed.
        """
        body = client.get(f"/establishments/{seeded_traceable_uai}").json()
        registered_text = {
            value
            for block in content.CONTENT_BY_ID.values()
            for value in (
                block.simple_definition,
                block.how_to_read,
                block.what_it_measures,
                block.what_it_does_not_measure,
                block.method,
                block.source_note,
                block.title,
            )
            if value
        } | {content.SCOPE_DISCLAIMER}

        # Computation notes are origin 2 and are asserted elsewhere.
        allowed_paths = (".note_de_calcul",)

        for path, node in _walk(body, "$"):
            if not isinstance(node, str) or len(node) < 80:
                continue
            if node in registered_text or path.endswith(allowed_paths):
                continue
            pytest.fail(
                f"Untraceable prose at {path}: {node[:90]!r}. Every sentence "
                f"shown to a reader must come from a versioned content block."
            )
