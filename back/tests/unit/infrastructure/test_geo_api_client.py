"""HTTP contract tests for the official commune client."""

from __future__ import annotations

import httpx
import pytest
import respx

from src.infrastructure.ingestion.errors import SourceUnavailableError
from src.infrastructure.ingestion.geo_api_client import (
    DEFAULT_GEO_API_BASE_URL,
    GeoApiClient,
)

COMMUNES_URL = f"{DEFAULT_GEO_API_BASE_URL}/communes"


def test_fetch_requests_the_complete_required_field_set(
    respx_mock: respx.MockRouter,
) -> None:
    route = respx_mock.get(COMMUNES_URL).mock(return_value=httpx.Response(200, json=[]))
    client = GeoApiClient(max_retries=1)

    assert client.fetch_communes() == []
    request = route.calls.last.request
    assert request.url.params["fields"] == (
        "nom,code,codesPostaux,codeDepartement,centre"
    )
    assert request.url.params["format"] == "json"


@pytest.mark.parametrize("payload", [{}, {"communes": []}, None, "[]"])
def test_non_array_payload_is_a_visible_source_failure(
    respx_mock: respx.MockRouter, payload: object
) -> None:
    respx_mock.get(COMMUNES_URL).mock(return_value=httpx.Response(200, json=payload))

    with pytest.raises(SourceUnavailableError, match="Commune source failed"):
        GeoApiClient(max_retries=1).fetch_communes()


def test_http_failure_is_not_converted_to_an_empty_dataset(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.get(COMMUNES_URL).mock(return_value=httpx.Response(503))

    with pytest.raises(SourceUnavailableError, match="failed after 1 attempts"):
        GeoApiClient(max_retries=1).fetch_communes()
