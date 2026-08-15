"""SPIKE-3 — throwaway ingestion prototype against the local Postgres.

Disposable spike code. See README.md in this directory.

Purpose: observe real volumes, shapes and field-level data quality so the
Phase 1 data model can be sized correctly. Tables are prefixed `spike_` so
they can never be confused with the Alembic-managed Phase 1 schema.

This also verifies empirically the two domain rules the product depends on:
  - the non-diffusion threshold (<20 candidates GT, <10 PRO) from
    docs/03_Glossaire_Metier.md;
  - that indicator rows are keyed by (uai, year) and can therefore be stored
    append-only, as required by F5 and docs/02_Architecture_Decisions.md.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from collections import Counter, defaultdict

import psycopg2

import ods_client as ods

DATABASE_URL = os.environ.get(
    "DATABASE_URL_LOCAL",
    "postgresql://schools_app:local_dev_password@localhost:5432/schools_db",
)

DIRECTORY_FIELDS = [
    "identifiant_de_l_etablissement",
    "nom_etablissement",
    "type_etablissement",
    "statut_public_prive",
    "code_postal",
    "nom_commune",
    "code_departement",
    "latitude",
    "longitude",
    "etat",
    "date_maj_ligne",
]
IVAC_FIELDS = [
    "uai",
    "session",
    "secteur",
    "nb_candidats_g",
    "taux_de_reussite_g",
    "va_du_taux_de_reussite_g",
    "nb_candidats_p",
    "taux_de_reussite_p",
]
IVAL_FIELDS = [
    "uai",
    "annee",
    "secteur",
    "presents_total",
    "taux_reu_total",
    "va_reu_total",
    "taux_acces_2nde",
]


def year_of(value: object) -> int | None:
    text = str(value)
    return int(text[:4]) if text[:4].isdigit() else None


def null_rates(rows: list[dict], fields: list[str]) -> list[tuple[str, float]]:
    total = len(rows) or 1
    return [
        (f, 100 * sum(1 for r in rows if r.get(f) in (None, "")) / total) for f in fields
    ]


def main() -> None:
    report: list[str] = ["# SPIKE-3 raw output — ingestion prototype", ""]

    def say(line: str = "") -> None:
        print(line)
        report.append(line)

    say("## 1. Volumes and payload shape")
    say()
    pulls = {
        "directory": (ods.DATASET_DIRECTORY, DIRECTORY_FIELDS),
        "ivac": (ods.DATASET_IVAC, IVAC_FIELDS),
        "ival_gt": (ods.DATASET_IVAL_GT, IVAL_FIELDS),
        "ival_pro": (ods.DATASET_IVAL_PRO, IVAL_FIELDS),
    }
    data: dict[str, list[dict]] = {}
    for name, (dataset_id, fields) in pulls.items():
        started = time.monotonic()
        rows = ods.export_all(dataset_id, ",".join(fields))
        elapsed = time.monotonic() - started
        data[name] = rows
        sizes = [len(json.dumps(r)) for r in rows[:2000]]
        say(
            f"  {name:10} rows={len(rows):6}  fetch={elapsed:5.1f}s  "
            f"avg_json={statistics.mean(sizes):5.0f}B  max_json={max(sizes):5}B  "
            f"est_total={len(rows) * statistics.mean(sizes) / 1e6:.1f}MB"
        )
    say()

    say("## 2. Field-level null rates (selected fields only)")
    say()
    for name, (_, fields) in pulls.items():
        say(f"  {name}:")
        for field, rate in sorted(null_rates(data[name], fields), key=lambda x: -x[1]):
            if rate > 0:
                say(f"    {field:32} {rate:5.1f}% null")
    say()

    say("## 3. Geolocation completeness (needed for PostGIS proximity search)")
    say()
    eligible = [
        r
        for r in data["directory"]
        if r.get("type_etablissement") in {"Collège", "Lycée", "EREA"}
        and r.get("etat") == "OUVERT"
    ]
    missing_geo = [r for r in eligible if r.get("latitude") is None or r.get("longitude") is None]
    say(f"  eligible establishments      : {len(eligible)}")
    say(f"  without latitude/longitude   : {len(missing_geo)} "
        f"({100 * len(missing_geo) / len(eligible):.2f}%)")
    say("  => proximity search must degrade gracefully for these.")
    say()

    say("## 4. Non-diffusion threshold rule, checked against real data")
    say()
    # IVAL GT: value added should be withheld below 20 candidates.
    for label, rows, count_field, va_field, threshold in (
        ("IVAL GT", data["ival_gt"], "presents_total", "va_reu_total", 20),
        ("IVAL PRO", data["ival_pro"], "presents_total", "va_reu_total", 10),
        ("IVAC (G)", data["ivac"], "nb_candidats_g", "va_du_taux_de_reussite_g", 20),
    ):
        below = [r for r in rows if (r.get(count_field) or 0) < threshold]
        above = [r for r in rows if (r.get(count_field) or 0) >= threshold]
        below_with_value = sum(1 for r in below if r.get(va_field) is not None)
        above_without_value = sum(1 for r in above if r.get(va_field) is None)
        say(f"  {label} (threshold {threshold} candidates)")
        say(f"    rows below threshold           : {len(below)}")
        say(f"      ... of which carry a value   : {below_with_value}")
        say(f"    rows at/above threshold        : {len(above)}")
        say(f"      ... of which have NO value   : {above_without_value}")
        say()

    say("## 5. Append-only key check — is (uai, year) unique?")
    say()
    for name in ("ivac", "ival_gt", "ival_pro"):
        year_field = "session" if name == "ivac" else "annee"
        keys = Counter((r["uai"], year_of(r[year_field])) for r in data[name])
        dupes = [k for k, n in keys.items() if n > 1]
        say(f"  {name:10} distinct (uai, year) keys={len(keys):6}  duplicates={len(dupes)}")
    directory_keys = Counter(r["identifiant_de_l_etablissement"] for r in data["directory"])
    dir_dupes = [u for u, n in directory_keys.items() if n > 1]
    say(f"  directory  distinct UAI={len(directory_keys):6}  duplicated UAI={len(dir_dupes)}")
    if dir_dupes:
        example = [r for r in data["directory"] if r["identifiant_de_l_etablissement"] == dir_dupes[0]]
        say(f"    example: {dir_dupes[0]} appears {len(example)} times ->")
        for row in example:
            say(f"      {row.get('nom_etablissement')} ({row.get('nom_commune')})")
        say("    => UAI is NOT a unique key in the directory: multi-site")
        say("       establishments share one UAI. Phase 1 must decide on a")
        say("       deduplication rule before making uai a primary key.")
    say()

    say("## 6. Loading into local Postgres")
    say()
    connection = psycopg2.connect(DATABASE_URL)
    connection.autocommit = True
    with connection.cursor() as cursor:
        cursor.execute("SELECT version(), postgis_full_version()")
        version, postgis = cursor.fetchone()
        say(f"  server: {version.split(',')[0]}")
        say(f"  postgis: {postgis.split(' ')[0]} {postgis.split(' ')[1]}")

        cursor.execute("DROP TABLE IF EXISTS spike_etablissements, spike_indicateurs")
        cursor.execute(
            """
            CREATE TABLE spike_etablissements (
                uai text NOT NULL,
                nom text,
                type_etablissement text,
                statut text,
                code_postal text,
                commune text,
                code_departement text,
                latitude double precision,
                longitude double precision,
                etat text
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE spike_indicateurs (
                uai text NOT NULL,
                annee integer NOT NULL,
                type_indicateur text NOT NULL,
                presents integer,
                taux_reussite double precision,
                valeur_ajoutee double precision,
                sous_seuil_diffusion boolean NOT NULL,
                PRIMARY KEY (uai, annee, type_indicateur)
            )
            """
        )

        started = time.monotonic()
        cursor.executemany(
            "INSERT INTO spike_etablissements VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [
                (
                    r["identifiant_de_l_etablissement"],
                    r.get("nom_etablissement"),
                    r.get("type_etablissement"),
                    r.get("statut_public_prive"),
                    r.get("code_postal"),
                    r.get("nom_commune"),
                    r.get("code_departement"),
                    r.get("latitude"),
                    r.get("longitude"),
                    r.get("etat"),
                )
                for r in data["directory"]
            ],
        )
        directory_seconds = time.monotonic() - started

        indicator_rows = []
        for name, kind, count_field, threshold in (
            ("ivac", "IVAC", "nb_candidats_g", 20),
            ("ival_gt", "IVAL_GT", "presents_total", 20),
            ("ival_pro", "IVAL_PRO", "presents_total", 10),
        ):
            year_field = "session" if name == "ivac" else "annee"
            va_field = "va_du_taux_de_reussite_g" if name == "ivac" else "va_reu_total"
            reu_field = "taux_de_reussite_g" if name == "ivac" else "taux_reu_total"
            for r in data[name]:
                value_added = r.get(va_field)
                indicator_rows.append(
                    (
                        r["uai"],
                        year_of(r[year_field]),
                        kind,
                        r.get(count_field),
                        r.get(reu_field),
                        value_added,
                        value_added is None,
                    )
                )
        started = time.monotonic()
        cursor.executemany(
            "INSERT INTO spike_indicateurs VALUES (%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (uai, annee, type_indicateur) DO NOTHING",
            indicator_rows,
        )
        indicator_seconds = time.monotonic() - started

        cursor.execute("SELECT count(*) FROM spike_etablissements")
        n_etab = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM spike_indicateurs")
        n_ind = cursor.fetchone()[0]
        cursor.execute(
            "SELECT pg_size_pretty(pg_total_relation_size('spike_etablissements')), "
            "pg_size_pretty(pg_total_relation_size('spike_indicateurs'))"
        )
        size_etab, size_ind = cursor.fetchone()

        say(f"  establishments loaded : {n_etab} in {directory_seconds:.1f}s ({size_etab})")
        say(f"  indicators loaded     : {n_ind} in {indicator_seconds:.1f}s ({size_ind})")
        say(f"  indicator rows offered: {len(indicator_rows)} "
            f"(difference = duplicate (uai, annee, type) keys rejected)")

        # Re-run the same insert: append-only behaviour must not lose prior years.
        cursor.executemany(
            "INSERT INTO spike_indicateurs VALUES (%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (uai, annee, type_indicateur) DO NOTHING",
            indicator_rows,
        )
        cursor.execute("SELECT count(*) FROM spike_indicateurs")
        say(f"  after identical re-run: {cursor.fetchone()[0]} rows (must be unchanged)")

        cursor.execute(
            "SELECT type_indicateur, min(annee), max(annee), count(*) "
            "FROM spike_indicateurs GROUP BY type_indicateur ORDER BY 1"
        )
        say()
        say("  stored history span per indicator type:")
        for kind, first, last, count in cursor.fetchall():
            say(f"    {kind:10} {first}-{last}  {count} rows")
    connection.close()
    say()

    ods.write_report("spike3_ingestion_prototype.md", report)


if __name__ == "__main__":
    try:
        main()
    except ods.SpikeAbort as error:
        ods.fail(str(error))
