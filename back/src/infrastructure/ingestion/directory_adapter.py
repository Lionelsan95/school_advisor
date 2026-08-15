"""DATA-3 — adapter reading the national education directory.

Grouping rule (decided 2026-08-15, docs/04_Journal_Decisions.md): the source
publishes one row per *site*, and 74 UAIs have several. Rows are grouped by
UAI into one `Establishment` carrying every site, so no location is dropped.

`site.sequence` is assigned by sorting the group on stable source fields, so
that repeated ingestion runs produce the same ordering — and therefore the
same canonical site — for unchanged input.
"""

from __future__ import annotations

import logging
from typing import Any

from src.domain.enums import establishment_type_from_source, sector_from_source
from src.domain.establishment import Establishment, Site
from src.domain.uai import InvalidUaiError, parse_uai

from .ods_client import DATASET_DIRECTORY, OdsClient

logger = logging.getLogger(__name__)

# Exactly the fields this adapter reads. Any of them disappearing upstream
# aborts ingestion via assert_schema rather than silently becoming null.
DIRECTORY_FIELDS = [
    "identifiant_de_l_etablissement",
    "nom_etablissement",
    "type_etablissement",
    "statut_public_prive",
    "adresse_1",
    "code_postal",
    "nom_commune",
    "code_commune",
    "code_departement",
    "latitude",
    "longitude",
    "etat",
    "date_maj_ligne",
]

_OPEN_STATE = "OUVERT"


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    """Deterministic ordering within a UAI group.

    Uses only fields the source always provides in some form; the fallbacks
    keep the sort total even when a field is null.
    """
    return (
        (row.get("nom_etablissement") or ""),
        (row.get("code_postal") or ""),
        (row.get("adresse_1") or ""),
    )


class DirectoryAdapter:
    """Implements the `DirectorySource` port."""

    def __init__(self, client: OdsClient) -> None:
        self._client = client

    def fetch_establishments(self) -> list[Establishment]:
        self._client.assert_schema(DATASET_DIRECTORY, DIRECTORY_FIELDS)
        rows = self._client.export_all(DATASET_DIRECTORY, DIRECTORY_FIELDS)
        return self.build_establishments(rows)

    @staticmethod
    def build_establishments(rows: list[dict[str, Any]]) -> list[Establishment]:
        """Pure transformation — unit-testable without any network."""
        grouped: dict[str, list[dict[str, Any]]] = {}
        rejected = 0
        for row in rows:
            try:
                uai = parse_uai(row.get("identifiant_de_l_etablissement"))
            except InvalidUaiError:
                # Surfaced, never silently dropped.
                rejected += 1
                logger.warning(
                    "Skipping directory row with invalid UAI: %r",
                    row.get("identifiant_de_l_etablissement"),
                )
                continue
            grouped.setdefault(uai, []).append(row)

        if rejected:
            logger.warning("%d directory row(s) rejected for an invalid UAI", rejected)

        establishments: list[Establishment] = []
        for uai, group in grouped.items():
            ordered = sorted(group, key=_sort_key)
            sites = tuple(
                Site(
                    sequence=index,
                    name=(row.get("nom_etablissement") or "").strip() or uai,
                    address=row.get("adresse_1"),
                    postal_code=row.get("code_postal"),
                    city=row.get("nom_commune"),
                    city_code=row.get("code_commune"),
                    latitude=_as_float(row.get("latitude")),
                    longitude=_as_float(row.get("longitude")),
                )
                for index, row in enumerate(ordered)
            )
            primary = ordered[0]
            establishments.append(
                Establishment(
                    uai=uai,
                    name=sites[0].name,
                    type=establishment_type_from_source(
                        primary.get("type_etablissement")
                    ),
                    sector=sector_from_source(primary.get("statut_public_prive")),
                    department_code=primary.get("code_departement"),
                    is_open=primary.get("etat") == _OPEN_STATE,
                    sites=sites,
                    source_updated_at=primary.get("date_maj_ligne"),
                )
            )

        multi_site = sum(1 for e in establishments if e.is_multi_site)
        logger.info(
            "Built %d establishments from %d directory rows (%d multi-site)",
            len(establishments),
            len(rows),
            multi_site,
        )
        return establishments
