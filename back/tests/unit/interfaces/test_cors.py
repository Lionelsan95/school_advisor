"""CORS-1 — the frontend is cross-origin from the API, so this must hold.

Without these headers the browser refuses every call and the frontend cannot
function at all. It is worth testing because the failure is invisible from the
server side: the API answers normally, and only the browser console shows why
nothing works.

The client is built without entering `TestClient` as a context manager, so the
lifespan never runs and no database is needed. Preflight is answered by the
middleware before routing, and `/health` touches no connection.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.settings import get_cors_origins
from src.interfaces.api.main import app

ALLOWED_ORIGIN = "http://localhost:5173"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_preflight_from_the_configured_origin_is_accepted(client: TestClient) -> None:
    response = client.options(
        "/establishments/search",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_simple_request_from_the_configured_origin_carries_the_header(
    client: TestClient,
) -> None:
    response = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_an_unlisted_origin_is_not_granted_access(client: TestClient) -> None:
    """A permissive default would defeat the point of configuring origins."""
    response = client.get(
        "/health", headers={"Origin": "https://not-our-frontend.invalid"}
    )

    assert "access-control-allow-origin" not in response.headers


def test_credentials_are_not_allowed(client: TestClient) -> None:
    """Read-only public data with no auth or cookies.

    Allowing credentials would widen the surface for no benefit, and it is what
    would make a future wildcard origin genuinely dangerous.
    """
    response = client.options(
        "/establishments/search",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-credentials" not in response.headers


class TestOriginParsing:
    """The setting is a comma-separated string; the middleware needs a list."""

    def test_multiple_origins_are_split_and_trimmed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            "CORS_ALLOWED_ORIGINS", "http://localhost:5173, https://example.test "
        )

        assert get_cors_origins() == ["http://localhost:5173", "https://example.test"]

    def test_a_trailing_comma_does_not_produce_an_empty_origin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,")

        assert get_cors_origins() == ["http://localhost:5173"]

    def test_importing_the_app_does_not_require_a_database_to_be_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: resolving CORS through `Settings` made `main` unimportable
        without DATABASE_URL, because that field is deliberately required."""
        monkeypatch.delenv("DATABASE_URL", raising=False)

        assert get_cors_origins()
