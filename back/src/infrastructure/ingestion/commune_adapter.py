"""Adapter for the official French commune reference."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.domain.commune import Commune
from src.domain.dataset_ids import DATASET_COMMUNES
from src.domain.source_reference import SourceReference

from .errors import SourceDataIntegrityError, SourceSchemaMismatchError
from .geo_api_client import GeoApiClient

COMMUNE_FIELDS = ("nom", "code", "codesPostaux", "codeDepartement", "centre")


class CommuneAdapter:
    """Validates the complete payload before returning any domain objects."""

    def __init__(self, client: GeoApiClient) -> None:
        self._client = client

    def fetch_communes(self) -> list[Commune]:
        rows = self._client.fetch_communes()
        return self.build_communes(rows)

    def source_references(self) -> list[SourceReference]:
        return [
            SourceReference(
                dataset_id=DATASET_COMMUNES,
                url=self._client.source_page_url,
                last_synchronised_at=datetime.now(UTC),
                source_published_at=None,
            )
        ]

    @staticmethod
    def build_communes(rows: list[dict[str, Any]]) -> list[Commune]:
        communes: list[Commune] = []
        seen_codes: set[str] = set()
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise SourceDataIntegrityError(
                    f"Commune row {index} is not a JSON object"
                )
            missing = [field for field in COMMUNE_FIELDS if field not in row]
            if missing:
                raise SourceSchemaMismatchError(
                    DATASET_COMMUNES, missing, sorted(row.keys())
                )

            raw_code = row["code"]
            name = row["nom"]
            department_code = row["codeDepartement"]
            postal_codes = row["codesPostaux"]
            identity_values = (raw_code, name, department_code)
            if not all(
                isinstance(value, str) and value.strip() for value in identity_values
            ):
                raise SourceDataIntegrityError(
                    f"Commune row {index} has an invalid code, name or department"
                )
            code = raw_code.strip().upper()
            if code in seen_codes:
                raise SourceDataIntegrityError(f"Duplicate commune code {code}")
            if not isinstance(postal_codes, list) or not all(
                isinstance(value, str) and value.strip() for value in postal_codes
            ):
                raise SourceDataIntegrityError(
                    f"Commune {code} has invalid postal codes"
                )
            normalized_postal_codes = tuple(
                sorted({postal_code.strip() for postal_code in postal_codes})
            )

            latitude: float | None = None
            longitude: float | None = None
            centre = row["centre"]
            if centre is not None:
                if not isinstance(centre, dict) or centre.get("type") != "Point":
                    raise SourceDataIntegrityError(
                        f"Commune {code} has an invalid centre geometry"
                    )
                coordinates = centre.get("coordinates")
                if (
                    not isinstance(coordinates, list)
                    or len(coordinates) != 2
                    or isinstance(coordinates[0], bool)
                    or isinstance(coordinates[1], bool)
                    or not isinstance(coordinates[0], (int, float))
                    or not isinstance(coordinates[1], (int, float))
                ):
                    raise SourceDataIntegrityError(
                        f"Commune {code} has invalid centre coordinates"
                    )
                longitude = float(coordinates[0])
                latitude = float(coordinates[1])

            try:
                commune = Commune(
                    code=code,
                    name=name.strip(),
                    postal_codes=normalized_postal_codes,
                    department_code=department_code.strip(),
                    latitude=latitude,
                    longitude=longitude,
                )
            except ValueError as error:
                raise SourceDataIntegrityError(str(error)) from error
            communes.append(commune)
            seen_codes.add(commune.code)
        return communes
