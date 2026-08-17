"""Row builders shared by the API integration tests.

A plain module rather than `conftest.py`: conftest injects fixtures, not
functions, so helpers placed there are invisible to the modules that call them.
Previously these lived in `test_establishments_api.py` and three other modules
imported them from it — a test module is not an API for other test modules.
"""

from __future__ import annotations

from typing import Any

import psycopg


def insert_establishment(
    connection: psycopg.Connection,
    uai: str,
    *,
    name: str = "Fake Test Establishment",
    type_: str = "lycee",
    sector: str = "public",
    department_code: str = "999",
    is_open: bool = True,
    filieres: list[str] | None = None,
    sections: list[str] | None = None,
    sites: list[dict[str, Any]] | None = None,
) -> None:
    sites = sites or [
        {
            "sequence": 0,
            "name": name,
            "city": "Fakeville",
            "postal_code": "99999",
            "latitude": None,
            "longitude": None,
        }
    ]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO establishment
                (uai, name, type, sector, department_code, is_open,
                 site_count, filieres, sections, source_updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (uai) DO UPDATE SET
                name = EXCLUDED.name, type = EXCLUDED.type,
                sector = EXCLUDED.sector, department_code = EXCLUDED.department_code,
                is_open = EXCLUDED.is_open, site_count = EXCLUDED.site_count,
                filieres = EXCLUDED.filieres, sections = EXCLUDED.sections
            """,
            (
                uai,
                name,
                type_,
                sector,
                department_code,
                is_open,
                len(sites),
                filieres or [],
                sections or [],
                "2026-01-01T00:00:00+00:00",
            ),
        )
        for site in sites:
            cursor.execute(
                """
                INSERT INTO site
                    (uai, sequence, name, address, postal_code, city, city_code,
                     latitude, longitude)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (uai, sequence) DO UPDATE SET
                    name = EXCLUDED.name, latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude, city = EXCLUDED.city
                """,
                (
                    uai,
                    site["sequence"],
                    site.get("name", name),
                    site.get("address"),
                    site.get("postal_code"),
                    site.get("city"),
                    site.get("city_code"),
                    site.get("latitude"),
                    site.get("longitude"),
                ),
            )


def insert_indicator(
    connection: psycopg.Connection,
    uai: str,
    year: int,
    *,
    indicator_type: str = "IVAC",
    sector: str = "public",
    candidates_present: int | None = 100,
    success_rate: float | None = 90.0,
    value_added_success: float | None = 1.0,
    access_rate: float | None = None,
    value_added_access: float | None = None,
    mention_rate: float | None = None,
    value_added_mention: float | None = None,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO indicator_result
                (uai, year, indicator_type, sector, candidates_present,
                 success_rate, value_added_success, access_rate,
                 value_added_access, mention_rate, value_added_mention)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (uai, year, indicator_type) DO UPDATE SET
                candidates_present = EXCLUDED.candidates_present,
                success_rate = EXCLUDED.success_rate,
                value_added_success = EXCLUDED.value_added_success,
                access_rate = EXCLUDED.access_rate,
                value_added_access = EXCLUDED.value_added_access,
                mention_rate = EXCLUDED.mention_rate,
                value_added_mention = EXCLUDED.value_added_mention
            """,
            (
                uai,
                year,
                indicator_type,
                sector,
                candidates_present,
                success_rate,
                value_added_success,
                access_rate,
                value_added_access,
                mention_rate,
                value_added_mention,
            ),
        )
