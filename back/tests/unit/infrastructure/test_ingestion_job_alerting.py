"""OPS-3 — `run_ingestion_once`'s failure-handling path.

This proves the exit criterion from docs/06_Implementation_Roadmap.md Phase
6: "a deliberate ingestion failure (bad network, malformed source data) is
caught and alerted, not silently ignored." Before this ticket, the only
channel for that was a CRITICAL log line in a file nobody watches — see
docs/02_Architecture_Decisions.md, "Risques / angles morts".

`run_ingestion_once` talks to Postgres and constructs real adapters directly,
so every I/O boundary is patched here to keep this a unit test (no database,
no network) while exercising the real orchestration: the lock, the outer
transaction, the `ingestion_run` audit write, and the alert call. Only the
webhook HTTP call itself is intercepted, with respx — everything from
`IngestPublicData.run()` down through `send_ingestion_failure_alert` is the
real, unmodified code under test.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import respx

from src.infrastructure.ingestion import job as job_module
from src.infrastructure.ingestion.errors import SourceUnavailableError
from src.infrastructure.ingestion.job import run_ingestion_once
from src.infrastructure.settings import Settings
from tests.unit.application.test_ingest_public_data import (
    FakeCommuneRepository,
    FakeCommuneSource,
    FakeDirectorySource,
    FakeEstablishmentRepository,
    FakeIndicatorRepository,
    FakeIndicatorSource,
    FakeSourceReferenceRepository,
)

WEBHOOK_URL = "https://hooks.example.invalid/ingestion-alerts"


class RaisingDirectorySource:
    """Stands in for a broken upstream — "bad network" from the exit
    criterion — by failing on the very first fetch, exactly like the real
    `DirectoryAdapter` would after `OdsClient` exhausts its retries."""

    def fetch_establishments(self) -> list[Any]:
        raise SourceUnavailableError(
            "Directory API returned 503 Service Unavailable after 3 attempts"
        )

    def source_references(self) -> list[Any]:
        return []


@contextmanager
def _fake_ingestion_lock(connection: Any) -> Iterator[bool]:
    yield True


class _FakeCursor:
    def __init__(self, log: list[tuple[str, tuple[Any, ...] | None]]) -> None:
        self._log = log

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        self._log.append((sql, params))

    def fetchone(self) -> None:
        return None


class _FakeTransaction:
    def __enter__(self) -> _FakeTransaction:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        return None


class FakeConnection:
    """Stands in for `psycopg.Connection` — records every statement executed
    on it so `_record_run`'s write can be inspected without a database."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self.executed)

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction()

    def close(self) -> None:
        pass


class _NoopHttpClient:
    """Stands in for `OdsClient`/`GeoApiClient`: never used because the
    adapters that would call it are replaced wholesale below."""

    def close(self) -> None:
        pass


@pytest.fixture
def job_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[FakeConnection], dict[str, Any]]:
    """Patches every I/O boundary `run_ingestion_once` touches, so the real
    orchestration in `job.py` runs against fakes instead of a database.

    Returns the list of `FakeConnection`s opened (main run connection first,
    then the audit connection on a failure path) and a mutable `state` dict
    the test fills in with the directory/indicator/commune sources it wants
    `IngestPublicData` to see.
    """
    connections: list[FakeConnection] = []

    def fake_connect(dsn: str) -> FakeConnection:
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(job_module.psycopg, "connect", fake_connect)
    monkeypatch.setattr(job_module, "ingestion_lock", _fake_ingestion_lock)
    monkeypatch.setattr(job_module, "OdsClient", lambda base_url: _NoopHttpClient())
    monkeypatch.setattr(job_module, "GeoApiClient", lambda base_url: _NoopHttpClient())

    state: dict[str, Any] = {
        "directory_source": None,
        "indicator_source": None,
        "commune_source": None,
    }
    monkeypatch.setattr(
        job_module, "DirectoryAdapter", lambda client: state["directory_source"]
    )
    monkeypatch.setattr(
        job_module, "IndicatorAdapter", lambda client: state["indicator_source"]
    )
    monkeypatch.setattr(
        job_module, "CommuneAdapter", lambda client: state["commune_source"]
    )
    monkeypatch.setattr(
        job_module,
        "PostgresEstablishmentRepository",
        lambda connection: FakeEstablishmentRepository(),
    )
    monkeypatch.setattr(
        job_module,
        "PostgresIndicatorRepository",
        lambda connection: FakeIndicatorRepository(),
    )
    monkeypatch.setattr(
        job_module,
        "PostgresCommuneRepository",
        lambda connection: FakeCommuneRepository(),
    )
    monkeypatch.setattr(
        job_module,
        "PostgresSourceReferenceRepository",
        lambda connection: FakeSourceReferenceRepository(),
    )
    return connections, state


def _settings(webhook_url: str | None = WEBHOOK_URL) -> Settings:
    return Settings(
        database_url="postgresql://unit-test/fake", alert_webhook_url=webhook_url
    )


def _insert_ingestion_run_calls(
    connection: FakeConnection,
) -> list[tuple[str, tuple[Any, ...] | None]]:
    return [
        (sql, params)
        for sql, params in connection.executed
        if "INSERT INTO ingestion_run" in sql
    ]


class TestDeliberateIngestionFailureIsCaughtAndAlerted:
    """THE KEY TEST — proves the Phase 6 exit criterion directly: a
    deliberate ingestion failure is (1) logged at CRITICAL, (2) alerted with
    its failure reason, and (3) still propagates to the caller rather than
    being swallowed by the alerting path."""

    def test_failure_is_logged_critical_alerted_and_still_raised(
        self,
        job_harness: tuple[list[FakeConnection], dict[str, Any]],
        respx_mock: respx.MockRouter,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        _connections, state = job_harness
        state["directory_source"] = RaisingDirectorySource()
        route = respx_mock.post(WEBHOOK_URL).mock(return_value=httpx.Response(200))

        with (
            caplog.at_level(logging.INFO),
            pytest.raises(SourceUnavailableError, match="503"),
        ):
            run_ingestion_once(_settings())

        # 1. Logged at CRITICAL — this was the only channel before OPS-3.
        critical_messages = [
            record.getMessage()
            for record in caplog.records
            if record.levelname == "CRITICAL"
        ]
        assert any("INGESTION FAILED" in message for message in critical_messages)

        # 2. An alert was attempted, carrying the failure reason.
        assert route.calls.call_count == 1
        sent = json.loads(route.calls.last.request.content)
        assert "SourceUnavailableError" in sent["reason"]
        assert "503" in sent["reason"]

        # 3. The *original* exception reaches the caller — proven by
        # `pytest.raises(SourceUnavailableError, ...)` above, not some
        # different error the alerting path might otherwise introduce.


class TestWebhookFailureDoesNotMaskTheIngestionFailure:
    def test_dead_webhook_does_not_change_the_outcome(
        self,
        job_harness: tuple[list[FakeConnection], dict[str, Any]],
        respx_mock: respx.MockRouter,
    ) -> None:
        _connections, state = job_harness
        state["directory_source"] = RaisingDirectorySource()
        respx_mock.post(WEBHOOK_URL).mock(side_effect=httpx.ConnectError("refused"))

        with pytest.raises(SourceUnavailableError, match="503"):
            run_ingestion_once(_settings())

        # Same exception type still propagates (asserted above) even though
        # the webhook itself is unreachable — and the failure is still
        # recorded. The audit connection is the last one opened: the main
        # run connection first, then a fresh one for the failure record (the
        # first may be in an aborted transaction).
        connections, _state = job_harness
        audit_connection = connections[-1]
        insert_calls = _insert_ingestion_run_calls(audit_connection)
        assert len(insert_calls) == 1
        _sql, params = insert_calls[0]
        assert params is not None
        succeeded, failure_reason = params[2], params[-1]
        assert succeeded is False
        assert "SourceUnavailableError" in failure_reason


class TestSuccessfulRunSendsNoAlert:
    def test_no_alert_is_sent_when_the_run_succeeds(
        self,
        job_harness: tuple[list[FakeConnection], dict[str, Any]],
        respx_mock: respx.MockRouter,
    ) -> None:
        _connections, state = job_harness
        # The real quality gates (docs/05_Resultats_Spike_Technique.md
        # thresholds) require real volume — 50k/60k/30k rows. Cheap
        # UAI-only stand-ins are enough: `IngestPublicData` only reads
        # `.uai`, and the fake repositories only read `len()`.
        establishments = [SimpleNamespace(uai=f"{i:08d}A") for i in range(50_000)]
        indicators = [
            SimpleNamespace(uai=establishments[i % 50_000].uai) for i in range(60_000)
        ]
        communes = [object() for _ in range(30_000)]

        state["directory_source"] = FakeDirectorySource(establishments)
        state["indicator_source"] = FakeIndicatorSource(indicators)
        state["commune_source"] = FakeCommuneSource(communes)
        # No route registered: any HTTP attempt at all is a defect here.

        report = run_ingestion_once(_settings())

        assert report is not None
        assert report.succeeded is True
        assert respx_mock.calls.call_count == 0
