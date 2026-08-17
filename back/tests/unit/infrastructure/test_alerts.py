"""OPS-3 — `send_ingestion_failure_alert`, the safe-degradation contract.

Per the module docstring: notification is best-effort and strictly secondary
to the failure it reports. A dead webhook must never become the error a
reader sees instead of the ingestion failure that prompted it — so the
central promise under test here is that this function returns `False` and
never raises, no matter how the webhook misbehaves.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from src.infrastructure.ingestion.alerts import (
    ALERT_TIMEOUT_SECONDS,
    send_ingestion_failure_alert,
)

WEBHOOK_URL = "https://hooks.example.invalid/ingestion-alerts"
STARTED_AT = "2026-08-17T03:00:00+00:00"


def test_a_successful_post_returns_true_and_carries_reason_and_started_at(
    respx_mock: respx.MockRouter,
) -> None:
    route = respx_mock.post(WEBHOOK_URL).mock(return_value=httpx.Response(200))

    delivered = send_ingestion_failure_alert(
        WEBHOOK_URL,
        reason="SourceUnavailableError: directory API returned 503",
        started_at=STARTED_AT,
    )

    assert delivered is True
    sent = json.loads(route.calls.last.request.content)
    assert sent["reason"] == "SourceUnavailableError: directory API returned 503"
    assert sent["started_at"] == STARTED_AT


def test_no_webhook_configured_makes_no_http_call_and_returns_false(
    respx_mock: respx.MockRouter,
) -> None:
    delivered = send_ingestion_failure_alert(
        None, reason="whatever failed", started_at=STARTED_AT
    )

    assert delivered is False
    assert respx_mock.calls.call_count == 0


def test_a_500_response_returns_false_without_raising(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.post(WEBHOOK_URL).mock(return_value=httpx.Response(500))

    delivered = send_ingestion_failure_alert(
        WEBHOOK_URL, reason="boom", started_at=STARTED_AT
    )

    assert delivered is False


def test_a_connection_error_returns_false_without_raising(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.post(WEBHOOK_URL).mock(side_effect=httpx.ConnectError("refused"))

    delivered = send_ingestion_failure_alert(
        WEBHOOK_URL, reason="boom", started_at=STARTED_AT
    )

    assert delivered is False


def test_a_timeout_returns_false_without_raising(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.post(WEBHOOK_URL).mock(side_effect=httpx.TimeoutException("timed out"))

    delivered = send_ingestion_failure_alert(
        WEBHOOK_URL, reason="boom", started_at=STARTED_AT
    )

    assert delivered is False


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("connection refused"),
        httpx.TimeoutException("timed out"),
        httpx.ReadTimeout("read timed out"),
        httpx.RemoteProtocolError("server disconnected"),
    ],
    ids=["connect-error", "timeout", "read-timeout", "protocol-error"],
)
def test_it_never_raises_regardless_of_how_the_webhook_fails(
    respx_mock: respx.MockRouter, failure: Exception
) -> None:
    """The module's central promise, proven directly rather than implied by
    the tests above: nothing here should ever need a `pytest.raises`."""
    respx_mock.post(WEBHOOK_URL).mock(side_effect=failure)

    delivered = send_ingestion_failure_alert(
        WEBHOOK_URL, reason="boom", started_at=STARTED_AT
    )

    assert delivered is False


def test_the_timeout_is_short_so_a_slow_endpoint_cannot_delay_the_report() -> None:
    assert ALERT_TIMEOUT_SECONDS <= 10.0
