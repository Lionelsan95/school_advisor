"""Postgres repositories, using psycopg 3 with plain parameterised SQL.

No ORM: the schema is four tables and the queries are simple. See
docs/02_Architecture_Decisions.md — added indirection is exactly what this
project is supposed to resist.

Bulk loading uses COPY. The Phase 0 spike measured ~440 rows/s with a naive
executemany, which was the only slow step of the whole pipeline; COPY removes
it (see docs/05_Resultats_Spike_Technique.md, section 3, recommendation 4).
"""

from __future__ import annotations

import logging

import psycopg
from psycopg import sql

from src.domain.commune import Commune
from src.domain.establishment import Establishment
from src.domain.indicator_result import IndicatorResult
from src.domain.source_reference import SourceReference

logger = logging.getLogger(__name__)


SNAPSHOT_TABLES = ("establishment", "site")


class PostgresEstablishmentRepository:
    """Implements `EstablishmentRepository`.

    `replace_all` snapshots the current tables, truncates them and re-COPYs the
    new data, all inside one transaction. TRUNCATE is transactional in
    Postgres, so readers never observe a half-loaded directory, and the
    snapshot gives a cheap rollback (see `restore_previous`). At ~9 MB this
    costs nothing, which is why it is preferred over dump/restore.

    An earlier version built staging tables with `LIKE ... INCLUDING ALL` and
    renamed them into place. That was abandoned: Postgres gives the copied
    indexes generated names, and a table rename does not rename its indexes,
    so after one run the live table carried `establishment_staging_type_idx2`
    instead of `ix_establishment_type` — with the suffix incrementing on every
    subsequent run. Any later migration referring to an index by its declared
    name would have failed. Truncate-and-refill keeps the schema objects, and
    their names, exactly as the migration defined them.
    """

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def replace_all(self, establishments: list[Establishment]) -> int:
        with self._connection.transaction(), self._connection.cursor() as cursor:
            # Snapshot first: plain data copies, no indexes needed — these
            # exist only to be restored from.
            for table in SNAPSHOT_TABLES:
                cursor.execute(
                    sql.SQL("DROP TABLE IF EXISTS {}").format(
                        sql.Identifier(f"{table}_previous")
                    )
                )
                cursor.execute(
                    sql.SQL("CREATE TABLE {} AS SELECT * FROM {}").format(
                        sql.Identifier(f"{table}_previous"), sql.Identifier(table)
                    )
                )

            cursor.execute("TRUNCATE establishment, site")

            with cursor.copy(
                "COPY establishment "
                "(uai, name, type, sector, department_code, is_open, "
                "site_count, filieres, sections, source_updated_at) FROM STDIN"
            ) as copy:
                for establishment in establishments:
                    copy.write_row(
                        (
                            establishment.uai,
                            establishment.name,
                            establishment.type.value,
                            establishment.sector.value
                            if establishment.sector
                            else None,
                            establishment.department_code,
                            establishment.is_open,
                            len(establishment.sites),
                            [f.value for f in establishment.filieres],
                            [s.value for s in establishment.sections],
                            establishment.source_updated_at,
                        )
                    )

            with cursor.copy(
                "COPY site "
                "(uai, sequence, name, address, postal_code, city, city_code, "
                "latitude, longitude) FROM STDIN"
            ) as copy:
                for establishment in establishments:
                    for site in establishment.sites:
                        copy.write_row(
                            (
                                establishment.uai,
                                site.sequence,
                                site.name,
                                site.address,
                                site.postal_code,
                                site.city,
                                site.city_code,
                                site.latitude,
                                site.longitude,
                            )
                        )

        logger.info("Replaced establishment snapshot with %d rows", len(establishments))
        return len(establishments)

    def restore_previous(self) -> int:
        """Roll back to the snapshot taken before the last `replace_all`.

        Exists so the rollback the architecture decision calls for is a real,
        tested operation rather than a sequence of SQL a human has to compose
        by hand during an incident.
        """
        with self._connection.transaction(), self._connection.cursor() as cursor:
            for table in SNAPSHOT_TABLES:
                cursor.execute("SELECT to_regclass(%s)", (f"public.{table}_previous",))
                row = cursor.fetchone()
                if row is None or row[0] is None:
                    raise RuntimeError(
                        f"No snapshot table {table}_previous — nothing to restore."
                    )
            cursor.execute("TRUNCATE establishment, site")
            cursor.execute(
                """
                INSERT INTO establishment (
                    uai, name, type, sector, department_code, is_open,
                    site_count, source_updated_at, filieres, sections
                )
                SELECT uai, name, type, sector, department_code, is_open,
                       site_count, source_updated_at, filieres, sections
                FROM establishment_previous
                """
            )
            cursor.execute(
                """
                INSERT INTO site (
                    uai, sequence, name, address, postal_code, city, city_code,
                    latitude, longitude
                )
                SELECT uai, sequence, name, address, postal_code, city, city_code,
                       latitude, longitude
                FROM site_previous
                """
            )
        restored = self.count()
        logger.warning(
            "Rolled back to the previous snapshot (%d establishments)", restored
        )
        return restored

    def count(self) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM establishment")
            row = cursor.fetchone()
            return int(row[0]) if row else 0


class PostgresIndicatorRepository:
    """Implements `IndicatorRepository`.

    Append-only: rows are inserted with ON CONFLICT DO NOTHING on the natural
    key `(uai, year, indicator_type)`. There is deliberately no UPDATE path —
    a past year can never be rewritten by a later run, which is what feature
    F5 (multi-year history) depends on.
    """

    _COLUMNS = (
        "uai",
        "year",
        "indicator_type",
        "sector",
        "candidates_present",
        "success_rate",
        "value_added_success",
        "access_rate",
        "value_added_access",
        "mention_rate",
        "value_added_mention",
    )

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def append(self, indicators: list[IndicatorResult]) -> int:
        if not indicators:
            return 0
        before = self.count()
        with self._connection.transaction(), self._connection.cursor() as cursor:
            # ON COMMIT DROP alone is not enough: when several appends run
            # inside one outer transaction (as the ingestion job does), the
            # commit that would drop this table has not happened yet and the
            # second CREATE fails with DuplicateTable. Drop explicitly.
            cursor.execute("DROP TABLE IF EXISTS indicator_incoming")
            cursor.execute(
                "CREATE TEMPORARY TABLE indicator_incoming "
                "(LIKE indicator_result INCLUDING DEFAULTS) ON COMMIT DROP"
            )
            columns = ", ".join(self._COLUMNS)
            with cursor.copy(f"COPY indicator_incoming ({columns}) FROM STDIN") as copy:
                for result in indicators:
                    copy.write_row(
                        (
                            result.uai,
                            result.year,
                            result.indicator_type.value,
                            result.sector.value if result.sector else None,
                            result.candidates_present,
                            result.success_rate,
                            result.value_added_success,
                            result.access_rate,
                            result.value_added_access,
                            result.mention_rate,
                            result.value_added_mention,
                        )
                    )
            cursor.execute(
                f"INSERT INTO indicator_result ({columns}) "
                f"SELECT {columns} FROM indicator_incoming "
                f"ON CONFLICT (uai, year, indicator_type) DO NOTHING"
            )
        inserted = self.count() - before
        logger.info(
            "Appended %d new indicator row(s) from %d offered",
            inserted,
            len(indicators),
        )
        return inserted

    def count(self) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM indicator_result")
            row = cursor.fetchone()
        return int(row[0]) if row else 0


class PostgresCommuneRepository:
    """Atomic snapshot storage for the official commune reference."""

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def replace_all(self, communes: list[Commune]) -> int:
        with self._connection.transaction(), self._connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS commune_previous")
            cursor.execute("CREATE TABLE commune_previous AS SELECT * FROM commune")
            cursor.execute("TRUNCATE commune")
            with cursor.copy(
                "COPY commune (code, name, postal_codes, department_code, "
                "latitude, longitude) FROM STDIN"
            ) as copy:
                for commune in communes:
                    copy.write_row(
                        (
                            commune.code,
                            commune.name,
                            list(commune.postal_codes),
                            commune.department_code,
                            commune.latitude,
                            commune.longitude,
                        )
                    )
        logger.info("Replaced commune snapshot with %d rows", len(communes))
        return len(communes)

    def restore_previous(self) -> int:
        with self._connection.transaction(), self._connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.commune_previous')")
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError(
                    "No snapshot table commune_previous — nothing to restore."
                )
            cursor.execute("TRUNCATE commune")
            cursor.execute(
                "INSERT INTO commune "
                "(code, name, postal_codes, department_code, latitude, longitude) "
                "SELECT code, name, postal_codes, department_code, latitude, "
                "longitude FROM commune_previous"
            )
        restored = self.count()
        logger.warning(
            "Rolled back to the previous commune snapshot (%d rows)", restored
        )
        return restored

    def count(self) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM commune")
            row = cursor.fetchone()
            return int(row[0]) if row else 0


class PostgresSourceReferenceRepository:
    """Implements `SourceReferenceRepository`.

    Unlike the two above, this one *does* update in place: a source reference
    describes where a dataset lives and when we last read it, so the current
    value is the only useful one. Nothing historical is lost — the per-run
    history lives in `ingestion_run`.
    """

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def snapshot(self) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS source_reference_previous")
            cursor.execute(
                "CREATE TABLE source_reference_previous AS "
                "SELECT * FROM source_reference"
            )

    def restore_previous(self) -> int:
        with self._connection.transaction(), self._connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.source_reference_previous')")
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError(
                    "No snapshot table source_reference_previous — nothing to restore."
                )
            cursor.execute("TRUNCATE source_reference")
            cursor.execute(
                "INSERT INTO source_reference "
                "(dataset_id, url, last_synchronised_at, source_published_at) "
                "SELECT dataset_id, url, last_synchronised_at, source_published_at "
                "FROM source_reference_previous"
            )
            cursor.execute("SELECT count(*) FROM source_reference")
            count_row = cursor.fetchone()
        restored = int(count_row[0]) if count_row else 0
        logger.warning("Rolled back to %d previous source references", restored)
        return restored

    def upsert(self, reference: SourceReference) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO source_reference
                    (dataset_id, url, last_synchronised_at, source_published_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (dataset_id) DO UPDATE SET
                    url = EXCLUDED.url,
                    last_synchronised_at = EXCLUDED.last_synchronised_at,
                    source_published_at = EXCLUDED.source_published_at
                """,
                (
                    reference.dataset_id,
                    reference.url,
                    reference.last_synchronised_at,
                    reference.source_published_at,
                ),
            )
