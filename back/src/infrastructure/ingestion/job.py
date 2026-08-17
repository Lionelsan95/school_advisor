"""Composition root and scheduler for the ingestion job.

Runs inside the backend process — no separate service, no queue. See
docs/02_Architecture_Decisions.md: at annual/weekly source refresh rates and
this data volume, an extra moving part would add operational risk without
buying anything.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import psycopg
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.application.ingest_public_data import IngestionReport, IngestPublicData
from src.infrastructure.persistence.repositories import (
    PostgresCommuneRepository,
    PostgresEstablishmentRepository,
    PostgresIndicatorRepository,
    PostgresSourceReferenceRepository,
)
from src.infrastructure.settings import Settings, get_settings

from .commune_adapter import CommuneAdapter
from .directory_adapter import DirectoryAdapter
from .geo_api_client import GeoApiClient
from .indicator_adapter import IndicatorAdapter
from .locking import ingestion_lock
from .ods_client import OdsClient

logger = logging.getLogger(__name__)


def run_ingestion_once(settings: Settings | None = None) -> IngestionReport | None:
    """Execute one full ingestion run and persist a record of it.

    Returns None when another run already holds the ingestion lock, so this one
    declined. A decline is not an attempt and is deliberately NOT recorded in
    `ingestion_run`: that table answers "did the last run succeed", and filling
    it with skipped runs would bury the answer.

    A failed run *is* recorded, with its reason — a failure that leaves no
    trace is exactly the silent-breakage mode this project must avoid.

    Overlapping runs are refused rather than queued because they corrupt the
    rollback snapshot; see `locking.py` for why that is a correctness problem
    and not merely wasted work.
    """
    settings = settings or get_settings()
    client = OdsClient(base_url=settings.ods_base_url)
    geo_client = GeoApiClient(base_url=settings.geo_api_base_url)
    started_at = datetime.now(UTC)
    try:
        with (
            psycopg.connect(settings.database_url) as connection,
            ingestion_lock(connection) as acquired,
        ):
            if not acquired:
                # WARNING, not CRITICAL: declining is the lock working, not a
                # fault. It is logged because a run silently not happening is
                # its own kind of surprise.
                logger.warning(
                    "Ingestion skipped: another run already holds the lock. "
                    "Overlapping runs are refused because the second one's "
                    "snapshot would capture the first one's freshly loaded "
                    "data, breaking rollback."
                )
                return None

            use_case = IngestPublicData(
                directory_source=DirectoryAdapter(client),
                indicator_source=IndicatorAdapter(client),
                commune_source=CommuneAdapter(geo_client),
                establishment_repository=PostgresEstablishmentRepository(connection),
                indicator_repository=PostgresIndicatorRepository(connection),
                commune_repository=PostgresCommuneRepository(connection),
                source_reference_repository=PostgresSourceReferenceRepository(
                    connection
                ),
            )
            try:
                # One transaction around BOTH writes. The repositories open
                # their own transaction blocks, which nest as savepoints, so
                # this outer block is what actually commits. Without it, a
                # failure while appending indicators would leave the freshly
                # swapped establishment snapshot live while the audit row said
                # the run had failed — the two would disagree about what users
                # are being shown.
                with connection.transaction():
                    report = use_case.run()
                    _record_run(connection, report)
            except Exception as error:
                # The use case already logged CRITICAL. Record the attempt on a
                # fresh connection, because the failing one may be in an
                # aborted transaction, then let the error propagate.
                failed = IngestionReport(
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    succeeded=False,
                    failure_reason=f"{type(error).__name__}: {error}",
                )
                with psycopg.connect(settings.database_url) as audit_connection:
                    _record_run(audit_connection, failed)
                raise
            return report
    finally:
        client.close()
        geo_client.close()


def _record_run(connection: psycopg.Connection, report: IngestionReport) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO ingestion_run (
                started_at, finished_at, succeeded, establishments_loaded,
                indicators_loaded, indicators_seen, communes_loaded, match_rate,
                unmatched_uai_count, failure_reason
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                report.started_at,
                report.finished_at,
                report.succeeded,
                report.establishments_loaded,
                report.indicators_loaded,
                report.indicators_seen,
                report.communes_loaded,
                report.match_rate,
                len(report.unmatched_uais),
                report.failure_reason,
            ),
        )


def start_scheduler(settings: Settings | None = None) -> BackgroundScheduler | None:
    """Start the in-process daily ingestion, if enabled."""
    settings = settings or get_settings()
    if not settings.ingestion_enabled:
        logger.info("Scheduled ingestion is disabled (INGESTION_ENABLED=false)")
        return None

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _scheduled_run,
        trigger=CronTrigger(hour=settings.ingestion_hour_utc, minute=0),
        id="public_data_ingestion",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Scheduled ingestion daily at %02d:00 UTC", settings.ingestion_hour_utc)
    return scheduler


def _scheduled_run() -> None:
    """Wrapper so a failure never kills the scheduler thread silently."""
    try:
        # A None return means another run held the lock; `run_ingestion_once`
        # has already logged that, and there is nothing further to do.
        run_ingestion_once()
    except Exception:
        logger.critical("Scheduled ingestion run failed", exc_info=True)
