"""Unit tests for `OdsClient.assert_schema` — THE MANDATORY TEST.

CLAUDE.md requires a source-schema-mismatch test case for any ingestion
change, and the Phase 0 spike explicitly deferred this test to Phase 1 (see
docs/05_Resultats_Spike_Technique.md, "Limite assumée de ce spike"). These
tests simulate an upstream schema change purely by mocking the HTTP layer
with respx — no network call is ever made.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from src.infrastructure.ingestion.errors import SourceSchemaMismatchError
from src.infrastructure.ingestion.ods_client import (
    DATASET_DIRECTORY,
    DEFAULT_BASE_URL,
    OdsClient,
)

CATALOG_URL = f"{DEFAULT_BASE_URL}/catalog/datasets/{DATASET_DIRECTORY}"


def _catalog_payload(field_names: list[str]) -> dict:
    return {"fields": [{"name": name} for name in field_names]}


def test_field_names_reads_the_catalog_metadata(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(CATALOG_URL).mock(
        return_value=httpx.Response(
            200, json=_catalog_payload(["uai", "nom_etablissement"])
        )
    )
    client = OdsClient()

    assert client.field_names(DATASET_DIRECTORY) == ["uai", "nom_etablissement"]


def test_assert_schema_passes_when_every_expected_field_is_present(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.get(CATALOG_URL).mock(
        return_value=httpx.Response(
            200,
            json=_catalog_payload(["uai", "nom_etablissement", "an_extra_field"]),
        )
    )
    client = OdsClient()

    client.assert_schema(DATASET_DIRECTORY, ["uai", "nom_etablissement"])  # no raise


def test_assert_schema_raises_when_an_expected_field_disappears(
    respx_mock: respx.MockRouter,
) -> None:
    """Simulates a renamed/removed upstream column — the exact scenario the
    Phase 0 spike's own scripts could only assert on ad hoc, not in a real
    test suite."""
    respx_mock.get(CATALOG_URL).mock(
        return_value=httpx.Response(
            200,
            json=_catalog_payload(
                ["identifiant_de_l_etablissement", "nom_etablissement"]
            ),
        )
    )
    client = OdsClient()

    with pytest.raises(SourceSchemaMismatchError) as excinfo:
        client.assert_schema(
            DATASET_DIRECTORY,
            ["identifiant_de_l_etablissement", "nom_etablissement", "code_postal"],
        )

    error = excinfo.value
    assert error.dataset_id == DATASET_DIRECTORY
    assert error.missing == ["code_postal"]
    assert "code_postal" in str(error)
    assert DATASET_DIRECTORY in str(error)


def test_assert_schema_names_every_missing_field_when_several_disappear(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.get(CATALOG_URL).mock(
        return_value=httpx.Response(200, json=_catalog_payload(["nom_etablissement"]))
    )
    client = OdsClient()

    with pytest.raises(SourceSchemaMismatchError) as excinfo:
        client.assert_schema(
            DATASET_DIRECTORY,
            ["identifiant_de_l_etablissement", "nom_etablissement", "code_postal"],
        )

    assert set(excinfo.value.missing) == {
        "identifiant_de_l_etablissement",
        "code_postal",
    }
