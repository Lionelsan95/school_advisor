"""Domain invariants for official communes."""

from __future__ import annotations

import pytest

from src.domain.commune import Commune


def _commune(**overrides: object) -> Commune:
    values: dict[str, object] = {
        "code": "92022",
        "name": "Chaville",
        "postal_codes": ("92370",),
        "department_code": "92",
        "latitude": 48.8091,
        "longitude": 2.191,
    }
    values.update(overrides)
    return Commune(**values)  # type: ignore[arg-type]


def test_complete_and_missing_coordinates_are_accepted() -> None:
    assert _commune().latitude == pytest.approx(48.8091)
    assert _commune(latitude=None, longitude=None).longitude is None


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(None, 2.191), (48.8091, None), (90.1, 2.191), (48.8091, 180.1)],
)
def test_partial_or_out_of_range_coordinates_are_rejected(
    latitude: float | None, longitude: float | None
) -> None:
    with pytest.raises(ValueError):
        _commune(latitude=latitude, longitude=longitude)


@pytest.mark.parametrize("field", ["code", "name"])
def test_blank_identity_fields_are_rejected(field: str) -> None:
    with pytest.raises(ValueError):
        _commune(**{field: "  "})
