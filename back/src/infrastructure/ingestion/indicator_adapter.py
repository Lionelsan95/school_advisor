"""DATA-4 — adapter reading the IVAC and IVAL result indicators.

The three datasets publish the same concepts under different column names, so
each gets an explicit field mapping rather than clever guessing. Two source
quirks are handled here, both established by the Phase 0 spike:

- the year lives in `session` (IVAC) or `annee` (IVAL) and is an ISO date
  string, not an integer;
- a null value-added figure is stored as null with **no reason attached**. The
  source publishes no reason field at all, and the documented candidate
  threshold does not predict the nulls. Nothing here may infer one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.domain.enums import IndicatorType, sector_from_source
from src.domain.indicator_result import IndicatorResult
from src.domain.source_reference import SourceReference
from src.domain.uai import InvalidUaiError, parse_uai

from .ods_client import (
    DATASET_IVAC,
    DATASET_IVAL_GT,
    DATASET_IVAL_PRO,
    OdsClient,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IndicatorDatasetSpec:
    """How one source dataset maps onto `IndicatorResult`."""

    dataset_id: str
    indicator_type: IndicatorType
    year_field: str
    candidates_field: str
    success_rate_field: str
    value_added_success_field: str
    access_rate_field: str | None = None
    value_added_access_field: str | None = None
    mention_rate_field: str | None = None
    value_added_mention_field: str | None = None

    @property
    def fields(self) -> list[str]:
        names = [
            "uai",
            "secteur",
            self.year_field,
            self.candidates_field,
            self.success_rate_field,
            self.value_added_success_field,
        ]
        optional = (
            self.access_rate_field,
            self.value_added_access_field,
            self.mention_rate_field,
            self.value_added_mention_field,
        )
        names.extend(name for name in optional if name)
        # Preserve order while removing duplicates.
        return list(dict.fromkeys(names))


IVAC_SPEC = IndicatorDatasetSpec(
    dataset_id=DATASET_IVAC,
    indicator_type=IndicatorType.IVAC,
    year_field="session",
    candidates_field="nb_candidats_g",
    success_rate_field="taux_de_reussite_g",
    value_added_success_field="va_du_taux_de_reussite_g",
    access_rate_field="taux_d_acces_6eme_3eme",
)

IVAL_GT_SPEC = IndicatorDatasetSpec(
    dataset_id=DATASET_IVAL_GT,
    indicator_type=IndicatorType.IVAL_GT,
    year_field="annee",
    candidates_field="presents_total",
    success_rate_field="taux_reu_total",
    value_added_success_field="va_reu_total",
    access_rate_field="taux_acces_2nde",
    value_added_access_field="va_acces_2nde",
    mention_rate_field="taux_men_total",
    value_added_mention_field="va_men_total",
)

IVAL_PRO_SPEC = IndicatorDatasetSpec(
    dataset_id=DATASET_IVAL_PRO,
    indicator_type=IndicatorType.IVAL_PRO,
    year_field="annee",
    candidates_field="presents_total",
    success_rate_field="taux_reu_total",
    value_added_success_field="va_reu_total",
    access_rate_field="taux_acces_2nde",
    value_added_access_field="va_acces_2nde",
    mention_rate_field="taux_men_total",
    value_added_mention_field="va_men_total",
)

ALL_SPECS = (IVAC_SPEC, IVAL_GT_SPEC, IVAL_PRO_SPEC)


def parse_year(value: Any) -> int | None:
    """`session` / `annee` are ISO date strings in the current datasets.

    The legacy IVAL datasets used plain integers, so both are accepted — but
    anything else is rejected rather than coerced.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _as_float(value: Any) -> float | None:
    """Legacy datasets type several numeric columns as text (`"-5"`)."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    return int(number) if number is not None else None


def _optional(row: dict[str, Any], field: str | None) -> float | None:
    """Read a field that only some of the three datasets publish.

    IVAC has no mention rate or access value-added, so its spec leaves those
    field names as None and the corresponding value stays absent.
    """
    return _as_float(row.get(field)) if field else None


class IndicatorAdapter:
    """Implements the `IndicatorSource` port across all three datasets."""

    def __init__(
        self, client: OdsClient, specs: tuple[IndicatorDatasetSpec, ...] = ALL_SPECS
    ):
        self._client = client
        self._specs = specs

    def fetch_indicators(self) -> list[IndicatorResult]:
        results: list[IndicatorResult] = []
        for spec in self._specs:
            self._client.assert_schema(spec.dataset_id, spec.fields)
            rows = self._client.export_all(spec.dataset_id, spec.fields)
            results.extend(self.build_results(spec, rows))
        return results

    def source_references(self) -> list[SourceReference]:
        return [
            SourceReference(
                dataset_id=spec.dataset_id,
                url=self._client.dataset_page_url(spec.dataset_id),
                last_synchronised_at=datetime.now(UTC),
                source_published_at=self._client.data_published_at(spec.dataset_id),
            )
            for spec in self._specs
        ]

    @staticmethod
    def build_results(
        spec: IndicatorDatasetSpec, rows: list[dict[str, Any]]
    ) -> list[IndicatorResult]:
        """Pure transformation — unit-testable without any network."""
        results: list[IndicatorResult] = []
        skipped = 0
        for row in rows:
            try:
                uai = parse_uai(row.get("uai"))
            except InvalidUaiError:
                skipped += 1
                continue
            year = parse_year(row.get(spec.year_field))
            if year is None:
                skipped += 1
                logger.warning(
                    "Skipping %s row for %s: unparseable year %r",
                    spec.dataset_id,
                    uai,
                    row.get(spec.year_field),
                )
                continue

            results.append(
                IndicatorResult(
                    uai=uai,
                    year=year,
                    indicator_type=spec.indicator_type,
                    sector=sector_from_source(row.get("secteur")),
                    candidates_present=_as_int(row.get(spec.candidates_field)),
                    success_rate=_as_float(row.get(spec.success_rate_field)),
                    # Null stays null. No reason is inferred, ever.
                    value_added_success=_as_float(
                        row.get(spec.value_added_success_field)
                    ),
                    access_rate=_optional(row, spec.access_rate_field),
                    value_added_access=_optional(row, spec.value_added_access_field),
                    mention_rate=_optional(row, spec.mention_rate_field),
                    value_added_mention=_optional(row, spec.value_added_mention_field),
                )
            )

        if skipped:
            logger.warning(
                "%d row(s) from %s skipped (invalid UAI or year)",
                skipped,
                spec.dataset_id,
            )
        logger.info("Built %d results from %s", len(results), spec.dataset_id)
        return results
