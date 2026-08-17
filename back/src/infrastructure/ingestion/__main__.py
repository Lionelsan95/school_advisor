"""Run one ingestion pass from the command line.

    python -m src.infrastructure.ingestion            # ingest now
    python -m src.infrastructure.ingestion --rollback # undo the last load

Exists so ingestion can be triggered and observed without waiting for the
scheduler and without anyone having to compose a Python one-liner. The
scheduled job (see `job.py`) calls the same code path.

Exits non-zero on failure so a cron wrapper or CI step can detect it.
"""

from __future__ import annotations

import argparse
import logging
import sys

import psycopg

from src.infrastructure.persistence.repositories import (
    PostgresCommuneRepository,
    PostgresEstablishmentRepository,
    PostgresSourceReferenceRepository,
)
from src.infrastructure.settings import get_settings

from .job import run_ingestion_once

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.infrastructure.ingestion",
        description="Load the public education datasets into the local database.",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Restore the establishment snapshot taken before the last load.",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    if args.rollback:
        with (
            psycopg.connect(settings.database_url) as connection,
            connection.transaction(),
        ):
            restored = PostgresEstablishmentRepository(connection).restore_previous()
            communes_restored = PostgresCommuneRepository(connection).restore_previous()
            sources_restored = PostgresSourceReferenceRepository(
                connection
            ).restore_previous()
        print(
            "Rolled back to the previous snapshot: "
            f"{restored} establishments and {communes_restored} communes. "
            f"Restored {sources_restored} source references."
        )
        return 0

    try:
        report = run_ingestion_once(settings)
    except Exception:
        # Already logged CRITICAL by the use case; keep the exit code honest.
        logger.critical("Ingestion did not complete. Nothing was published.")
        return 1

    if report is None:
        # Exit 0: declining is the lock doing its job, not a failure. A
        # non-zero code here would make a cron wrapper alert on correct
        # behaviour.
        print(
            "Ingestion skipped: another run is already in progress. "
            "Nothing was changed."
        )
        return 0

    print(
        f"Ingestion succeeded in {report.duration_seconds:.1f}s — "
        f"{report.establishments_loaded} establishments, "
        f"{report.communes_loaded} communes, "
        f"{report.indicators_loaded} new indicator rows "
        f"({report.indicators_seen} seen), "
        f"match rate {report.match_rate:.2%}, "
        f"{len(report.unmatched_uais)} unmatched UAI(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
