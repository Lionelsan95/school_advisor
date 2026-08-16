"""Shared test data builders for the ingestion/domain unit tests.

Not a test module itself (no `test_` functions), so pytest does not collect
it — it is imported by the test modules under `tests/unit/`.

Kept deliberately dumb: every field a caller doesn't override gets a
plausible, always-valid default, so each test only has to spell out the
field it is actually asserting about.
"""

from __future__ import annotations

from typing import Any

from src.domain.enums import EstablishmentType, IndicatorType, Sector
from src.domain.establishment import Establishment, Site
from src.domain.indicator_result import IndicatorResult


def make_site(sequence: int = 0, name: str = "Test school", **overrides: Any) -> Site:
    fields: dict[str, Any] = dict(
        sequence=sequence,
        name=name,
        address="1 rue de Test",
        postal_code="75000",
        city="Paris",
        city_code="75100",
        latitude=48.85,
        longitude=2.35,
    )
    fields.update(overrides)
    return Site(**fields)


def make_establishment(
    uai: str = "0750001A",
    sites: tuple[Site, ...] | None = None,
    **overrides: Any,
) -> Establishment:
    fields: dict[str, Any] = dict(
        uai=uai,
        name="Test school",
        type=EstablishmentType.COLLEGE,
        sector=Sector.PUBLIC,
        department_code="75",
        is_open=True,
        sites=sites or (make_site(),),
        source_updated_at="2025-01-01T00:00:00+00:00",
    )
    fields.update(overrides)
    return Establishment(**fields)


def make_indicator_result(
    uai: str = "0750001A",
    year: int = 2025,
    indicator_type: IndicatorType = IndicatorType.IVAC,
    **overrides: Any,
) -> IndicatorResult:
    fields: dict[str, Any] = dict(uai=uai, year=year, indicator_type=indicator_type)
    fields.update(overrides)
    return IndicatorResult(**fields)


# The offer-descriptor flags the directory publishes (Phase 2, ticket API-2).
# `voie_*`, `section_*` and `segpa` arrive as the strings "0"/"1"; `ulis`
# arrives as the integer 0/1 — see `flag_is_set`. Defaulted to "not set" so a
# caller only has to override the flag(s) a given test is actually about.
_OFFER_FLAG_DEFAULTS: dict[str, Any] = {
    "voie_generale": "0",
    "voie_technologique": "0",
    "voie_professionnelle": "0",
    "section_europeenne": "0",
    "section_internationale": "0",
    "section_sport": "0",
    "section_arts": "0",
    "section_cinema": "0",
    "section_theatre": "0",
    "ulis": 0,
    "segpa": "0",
}


def directory_row(uai: str = "0750001A", **overrides: Any) -> dict[str, Any]:
    """A source directory row exactly as `DIRECTORY_FIELDS` expects it."""
    row: dict[str, Any] = {
        "identifiant_de_l_etablissement": uai,
        "nom_etablissement": "Test school",
        "type_etablissement": "collège",
        "statut_public_prive": "public",
        "adresse_1": "1 rue de Test",
        "code_postal": "75000",
        "nom_commune": "Paris",
        "code_commune": "75100",
        "code_departement": "75",
        "latitude": "48.85",
        "longitude": "2.35",
        "etat": "OUVERT",
        "date_maj_ligne": "2025-01-01T00:00:00+00:00",
        **_OFFER_FLAG_DEFAULTS,
    }
    row.update(overrides)
    return row


def ivac_row(uai: str = "0750001A", **overrides: Any) -> dict[str, Any]:
    """A source IVAC row exactly as `IVAC_SPEC.fields` expects it."""
    row: dict[str, Any] = {
        "uai": uai,
        "secteur": "public",
        "session": "2025-01-01T00:00:00+00:00",
        "nb_candidats_g": 100,
        "taux_de_reussite_g": 92.5,
        "va_du_taux_de_reussite_g": 1.2,
        "taux_d_acces_6eme_3eme": 88.0,
    }
    row.update(overrides)
    return row


def ival_gt_row(uai: str = "0750001A", **overrides: Any) -> dict[str, Any]:
    """A source IVAL GT row exactly as `IVAL_GT_SPEC.fields` expects it."""
    row: dict[str, Any] = {
        "uai": uai,
        "secteur": "public",
        "annee": "2025-01-01T00:00:00+00:00",
        "presents_total": 200,
        "taux_reu_total": 90.0,
        "va_reu_total": -2.5,
        "taux_acces_2nde": 85.0,
        "va_acces_2nde": 1.0,
        "taux_men_total": 70.0,
        "va_men_total": 3.0,
    }
    row.update(overrides)
    return row
