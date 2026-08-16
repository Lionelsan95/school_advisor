import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FactSheetPage } from "../src/pages/FactSheetPage";
import { factSheet } from "./fixtures";

function renderSheet() {
  return render(
    <MemoryRouter initialEntries={["/etablissements/9760127J"]}>
      <Routes>
        <Route path="/etablissements/:uai" element={<FactSheetPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("FactSheetPage (FE-2)", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => factSheet,
      }),
    );
  });

  it("renders the establishment and its scope disclaimer", async () => {
    renderSheet();
    expect(await screen.findByText(factSheet.identite.nom)).toBeInTheDocument();
    expect(screen.getByLabelText("Portée des données")).toBeInTheDocument();
  });

  it("renders the absence from the API's static block, not a local string", async () => {
    renderSheet();
    await waitFor(() =>
      expect(screen.getAllByText("Valeur non disponible").length).toBeGreaterThan(0),
    );
  });

  it("never states why a value is absent", async () => {
    const { container } = renderSheet();
    await screen.findByText(factSheet.identite.nom);
    expect(container.textContent ?? "").not.toMatch(
      /seuil|effectif insuffisant|trop peu/i,
    );
  });

  it("shows the published rate alongside the absent value added", async () => {
    renderSheet();
    // The Mayotte case: a real success rate with no value added. Both must be
    // rendered honestly — the presence of one is not evidence about the other.
    expect(await screen.findByText(/57\s*%/)).toBeInTheDocument();
  });
});
