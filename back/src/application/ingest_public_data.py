"""DATA-5 — the ingestion use case, with its quality gates.

docs/02_Architecture_Decisions.md calls silent ingestion failure the project's
most critical blind spot. A schema check alone is not enough: the source can
stay perfectly well-shaped and still deliver something wrong (a collapsed
export, a directory that lost a region). So this use case refuses to publish a
run that does not look like what the Phase 0 spike measured.

Reference values, all measured on 2026-08-15 and recorded in
docs/05_Resultats_Spike_Technique.md:
  - 67 896 directory rows -> 67 816 distinct UAIs (74 are multi-site)
  - 87 612 indicator rows across all published years
  - 98.80% of *latest-year* indicator rows resolve to a directory entry;
    97.53% when every year is counted, because older years reference
    establishments that have since closed and left the directory
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.application.errors import SuspiciousIngestionError
from src.application.ports import (
    DirectorySource,
    EstablishmentRepository,
    IndicatorRepository,
    IndicatorSource,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QualityGates:
    """Thresholds below which a run is refused rather than published.

    Set well under the observed values so normal source drift does not trip
    them, but high enough that a genuinely broken export cannot pass.
    """

    min_establishments: int = 50_000
    min_indicators: int = 60_000
    # Observed 97.53% across all published years on 2026-08-15. Note this is
    # NOT the spike's 98.80%, which covered the latest year only: older years
    # reference establishments that have since closed and left the directory,
    # so an all-years rate is structurally lower. Do not compare the two
    # figures directly. A fall to 95% means something changed upstream and a
    # human needs to look before this data reaches users.
    min_match_rate: float = 0.95


@dataclass
class IngestionReport:
    started_at: datetime
    finished_at: datetime | None = None
    establishments_loaded: int = 0
    indicators_loaded: int = 0
    indicators_seen: int = 0
    unmatched_uais: list[str] = field(default_factory=list)
    match_rate: float = 0.0
    succeeded: bool = False
    failure_reason: str | None = None

    @property
    def duration_seconds(self) -> float:
        end = self.finished_at or datetime.now(UTC)
        return (end - self.started_at).total_seconds()


class IngestPublicData:
    """Orchestrates a full refresh from the public datasets."""

    def __init__(
        self,
        directory_source: DirectorySource,
        indicator_source: IndicatorSource,
        establishment_repository: EstablishmentRepository,
        indicator_repository: IndicatorRepository,
        gates: QualityGates | None = None,
    ) -> None:
        self._directory = directory_source
        self._indicators = indicator_source
        self._establishments_repo = establishment_repository
        self._indicators_repo = indicator_repository
        self._gates = gates or QualityGates()

    def run(self) -> IngestionReport:
        report = IngestionReport(started_at=datetime.now(UTC))
        try:
            report = self._run(report)
        except Exception as error:
            report.finished_at = datetime.now(UTC)
            report.succeeded = False
            report.failure_reason = f"{type(error).__name__}: {error}"
            # CRITICAL, not WARNING: this is the alert channel until OPS-3
            # wires a real notification target.
            logger.critical("INGESTION FAILED — %s", report.failure_reason)
            raise
        return report

    def _run(self, report: IngestionReport) -> IngestionReport:
        establishments = self._directory.fetch_establishments()
        if len(establishments) < self._gates.min_establishments:
            raise SuspiciousIngestionError(
                f"Directory returned only {len(establishments)} establishments, "
                f"below the minimum of {self._gates.min_establishments}. "
                f"Refusing to replace the current data."
            )

        indicators = self._indicators.fetch_indicators()
        if len(indicators) < self._gates.min_indicators:
            raise SuspiciousIngestionError(
                f"Indicator sources returned only {len(indicators)} rows, below "
                f"the minimum of {self._gates.min_indicators}. "
                f"Refusing to append this run."
            )

        # The join match rate is itself a health signal: the spike traced the
        # 1.2% of unmatched rows to a directory coverage gap in two
        # departements, so a sharp drop means the directory lost more ground.
        known = {establishment.uai for establishment in establishments}
        unmatched = sorted({r.uai for r in indicators if r.uai not in known})
        matched_rows = sum(1 for r in indicators if r.uai in known)
        report.indicators_seen = len(indicators)
        report.match_rate = matched_rows / len(indicators) if indicators else 0.0
        report.unmatched_uais = unmatched

        if report.match_rate < self._gates.min_match_rate:
            raise SuspiciousIngestionError(
                f"Only {report.match_rate:.2%} of indicator rows resolve to a "
                f"directory entry, below the {self._gates.min_match_rate:.0%} "
                f"floor (98.80% measured during the Phase 0 spike). "
                f"{len(unmatched)} UAI(s) unmatched."
            )

        # Unmatched establishments are logged, never dropped silently.
        if unmatched:
            logger.warning(
                "%d indicator UAI(s) have no directory entry; match rate %.2f%%. "
                "First 20: %s",
                len(unmatched),
                report.match_rate * 100,
                unmatched[:20],
            )

        report.establishments_loaded = self._establishments_repo.replace_all(
            establishments
        )
        report.indicators_loaded = self._indicators_repo.append(indicators)
        report.finished_at = datetime.now(UTC)
        report.succeeded = True

        logger.info(
            "Ingestion complete in %.1fs — %d establishments, %d new indicator rows "
            "(%d seen), match rate %.2f%%",
            report.duration_seconds,
            report.establishments_loaded,
            report.indicators_loaded,
            report.indicators_seen,
            report.match_rate * 100,
        )
        return report
