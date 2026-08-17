import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GlossaryProvider } from "../src/context/GlossaryContext";
import { GlossaryTerm } from "../src/components/GlossaryTerm";

const GLOSSARY = {
  version: 1,
  rappel_de_portee: "Ces indicateurs décrivent certains résultats scolaires.",
  termes: [
    {
      term_id: "ulis",
      terme: "ULIS",
      definition:
        "Une unité localisée pour l'inclusion scolaire accueille des élèves en " +
        "situation de handicap avec un accompagnement adapté.",
      exemple: null,
      source: "Annuaire de l'éducation.",
      termes_associes: ["segpa"],
    },
  ],
};

function renderTerm(termId: string) {
  return render(
    <GlossaryProvider>
      <GlossaryTerm termId={termId}>{termId.toUpperCase()}</GlossaryTerm>
    </GlossaryProvider>,
  );
}

describe("GlossaryTerm (FE-7)", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => GLOSSARY }),
    );
  });

  it("turns a known term into a definition trigger", async () => {
    renderTerm("ulis");
    expect(await screen.findByRole("button", { name: /Définition : ULIS/ })).toBeInTheDocument();
  });

  it("shows the API's definition, not a locally written one", async () => {
    renderTerm("ulis");
    await userEvent.click(await screen.findByRole("button", { name: /Définition/ }));

    expect(screen.getByText(GLOSSARY.termes[0].definition)).toBeInTheDocument();
  });

  it("renders an unknown term as plain text rather than a broken link", async () => {
    // "sport" is a real section value with no glossary entry. A definition is
    // an aid; its absence must never withhold the label or the figure beside it.
    renderTerm("sport");
    expect(await screen.findByText("SPORT")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("degrades to plain text when the glossary cannot be fetched", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    renderTerm("ulis");

    expect(await screen.findByText("ULIS")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
