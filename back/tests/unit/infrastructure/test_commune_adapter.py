"""Strict validation of the official commune payload."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from src.domain.dataset_ids import DATASET_COMMUNES
from src.infrastructure.ingestion.commune_adapter import (
    COMMUNE_FIELDS,
    CommuneAdapter,
)
from src.infrastructure.ingestion.errors import (
    SourceDataIntegrityError,
    SourceSchemaMismatchError,
)


def commune_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "nom": "L'Île-Rousse",
        "code": "2B134",
        "codesPostaux": ["20220"],
        "codeDepartement": "2B",
        "centre": {"type": "Point", "coordinates": [8.937, 42.634]},
    }
    row.update(overrides)
    return row


class TestSchemaMismatch:
    @pytest.mark.parametrize("missing_field", COMMUNE_FIELDS)
    def test_every_mandatory_missing_field_aborts_the_payload(
        self, missing_field: str
    ) -> None:
        row = commune_row()
        del row[missing_field]

        with pytest.raises(SourceSchemaMismatchError) as excinfo:
            CommuneAdapter.build_communes([row])

        assert excinfo.value.dataset_id == DATASET_COMMUNES
        assert excinfo.value.missing == [missing_field]

    def test_a_non_object_row_is_rejected(self) -> None:
        with pytest.raises(SourceDataIntegrityError, match="not a JSON object"):
            CommuneAdapter.build_communes([commune_row(), None])  # type: ignore[list-item]


class TestIdentityAndPostalCodeIntegrity:
    @pytest.mark.parametrize(
        "overrides",
        [
            {"code": None},
            {"code": "  "},
            {"nom": 123},
            {"codeDepartement": ""},
            {"codesPostaux": None},
            {"codesPostaux": "20220"},
            {"codesPostaux": ["20220", None]},
            {"codesPostaux": ["20220", ""]},
        ],
    )
    def test_invalid_identity_or_postal_values_abort(
        self, overrides: dict[str, Any]
    ) -> None:
        with pytest.raises(SourceDataIntegrityError):
            CommuneAdapter.build_communes([commune_row(**overrides)])

    def test_empty_postal_code_list_is_preserved_as_official_absence(self) -> None:
        commune = CommuneAdapter.build_communes([commune_row(codesPostaux=[])])[0]
        assert commune.postal_codes == ()

    def test_postal_codes_are_trimmed_deduplicated_and_stably_ordered(self) -> None:
        commune = CommuneAdapter.build_communes(
            [commune_row(codesPostaux=[" 20221 ", "20220", "20220"])]
        )[0]
        assert commune.postal_codes == ("20220", "20221")

    def test_duplicate_commune_codes_abort_even_when_case_differs(self) -> None:
        duplicate = deepcopy(commune_row())
        duplicate["code"] = "2b134"

        with pytest.raises(SourceDataIntegrityError, match="Duplicate commune code"):
            CommuneAdapter.build_communes([commune_row(), duplicate])


class TestCentreIntegrity:
    @pytest.mark.parametrize(
        "centre",
        [
            [],
            {},
            {"type": "Polygon", "coordinates": [8.9, 42.6]},
            {"type": "Point"},
            {"type": "Point", "coordinates": [8.9]},
            {"type": "Point", "coordinates": [8.9, 42.6, 1]},
            {"type": "Point", "coordinates": [True, 42.6]},
            {"type": "Point", "coordinates": [8.9, "42.6"]},
            {"type": "Point", "coordinates": [181, 42.6]},
            {"type": "Point", "coordinates": [8.9, 91]},
        ],
    )
    def test_malformed_or_out_of_range_centres_abort(self, centre: Any) -> None:
        with pytest.raises(SourceDataIntegrityError):
            CommuneAdapter.build_communes([commune_row(centre=centre)])

    def test_null_centre_preserves_missing_coordinates(self) -> None:
        commune = CommuneAdapter.build_communes([commune_row(centre=None)])[0]
        assert commune.latitude is None
        assert commune.longitude is None

    def test_geojson_coordinate_order_is_longitude_then_latitude(self) -> None:
        commune = CommuneAdapter.build_communes([commune_row()])[0]
        assert commune.longitude == pytest.approx(8.937)
        assert commune.latitude == pytest.approx(42.634)


def test_adapter_normalizes_codes_but_preserves_the_official_name() -> None:
    commune = CommuneAdapter.build_communes(
        [commune_row(code=" 2b134 ", nom="  L'Île-Rousse  ")]
    )[0]
    assert commune.code == "2B134"
    assert commune.name == "L'Île-Rousse"
