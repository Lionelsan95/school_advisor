"""SPIKE-1 — reliability of the UAI join between the directory and IVAC/IVAL.

Disposable spike code. See README.md in this directory.

Why this runs nationally instead of on a single departement
-----------------------------------------------------------
The ticket suggests "e.g. one full departement". These datasets are small
enough (68k directory rows, ~7k IVAC rows/year, ~4k IVAL rows/year) that the
whole population fits in memory via the export endpoint. A national run
removes the sampling risk entirely: a borderline match rate measured on one
departement would not support a go/no-go decision.

Why the denominator matters more than the rate
----------------------------------------------
The directory holds ~68 000 establishments of every level (mostly primary
schools). IVAC covers colleges, IVAL covers lycees. Dividing matches by the
raw directory count would produce a meaningless ~10% "match rate". Two
distinct questions are measured separately:

  A. Join reliability  — of the UAIs appearing in an indicator dataset, how
     many resolve to a directory entry? This is the question that decides
     whether the product can attach an indicator to an establishment.
  B. Coverage          — of the eligible directory establishments, how many
     have indicators at all? This is a product-scope question (how many
     fact sheets will show figures), not a join-defect question.

A row whose valeur_ajoutee is null because of the non-diffusion threshold
counts as a JOIN SUCCESS: the row exists, the value is legitimately withheld.
"""

from __future__ import annotations

from collections import Counter, defaultdict

import ods_client as ods

# Establishment types that IVAC/IVAL can legitimately cover.
ELIGIBLE_TYPES = {"Collège", "Lycée", "EREA"}

DIRECTORY_FIELDS = [
    "identifiant_de_l_etablissement",
    "nom_etablissement",
    "type_etablissement",
    "statut_public_prive",
    "code_departement",
    "etat",
]
IVAC_FIELDS = ["uai", "session", "secteur", "nb_candidats_g", "va_du_taux_de_reussite_g"]
IVAL_FIELDS = ["uai", "annee", "secteur", "presents_total", "va_reu_total"]


def year_of(value: object) -> int | None:
    """Both `session` (IVAC) and `annee` (IVAL v2) are ISO date strings."""
    if value is None:
        return None
    text = str(value)
    return int(text[:4]) if text[:4].isdigit() else None


def main() -> None:
    report: list[str] = ["# SPIKE-1 raw output — UAI join reliability", ""]

    def say(line: str = "") -> None:
        print(line)
        report.append(line)

    say("## Schema checks")
    ods.check_fields_present(ods.DATASET_DIRECTORY, DIRECTORY_FIELDS)
    ods.check_fields_present(ods.DATASET_IVAC, IVAC_FIELDS)
    ods.check_fields_present(ods.DATASET_IVAL_GT, IVAL_FIELDS)
    ods.check_fields_present(ods.DATASET_IVAL_PRO, IVAL_FIELDS)
    say("All expected fields present on all four datasets.")
    say()

    say("## Pulling data")
    directory = ods.export_all(ods.DATASET_DIRECTORY, ",".join(DIRECTORY_FIELDS))
    ivac = ods.export_all(ods.DATASET_IVAC, ",".join(IVAC_FIELDS))
    ival_gt = ods.export_all(ods.DATASET_IVAL_GT, ",".join(IVAL_FIELDS))
    ival_pro = ods.export_all(ods.DATASET_IVAL_PRO, ",".join(IVAL_FIELDS))
    say(
        f"directory={len(directory)} ivac={len(ivac)} "
        f"ival_gt={len(ival_gt)} ival_pro={len(ival_pro)}"
    )
    say()

    # --- Build the directory index -------------------------------------------------
    by_uai: dict[str, dict] = {}
    duplicates = 0
    for row in directory:
        uai = row["identifiant_de_l_etablissement"]
        if uai in by_uai:
            duplicates += 1
        by_uai[uai] = row
    if duplicates:
        say(f"WARNING: {duplicates} duplicate UAI(s) in the directory export.")

    eligible = {
        uai: row
        for uai, row in by_uai.items()
        if row.get("type_etablissement") in ELIGIBLE_TYPES
        and row.get("etat") == "OUVERT"
    }
    say("## Population")
    say(f"Directory rows            : {len(directory)}")
    say(f"Distinct UAI in directory : {len(by_uai)}")
    say(f"Eligible (college/lycee/EREA, OUVERT): {len(eligible)}")
    type_counts = Counter(r.get("type_etablissement") for r in by_uai.values())
    say(f"By type: {dict(type_counts.most_common(8))}")
    say()

    # --- Direction A: join reliability ---------------------------------------------
    sources = {
        "IVAC (colleges)": (ivac, "session"),
        "IVAL GT (lycees)": (ival_gt, "annee"),
        "IVAL PRO (lycees)": (ival_pro, "annee"),
    }

    say("## Direction A — join reliability (indicator UAI -> directory)")
    say()
    total_rows = 0
    total_rows_matched = 0
    unmatched_detail: dict[str, list[dict]] = {}

    for label, (rows, year_field) in sources.items():
        latest = max(year_of(r[year_field]) or 0 for r in rows)
        recent = [r for r in rows if year_of(r[year_field]) == latest]
        uais = {r["uai"] for r in recent}
        matched_any = {u for u in uais if u in by_uai}
        matched_eligible = {u for u in uais if u in eligible}
        unmatched = sorted(uais - set(by_uai))
        unmatched_detail[label] = [
            {"uai": u, "in_directory": False} for u in unmatched[:20]
        ]

        total_rows += len(recent)
        total_rows_matched += sum(1 for r in recent if r["uai"] in by_uai)

        say(f"### {label} — latest year {latest}")
        say(f"  rows: {len(recent)}   distinct UAI: {len(uais)}")
        say(
            f"  matched to ANY directory entry     : {len(matched_any)} "
            f"({100 * len(matched_any) / len(uais):.2f}%)"
        )
        say(
            f"  matched to an ELIGIBLE+OPEN entry  : {len(matched_eligible)} "
            f"({100 * len(matched_eligible) / len(uais):.2f}%)"
        )
        say(f"  unmatched entirely                 : {len(unmatched)}")

        # Classify the near-misses: present in the directory but filtered out.
        filtered = uais & set(by_uai) - set(eligible)
        reasons = Counter()
        for u in filtered:
            row = by_uai[u]
            reasons[f"{row.get('type_etablissement')}/{row.get('etat')}"] += 1
        if reasons:
            say(f"  in directory but not eligible      : {dict(reasons.most_common(6))}")
        if unmatched:
            say(f"  sample of unmatched UAI            : {unmatched[:10]}")
        say()

    overall = 100 * total_rows_matched / total_rows if total_rows else 0
    say(f"**Overall join reliability (latest year, all three sources): {overall:.2f}%**")
    say(f"({total_rows_matched} of {total_rows} indicator rows resolved to a directory entry)")
    say()

    # --- Direction B: coverage ------------------------------------------------------
    say("## Direction B — coverage (eligible directory establishment -> indicators)")
    say()
    indicator_uais: dict[str, set[str]] = {
        "college": {r["uai"] for r in ivac},
        "lycee": {r["uai"] for r in ival_gt} | {r["uai"] for r in ival_pro},
    }
    by_type: dict[str, list[dict]] = defaultdict(list)
    for row in eligible.values():
        by_type[row["type_etablissement"]].append(row)

    for etype, rows in sorted(by_type.items()):
        pool = indicator_uais["college"] if etype == "Collège" else indicator_uais["lycee"]
        if etype == "EREA":
            pool = indicator_uais["college"] | indicator_uais["lycee"]
        covered = sum(1 for r in rows if r["identifiant_de_l_etablissement"] in pool)
        say(f"### {etype}: {covered}/{len(rows)} ({100 * covered / len(rows):.1f}%) have indicators (any year)")
        # Which uncovered establishments are they?
        uncovered = [r for r in rows if r["identifiant_de_l_etablissement"] not in pool]
        status = Counter(r.get("statut_public_prive") for r in uncovered)
        say(f"  uncovered by statut: {dict(status.most_common())}")
        say()

    # Is the private hors-contrat sector structurally absent?
    say("## Sector check (is private hors contrat excluded from indicators?)")
    for etype, rows in sorted(by_type.items()):
        pool = indicator_uais["college"] if etype == "Collège" else indicator_uais["lycee"]
        if etype == "EREA":
            pool = indicator_uais["college"] | indicator_uais["lycee"]
        per_status: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for r in rows:
            bucket = per_status[r.get("statut_public_prive") or "None"]
            bucket[1] += 1
            if r["identifiant_de_l_etablissement"] in pool:
                bucket[0] += 1
        say(f"### {etype}")
        for status, (covered, total) in sorted(per_status.items()):
            say(f"  {status:28} {covered:5}/{total:5}  ({100 * covered / total:5.1f}%)")
        say()

    ods.write_report("spike1_uai_join.md", report)


if __name__ == "__main__":
    try:
        main()
    except ods.SpikeAbort as error:
        ods.fail(str(error))
