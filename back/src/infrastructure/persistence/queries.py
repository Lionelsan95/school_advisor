"""Read adapters for the Phase 2 API.

Kept apart from `repositories.py`, which is the ingestion write side. Same
house style: psycopg 3 with parameterised SQL, no ORM.

The proximity search uses PostGIS as a function library over the existing
`site.latitude` / `site.longitude` float columns — `ST_DistanceSphere` for the
exact cut, preceded by a bounding-box filter that `ix_site_coordinates` can
serve. No geometry column is introduced: at 68k rows the box narrows the
candidate set enough that a stored geography would buy nothing, and it would
be a second representation of the same coordinates to keep in sync.

Caveat carried from the Phase 0 spike and `Site`'s docstring: annexe sites of
a multi-site establishment repeat the parent's coordinates in the source. Two
sites 30 km apart can share a point, so a distance here is accurate to the
establishment, not to each of its buildings.
"""

from __future__ import annotations

from math import cos, radians
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from src.application.ports import (
    CommuneSearchHit,
    SearchCriteria,
    SearchHit,
    SearchResults,
)
from src.domain.commune import Commune
from src.domain.enums import (
    EstablishmentType,
    Filiere,
    IndicatorType,
    Section,
    Sector,
)
from src.domain.establishment import Establishment, Site
from src.domain.indicator_result import IndicatorResult
from src.domain.source_reference import SourceReference


def _establishment_from_rows(
    establishment_row: dict[str, Any], site_rows: list[dict[str, Any]]
) -> Establishment:
    return Establishment(
        uai=establishment_row["uai"],
        name=establishment_row["name"],
        type=EstablishmentType(establishment_row["type"]),
        sector=Sector(establishment_row["sector"])
        if establishment_row["sector"]
        else None,
        department_code=establishment_row["department_code"],
        is_open=establishment_row["is_open"],
        sites=tuple(
            Site(
                sequence=row["sequence"],
                name=row["name"],
                address=row["address"],
                postal_code=row["postal_code"],
                city=row["city"],
                city_code=row["city_code"],
                latitude=row["latitude"],
                longitude=row["longitude"],
            )
            for row in site_rows
        ),
        filieres=tuple(Filiere(value) for value in establishment_row["filieres"]),
        sections=tuple(Section(value) for value in establishment_row["sections"]),
        source_updated_at=establishment_row["source_updated_at"],
    )


_ESTABLISHMENT_FIELDS = (
    "uai",
    "name",
    "type",
    "sector",
    "department_code",
    "is_open",
    "filieres",
    "sections",
    "source_updated_at",
)
_ESTABLISHMENT_COLUMNS = ", ".join(_ESTABLISHMENT_FIELDS)
_ESTABLISHMENT_COLUMNS_QUALIFIED = sql.SQL(
    ", ".join(f"e.{name}" for name in _ESTABLISHMENT_FIELDS)
)
_SITE_COLUMNS = (
    "uai, sequence, name, address, postal_code, city, city_code, latitude, longitude"
)


class PostgresEstablishmentReader:
    """Implements `EstablishmentReader`."""

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def get_by_uai(self, uai: str) -> Establishment | None:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                f"SELECT {_ESTABLISHMENT_COLUMNS} FROM establishment WHERE uai = %s",
                (uai,),
            )
            establishment_row = cursor.fetchone()
            if establishment_row is None:
                return None
            cursor.execute(
                f"SELECT {_SITE_COLUMNS} FROM site WHERE uai = %s ORDER BY sequence",
                (uai,),
            )
            site_rows = cursor.fetchall()
        return _establishment_from_rows(establishment_row, site_rows)

    def search(self, criteria: SearchCriteria) -> SearchResults:
        where, params = self._filters(criteria)
        text_query = (
            criteria.text_query.strip() if criteria.text_query is not None else None
        )

        # One row per establishment, represented by its canonical site, so a
        # multi-site establishment appears once rather than once per building.
        #
        # LATERAL ... ORDER BY sequence LIMIT 1 rather than `sequence = 0`:
        # the domain defines the canonical site as the *lowest* sequence
        # (Establishment.canonical_site), not literally zero. Those coincide
        # today because DirectoryAdapter numbers sites with enumerate(), but
        # an equality test would turn any future gap in that numbering into an
        # establishment silently missing from every search result — reachable
        # by UAI, invisible to search, with nothing raised.
        query_context = sql.SQL("")
        context_params: list[Any] = []
        if text_query is not None:
            query_context = sql.SQL(
                "CROSS JOIN LATERAL ("
                "  SELECT normalize_search_text(%s) AS text, "
                "         upper(regexp_replace(%s, '\\s+', '', 'g')) AS uai"
                ") q "
            )
            context_params = [text_query, text_query]

        base = sql.SQL(
            "FROM establishment e "
            "JOIN LATERAL ("
            "  SELECT * FROM site WHERE site.uai = e.uai ORDER BY sequence LIMIT 1"
            ") s ON true "
            "{query_context}"
            "WHERE {where}"
        ).format(
            query_context=query_context,
            where=sql.SQL(" AND ").join(where),
        )

        match_tier = sql.SQL("")
        if text_query is not None:
            match_tier = sql.SQL(
                "CASE "
                "WHEN e.uai = q.uai THEN 0 "
                "WHEN e.search_name = q.text THEN 1 "
                "WHEN s.search_city = q.text OR s.postal_code = %s THEN 2 "
                "WHEN e.search_name LIKE q.text || '%%' THEN 3 "
                "WHEN s.search_city LIKE q.text || '%%' THEN 4 "
                "WHEN e.search_name LIKE '%%' || q.text || '%%' THEN 5 "
                "ELSE 6 END"
            )

        if criteria.has_location:
            distance = sql.SQL(
                "ST_DistanceSphere("
                "  ST_MakePoint(s.longitude, s.latitude), ST_MakePoint(%s, %s)"
                ") / 1000.0"
            )
            select = sql.SQL(
                "SELECT {columns}, {distance} AS distance_km{match_column} "
            ).format(
                columns=_ESTABLISHMENT_COLUMNS_QUALIFIED,
                distance=distance,
                match_column=(
                    sql.SQL(", {tier} AS match_tier").format(tier=match_tier)
                    if text_query is not None
                    else sql.SQL("")
                ),
            )
            # Proximity, then name — so ties resolve identically on every run
            # instead of following whatever order the planner produced.
            order = (
                sql.SQL(
                    " ORDER BY match_tier ASC, distance_km ASC, e.name ASC, e.uai ASC"
                )
                if text_query is not None
                else sql.SQL(" ORDER BY distance_km ASC, e.name ASC, e.uai ASC")
            )
            select_params: list[Any] = [criteria.longitude, criteria.latitude]
            if text_query is not None:
                select_params.append(text_query)
        else:
            select = sql.SQL(
                "SELECT {columns}, NULL::float AS distance_km{match_column} "
            ).format(
                columns=_ESTABLISHMENT_COLUMNS_QUALIFIED,
                match_column=(
                    sql.SQL(", {tier} AS match_tier").format(tier=match_tier)
                    if text_query is not None
                    else sql.SQL("")
                ),
            )
            order = (
                sql.SQL(
                    " ORDER BY match_tier ASC, s.city ASC NULLS LAST, "
                    "e.name ASC, e.uai ASC"
                )
                if text_query is not None
                else sql.SQL(" ORDER BY s.city ASC NULLS LAST, e.name ASC, e.uai ASC")
            )
            select_params = [text_query] if text_query is not None else []

        # One transaction around the count, the page and the site fetch. Under
        # the default READ COMMITTED each statement would take its own
        # snapshot, so an ingestion committing mid-request could return a total
        # that does not match the page, or a row whose sites have just been
        # replaced. A single transaction makes the three agree.
        with (
            self._connection.transaction(),
            self._connection.cursor(row_factory=dict_row) as cursor,
        ):
            cursor.execute(
                sql.SQL("SELECT count(*) AS total ") + base,
                [*context_params, *params],
            )
            total_row = cursor.fetchone()
            total = int(total_row["total"]) if total_row else 0

            cursor.execute(
                select + base + order + sql.SQL(" LIMIT %s OFFSET %s"),
                [
                    *select_params,
                    *context_params,
                    *params,
                    criteria.limit,
                    criteria.offset,
                ],
            )
            rows = cursor.fetchall()

            uais = [row["uai"] for row in rows]
            sites_by_uai: dict[str, list[dict[str, Any]]] = {uai: [] for uai in uais}
            if uais:
                cursor.execute(
                    f"SELECT {_SITE_COLUMNS} FROM site "
                    "WHERE uai = ANY(%s) ORDER BY uai, sequence",
                    (uais,),
                )
                for site_row in cursor.fetchall():
                    sites_by_uai[site_row["uai"]].append(site_row)

        hits = tuple(
            SearchHit(
                establishment=_establishment_from_rows(row, sites_by_uai[row["uai"]]),
                distance_km=round(row["distance_km"], 2)
                if row["distance_km"] is not None
                else None,
            )
            for row in rows
        )
        return SearchResults(hits=hits, total_count=total)

    def _filters(
        self, criteria: SearchCriteria
    ) -> tuple[list[sql.Composable], list[Any]]:
        """Build the WHERE clause.

        Every branch here filters on what an establishment *is* or *offers*.
        There is no branch on a result value, and no code path that could add
        one without changing `SearchCriteria` first.
        """
        where: list[sql.Composable] = [sql.SQL("e.is_open")]
        params: list[Any] = []

        if criteria.establishment_type is not None:
            where.append(sql.SQL("e.type = %s"))
            params.append(criteria.establishment_type.value)
        if criteria.sector is not None:
            where.append(sql.SQL("e.sector = %s"))
            params.append(criteria.sector.value)
        if criteria.filiere is not None:
            where.append(sql.SQL("e.filieres @> ARRAY[%s]::text[]"))
            params.append(criteria.filiere.value)
        if criteria.text_query is not None:
            where.append(
                sql.SQL(
                    "(e.uai = q.uai OR e.search_name LIKE '%%' || q.text || '%%' "
                    "OR s.search_city LIKE '%%' || q.text || '%%' "
                    "OR s.postal_code = %s)"
                )
            )
            params.append(criteria.text_query.strip())
        if criteria.commune_code is not None:
            where.append(sql.SQL("s.city_code = %s"))
            params.append(criteria.commune_code.strip())
        if criteria.postal_code is not None:
            where.append(sql.SQL("s.postal_code = %s"))
            params.append(criteria.postal_code.strip())

        latitude, longitude, radius_km = (
            criteria.latitude,
            criteria.longitude,
            criteria.radius_km,
        )
        if latitude is not None and longitude is not None and radius_km is not None:
            # Establishments with no coordinates drop out here, because a NULL
            # fails every comparison. That is the intended behaviour: they
            # cannot be placed, and guessing a location would invent data.
            #
            # The bounding box is only an index-friendly pre-filter; the
            # ST_DistanceSphere test below is what actually defines the result
            # set. So the box is added only when it is certainly safe — if it
            # would run past a pole or across the antimeridian, it is skipped
            # entirely and the exact test stands alone. Slower, always right.
            # A wrap-around box would be correct too, but it would be a branch
            # no French establishment can currently reach (the easternmost
            # site sits at 168.1°E in Nouvelle-Calédonie) and therefore a
            # branch no test would meaningfully exercise.
            lat_delta = radius_km / 111.0
            lng_delta = radius_km / max(111.0 * cos(radians(latitude)), 1e-6)
            lat_low, lat_high = latitude - lat_delta, latitude + lat_delta
            lng_low, lng_high = longitude - lng_delta, longitude + lng_delta
            box_is_safe = (
                lat_low >= -90
                and lat_high <= 90
                and lng_low >= -180
                and lng_high <= 180
            )
            if box_is_safe:
                where.append(
                    sql.SQL(
                        "s.latitude BETWEEN %s AND %s AND s.longitude BETWEEN %s AND %s"
                    )
                )
                params.extend([lat_low, lat_high, lng_low, lng_high])

            where.append(
                sql.SQL(
                    "ST_DistanceSphere("
                    "  ST_MakePoint(s.longitude, s.latitude), ST_MakePoint(%s, %s)"
                    ") <= %s"
                )
            )
            params.extend([longitude, latitude, radius_km * 1000.0])

        return where, params


class PostgresCommuneReader:
    """Deterministic name/code/postcode lookup over the ingested reference."""

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def search(self, query: str, limit: int) -> tuple[CommuneSearchHit, ...]:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                WITH q AS (
                    SELECT normalize_search_text(%s) AS text, upper(%s::text) AS raw
                )
                SELECT c.code, c.name, c.postal_codes, c.department_code,
                       c.latitude, c.longitude,
                       CASE
                           WHEN c.code = q.raw THEN 0
                           WHEN q.raw = ANY(c.postal_codes) THEN 1
                           WHEN c.search_name = q.text THEN 2
                           WHEN c.search_name LIKE q.text || '%%' THEN 3
                           ELSE 4
                       END AS match_tier
                FROM commune c CROSS JOIN q
                WHERE c.code = q.raw
                   OR q.raw = ANY(c.postal_codes)
                   OR c.search_name LIKE '%%' || q.text || '%%'
                ORDER BY match_tier ASC, c.name ASC, c.code ASC
                LIMIT %s
                """,
                (query, query.strip(), limit),
            )
            rows = cursor.fetchall()
        return tuple(
            CommuneSearchHit(
                commune=Commune(
                    code=row["code"],
                    name=row["name"],
                    postal_codes=tuple(row["postal_codes"]),
                    department_code=row["department_code"],
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                ),
                match_tier=row["match_tier"],
            )
            for row in rows
        )


class PostgresIndicatorReader:
    """Implements `IndicatorReader`."""

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def list_for_establishment(self, uai: str) -> list[IndicatorResult]:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT uai, year, indicator_type, sector, candidates_present,
                       success_rate, value_added_success, access_rate,
                       value_added_access, mention_rate, value_added_mention
                FROM indicator_result
                WHERE uai = %s
                ORDER BY year DESC, indicator_type ASC
                """,
                (uai,),
            )
            rows = cursor.fetchall()
        return [
            IndicatorResult(
                uai=row["uai"],
                year=row["year"],
                indicator_type=IndicatorType(row["indicator_type"]),
                sector=Sector(row["sector"]) if row["sector"] else None,
                candidates_present=row["candidates_present"],
                success_rate=row["success_rate"],
                value_added_success=row["value_added_success"],
                access_rate=row["access_rate"],
                value_added_access=row["value_added_access"],
                mention_rate=row["mention_rate"],
                value_added_mention=row["value_added_mention"],
            )
            for row in rows
        ]


class PostgresSourceReferenceReader:
    """Implements `SourceReferenceReader`."""

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def all_by_dataset_id(self) -> dict[str, SourceReference]:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "SELECT dataset_id, url, last_synchronised_at, source_published_at "
                "FROM source_reference"
            )
            rows = cursor.fetchall()
        return {
            row["dataset_id"]: SourceReference(
                dataset_id=row["dataset_id"],
                url=row["url"],
                last_synchronised_at=row["last_synchronised_at"],
                source_published_at=row["source_published_at"],
            )
            for row in rows
        }
