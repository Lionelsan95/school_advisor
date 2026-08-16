import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScopeDisclaimer } from "../src/components/ScopeDisclaimer";

const TEXT = "Ces indicateurs décrivent certains résultats scolaires.";

describe("ScopeDisclaimer (FE-3 / F7)", () => {
  it("renders the text the API supplied, verbatim", () => {
    render(<ScopeDisclaimer text={TEXT} />);
    expect(screen.getByText(TEXT)).toBeInTheDocument();
  });

  it("offers no way to dismiss it", () => {
    // docs/14 §7: the reminder can never be closed permanently.
    render(<ScopeDisclaimer text={TEXT} />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
