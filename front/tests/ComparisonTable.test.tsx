import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ComparisonIdentity, ComparisonRow } from "../src/api/types";
import { ComparisonTable } from "../src/components/ComparisonTable";
import { absenceExplanation, explanation, presentFigure, source } from "./fixtures";

const YEAR_ABSENCE = {
  ...absenceExplanation,
  content_id: "annee_non_publiee",
  titre: "Année non publiée pour cet établissement",
  definition_simple:
    "Aucun résultat n'est publié pour cet établissement pour cette année.",
};

const explanations = {
  taux_reussite: explanation,
  taux_attendu: { ...explanation, content_id: "taux_attendu" },
  valeur_ajoutee: { ...explanation, content_id: "valeur_ajoutee" },
  taux_acces: { ...explanation, content_id: "taux_acces" },
  taux_mention: { ...explanation, content_id: "taux_mention" },
  valeur_non_disponible: absenceExplanation,
  annee_non_publiee: YEAR_ABSENCE,
};

const establishments: ComparisonIdentity[] = [
  { uai: "9990001A", nom: "Lycée A", type: "lycee", statut_public_prive: "public", commune: "Ville" },
  { uai: "9990002B", nom: "Collège B", type: "college", statut_public_prive: "public", commune: "Ville" },
];

function resultYear(annee: number) {
  return {
    annee,
    type_indicateur: "IVAL_GT",
    candidats_presents: 100,
    taux_reussite: { ...presentFigure, valeur: 94 },
    taux_reussite_attendu: { ...presentFigure, valeur: 91 },
    valeur_ajoutee_reussite: { ...presentFigure, valeur: 3 },
    taux_acces: { ...presentFigure, valeur: 80 },
    valeur_ajoutee_acces: { ...presentFigure, valeur: 1 },
    taux_mention: { ...presentFigure, valeur: 60 },
    valeur_ajoutee_mention: { ...presentFigure, valeur: 2 },
    source,
  };
}

/** 2013: only the lycée published. 2023: both did. */
const rows: ComparisonRow[] = [
  {
    annee: 2023,
    cellules: [
      { uai: "9990001A", annee_publiee: true, resultat: resultYear(2023), explication_absence: null },
      { uai: "9990002B", annee_publiee: true, resultat: resultYear(2023), explication_absence: null },
    ],
  },
  {
    annee: 2013,
    cellules: [
      { uai: "9990001A", annee_publiee: true, resultat: resultYear(2013), explication_absence: null },
      { uai: "9990002B", annee_publiee: false, resultat: null, explication_absence: "annee_non_publiee" },
    ],
  },
];

function renderTable() {
  return render(
    <ComparisonTable
      establishments={establishments}
      rows={rows}
      explanations={explanations}
      onExplain={vi.fn()}
    />,
  );
}

describe("ComparisonTable (F4)", () => {
  it("shows both establishments for a year they both published", () => {
    renderTable();
    expect(screen.getAllByText("Lycée A").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Collège B").length).toBeGreaterThan(0);
  });

  it("states a year one establishment never published, rather than leaving a blank", () => {
    // A blank column beside a filled one reads as a loss. IVAC simply starts
    // in 2022, which says nothing about either establishment.
    renderTable();
    expect(screen.getByText(YEAR_ABSENCE.titre)).toBeInTheDocument();
    expect(screen.getByText(YEAR_ABSENCE.definition_simple)).toBeInTheDocument();
  });

  it("computes and displays no difference, winner or aggregate", () => {
    const { container } = renderTable();
    const text = container.textContent ?? "";
    // Charter §11 forbids a gap, a count of criteria won, an average, a score
    // or a verdict. None may appear even incidentally.
    for (const forbidden of [
      "écart",
      "differ",
      "meilleur",
      "gagnant",
      "score",
      "moyenne des",
      "verdict",
    ]) {
      expect(text.toLowerCase()).not.toContain(forbidden.toLowerCase());
    }
    // 94 appears twice (once per establishment) and is never subtracted.
    expect(text).not.toMatch(/\+3 points d'écart|3 points de plus/i);
  });

  it("gives both columns the same class, so neither can be emphasised", () => {
    const { container } = renderTable();
    // The direct children of each row's grid are the two establishment
    // columns. Selecting on a class substring would also catch the grid
    // wrapper itself, which is not a column.
    const grids = container.querySelectorAll("section > div");
    expect(grids.length).toBeGreaterThan(0);

    for (const grid of grids) {
      const columns = Array.from(grid.children);
      expect(columns).toHaveLength(2);
      // One shared class: there is no "winner" or "highlight" variant to
      // apply to whichever column happens to hold the larger number.
      expect(new Set(columns.map((node) => node.className)).size).toBe(1);
    }
  });
});
