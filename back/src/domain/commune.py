"""Official French commune reference used for deterministic locality lookup."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Commune:
    """A commune and the centre published by the official Geo API.

    Coordinates are optional because the source can publish a commune without
    a centre. They are never reconstructed from establishment locations.
    """

    code: str
    name: str
    postal_codes: tuple[str, ...]
    department_code: str
    latitude: float | None
    longitude: float | None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("A commune code is required")
        if not self.name.strip():
            raise ValueError(f"Commune {self.code} must have a name")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(
                f"Commune {self.code} coordinates must both be present or absent"
            )
        if self.latitude is not None and not -90 <= self.latitude <= 90:
            raise ValueError(f"Commune {self.code} latitude is outside [-90, 90]")
        if self.longitude is not None and not -180 <= self.longitude <= 180:
            raise ValueError(f"Commune {self.code} longitude is outside [-180, 180]")
