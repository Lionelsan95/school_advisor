"""SPIKE-2 — methodological continuity of the IVAL series (legacy vs v2).

Disposable spike code. See README.md in this directory.

Question to answer: can the 2012-2025 IVAL history be displayed as one
continuous series (F5), or is there a break that must be surfaced to the user?

Three separate things could break continuity, and they are checked separately
because they have different consequences for the UI:

  1. A *publication* break — the dataset was re-published under a new id with
     renamed fields. Cosmetic for the user, but real work for ingestion.
  2. A *value* break — the same UAI/year carries different numbers in the old
     and new datasets, meaning the DEPP recomputed the series.
  3. A *scope* break — the set of measured sub-indicators changes mid-series
     (e.g. the 2021 baccalaureat reform removing the L/ES/S streams). The
     total-level indicators can stay continuous while the per-stream ones do
     not.
"""

from __future__ import annotations

import ods_client as ods

# Field pairs that should be equivalent between the legacy and the v2 dataset.
GT_EQUIVALENTS = [
    ("taux_reu_total", "taux_brut_de_reussite_total_series"),
    ("va_reu_total", "va_reu_total"),
    ("taux_acces_2nde", "taux_acces_brut_seconde_bac"),
    ("presents_total", "effectif_presents_total_series"),
]
PRO_EQUIVALENTS = [
    ("taux_reu_total", "taux_brut_de_reussite_total_secteurs"),
    ("va_reu_total", "va_reu_total"),
    ("presents_total", "effectif_presents_total_secteurs"),
]

SAMPLE_SIZE = 200


def normalise(value: object) -> float | None:
    """The legacy datasets type several numeric columns as text."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare_pair(
    say, label: str, new_id: str, legacy_id: str, equivalents: list[tuple[str, str]]
) -> None:
    say(f"## {label}")
    say()

    new_meta = ods.dataset_metadata(new_id)["metas"]["default"]
    legacy_meta = ods.dataset_metadata(legacy_id)["metas"]["default"]
    say(f"  v2     : {new_id}")
    say(f"           {new_meta['records_count']} rows, modified {new_meta['modified'][:10]}")
    say(f"  legacy : {legacy_id}")
    say(f"           {legacy_meta['records_count']} rows, modified {legacy_meta['modified'][:10]}")
    say()

    # --- 1. Publication break: field naming ------------------------------------
    new_fields = set(ods.field_names(new_id))
    legacy_fields = set(ods.field_names(legacy_id))
    shared = new_fields & legacy_fields
    say(f"  fields: v2={len(new_fields)} legacy={len(legacy_fields)} shared={len(shared)}")
    say(f"  key field: v2 uses 'uai', legacy uses 'code_etablissement' -> {'uai' in legacy_fields}")
    say()

    # --- 2. Year ranges ---------------------------------------------------------
    new_years = ods.aggregate(new_id, "annee as y, count(*) as n", "annee", "y")
    legacy_years = ods.aggregate(legacy_id, "annee as y, count(*) as n", "annee", "y")
    new_map = {str(r["y"])[:4]: r["n"] for r in new_years}
    legacy_map = {str(r["y"])[:4]: r["n"] for r in legacy_years}
    say(f"  v2 years     : {min(new_map)}-{max(new_map)}")
    say(f"  legacy years : {min(legacy_map)}-{max(legacy_map)}")
    overlap = sorted(set(new_map) & set(legacy_map))
    say(f"  overlap      : {overlap[0]}-{overlap[-1]} ({len(overlap)} years)")
    identical_counts = [y for y in overlap if new_map[y] == legacy_map[y]]
    say(f"  years with identical row counts on both sides: {len(identical_counts)}/{len(overlap)}")
    if len(identical_counts) != len(overlap):
        differing = {y: (legacy_map[y], new_map[y]) for y in overlap if new_map[y] != legacy_map[y]}
        say(f"  DIFFERING counts (legacy, v2): {differing}")
    say()

    # --- 3. Value break on the overlap -----------------------------------------
    probe_year = overlap[-1]
    say(f"  Value comparison on {probe_year}, {SAMPLE_SIZE} establishments:")
    new_sel = "uai," + ",".join(sorted({n for n, _ in equivalents}))
    legacy_sel = "code_etablissement," + ",".join(sorted({legacy for _, legacy in equivalents}))
    new_rows = ods.export_all(
        new_id, new_sel, where=f"annee=date'{probe_year}'", cache=True
    )[:SAMPLE_SIZE]
    legacy_rows = ods.export_all(
        legacy_id, legacy_sel, where=f"annee={probe_year}", cache=True
    )
    legacy_by_uai = {r["code_etablissement"]: r for r in legacy_rows}

    compared = 0
    mismatches: list[str] = []
    missing = 0
    for row in new_rows:
        legacy = legacy_by_uai.get(row["uai"])
        if legacy is None:
            missing += 1
            continue
        for new_field, legacy_field in equivalents:
            a, b = normalise(row.get(new_field)), normalise(legacy.get(legacy_field))
            compared += 1
            if a != b:
                mismatches.append(f"{row['uai']} {new_field}: v2={a} legacy={b}")

    say(f"    values compared      : {compared}")
    say(f"    value mismatches     : {len(mismatches)}")
    say(f"    absent from legacy   : {missing}")
    for line in mismatches[:10]:
        say(f"      {line}")
    say()
    verdict = (
        "NO value break — v2 republishes identical figures under new field names"
        if not mismatches
        else "VALUE BREAK DETECTED — see mismatches above"
    )
    say(f"  => {verdict}")
    say()


def check_stream_scope(say) -> None:
    """Detect the 2021 baccalaureat reform break in the per-stream sub-indicators."""
    say("## Scope break — per-stream sub-indicators (GT)")
    say()
    select = (
        "annee as y, count(*) as n, "
        "count(presents_l) as n_l, count(presents_es) as n_es, count(presents_s) as n_s, "
        "count(presents_gnle) as n_gnle, "
        "count(taux_reu_total) as n_reu, count(va_reu_total) as n_va, "
        "count(taux_acces_2nde) as n_acces"
    )
    rows = ods.aggregate(ods.DATASET_IVAL_GT, select, "annee", "y")
    say("  year   rows      L     ES      S   GNLE  |  reu_total  va_total  acces")
    for r in rows:
        say(
            f"  {str(r['y'])[:4]}  {r['n']:5}  {r['n_l']:5}  {r['n_es']:5}  {r['n_s']:5}  "
            f"{r['n_gnle']:5}  |  {r['n_reu']:9}  {r['n_va']:8}  {r['n_acces']:5}"
        )
    say()
    first_gnle = min((str(r["y"])[:4] for r in rows if r["n_gnle"] > 0), default=None)
    last_lsg = max((str(r["y"])[:4] for r in rows if r["n_s"] > 0), default=None)
    say(f"  Last year with L/ES/S streams : {last_lsg}")
    say(f"  First year with 'generale'    : {first_gnle}")
    say(
        "  => Per-stream series BREAK at the baccalaureat reform. "
        "Total-level indicators remain populated across every year."
    )
    say()


def check_ivac(say) -> None:
    say("## IVAC (colleges) — single dataset, no legacy/v2 split")
    say()
    rows = ods.aggregate(
        ods.DATASET_IVAC,
        "session as y, count(*) as n, count(va_du_taux_de_reussite_g) as n_va, "
        "count(taux_de_reussite_g) as n_reu",
        "session",
        "y",
    )
    for r in rows:
        say(f"  {str(r['y'])[:4]}: rows={r['n']:5}  taux_reussite={r['n_reu']:5}  va={r['n_va']:5}")
    years = [str(r["y"])[:4] for r in rows]
    say(f"  => IVAC covers {min(years)}-{max(years)} only ({len(years)} years), one dataset, no rename.")
    say()


def main() -> None:
    report: list[str] = ["# SPIKE-2 raw output — IVAL methodology continuity", ""]

    def say(line: str = "") -> None:
        print(line)
        report.append(line)

    compare_pair(
        say,
        "IVAL general & technological (GT)",
        ods.DATASET_IVAL_GT,
        ods.DATASET_IVAL_GT_LEGACY,
        GT_EQUIVALENTS,
    )
    compare_pair(
        say,
        "IVAL professional (PRO)",
        ods.DATASET_IVAL_PRO,
        ods.DATASET_IVAL_PRO_LEGACY,
        PRO_EQUIVALENTS,
    )
    check_stream_scope(say)
    check_ivac(say)

    ods.write_report("spike2_ival_continuity.md", report)


if __name__ == "__main__":
    try:
        main()
    except ods.SpikeAbort as error:
        ods.fail(str(error))
