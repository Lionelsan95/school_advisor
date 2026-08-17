import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ComparisonPage } from "../src/pages/ComparisonPage";
import { FactSheetPage } from "../src/pages/FactSheetPage";
import { factSheet } from "./fixtures";

/**
 * F8's acceptance criterion is that exported content carries the explanations,
 * the scope reminder and the sources IN FULL — no shortened version.
 *
 * A print stylesheet alone cannot deliver that. On screen, only the
 * explanation panel the reader opened exists in the DOM, so printing would
 * silently drop the other five. These tests assert the print-only block exists
 * regardless of interaction, which is the part that actually satisfies the
 * criterion.
 */
function renderSheet() {
  return render(
    <MemoryRouter initialEntries={["/etablissements/9760127J"]}>
      <Routes>
        <Route path="/etablissements/:uai" element={<FactSheetPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("printable fact sheet (F8)", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => factSheet }),
    );
  });

  it("renders every explanation without any panel being opened", async () => {
    const { container } = renderSheet();
    await screen.findByText(factSheet.identite.nom);

    const printBlock = container.querySelector(".print-only");
    expect(printBlock).not.toBeNull();

    // All six blocks the API returned, not just one.
    for (const block of Object.values(factSheet.explications)) {
      expect(printBlock!.textContent).toContain(block.titre);
      expect(printBlock!.textContent).toContain(block.definition_simple);
    }
  });

  it("includes what each indicator does NOT measure", async () => {
    // The limits are the part most easily lost in an export, and the part the
    // charter most insists on keeping.
    const { container } = renderSheet();
    await screen.findByText(factSheet.identite.nom);
    const printBlock = container.querySelector(".print-only")!;

    for (const block of Object.values(factSheet.explications)) {
      expect(printBlock.textContent).toContain(block.ce_que_cela_ne_mesure_pas);
    }
  });

  it("keeps the scope reminder on the page that would be printed", async () => {
    renderSheet();
    await waitFor(() =>
      expect(screen.getByLabelText("Portée des données")).toBeInTheDocument(),
    );
  });

  it("states when the page was consulted", async () => {
    const { container } = renderSheet();
    await screen.findByText(factSheet.identite.nom);
    // A shared or printed page must say when the data was current, or the
    // recipient cannot tell how old it is.
    expect(container.querySelector(".print-only")!.textContent).toMatch(
      /Page consultée le/,
    );
  });

  it("hides the share controls from the printed output", async () => {
    const { container } = renderSheet();
    await screen.findByText(factSheet.identite.nom);
    // Buttons that cannot be pressed on paper are noise; `.no-print` is what
    // the stylesheet keys on.
    expect(container.querySelector(".no-print")).not.toBeNull();
  });
});

/**
 * The comparison page must print the same complete explanations as the fact
 * sheet. It did not: it rendered three of the charter's six parts, dropping
 * `comment_lire` and `methode` — which for an absence are the sentences saying
 * it is "ni un résultat élevé, ni un résultat faible" and that nothing is ever
 * substituted for a missing value.
 *
 * Nothing caught it because the tests above only exercised the fact sheet.
 * These cover the second surface, and assert the two agree rather than
 * checking each against a hand-written list that could drift.
 */
describe("printable comparison (F8)", () => {
  const comparison = {
    etablissements: [
      { uai: "9990001A", nom: "Lycée A", type: "lycee", statut_public_prive: "public", commune: "Ville" },
      { uai: "9990002B", nom: "Collège B", type: "college", statut_public_prive: "public", commune: "Ville" },
    ],
    lignes: [],
    explications: factSheet.explications,
    rappel_de_portee: factSheet.rappel_de_portee,
  };

  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => comparison }),
    );
  });

  async function renderComparison() {
    const view = render(
      <MemoryRouter initialEntries={["/comparaison?uai=9990001A&uai=9990002B"]}>
        <Routes>
          <Route path="/comparaison" element={<ComparisonPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByLabelText("Portée des données");
    return view;
  }

  it("prints all six parts of every explanation, like the fact sheet", async () => {
    const { container } = await renderComparison();
    const printed = container.querySelector(".print-only")!.textContent ?? "";

    for (const block of Object.values(factSheet.explications)) {
      expect(printed).toContain(block.definition_simple);
      expect(printed).toContain(block.comment_lire);
      expect(printed).toContain(block.ce_que_cela_mesure);
      expect(printed).toContain(block.ce_que_cela_ne_mesure_pas);
      expect(printed).toContain(block.source);
      if (block.methode) expect(printed).toContain(block.methode);
    }
  });

  it("keeps the absence disclaimer that stops a gap reading as a poor result", async () => {
    const { container } = await renderComparison();
    const printed = container.querySelector(".print-only")!.textContent ?? "";
    const absence = factSheet.explications.valeur_non_disponible;

    expect(printed).toContain(absence.comment_lire);
    expect(printed).toContain(absence.methode!);
  });

  it("keeps the scope reminder", async () => {
    await renderComparison();
    expect(screen.getByLabelText("Portée des données")).toBeInTheDocument();
  });
});
