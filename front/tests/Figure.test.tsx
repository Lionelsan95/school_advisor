import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Figure } from "../src/components/Figure";
import {
  absenceExplanation,
  absentFigure,
  computedFigure,
  explanation,
  presentFigure,
  source,
} from "./fixtures";

const base = {
  label: "Taux de réussite",
  unit: "%",
  year: 2025,
  explanation,
  absenceExplanation,
  source,
  onExplain: vi.fn(),
};

describe("Figure", () => {
  it("renders a published value with its unit", () => {
    render(<Figure {...base} figure={presentFigure} />);
    expect(screen.getByText(/94\s*%/)).toBeInTheDocument();
  });

  it("always renders the source beside the number", () => {
    render(<Figure {...base} figure={presentFigure} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", source.url);
  });

  it("marks a derived value as computed so it cannot pass for official data", () => {
    render(<Figure {...base} figure={computedFigure} />);
    expect(screen.getByText("Calculé par ce service")).toBeInTheDocument();
  });

  describe("absent value (the Mayotte case: 655 candidates, no value added)", () => {
    it("states the absence using the API's approved wording", () => {
      render(<Figure {...base} figure={absentFigure} />);
      expect(screen.getByText(absenceExplanation.titre)).toBeInTheDocument();
    });

    it("never states a cause for the absence", () => {
      const { container } = render(<Figure {...base} figure={absentFigure} />);
      const text = container.textContent ?? "";
      // The source publishes no reason; asserting one would be the exact
      // factual error the backend's design exists to prevent.
      expect(text).not.toMatch(/seuil|effectif|insuffisant|trop peu/i);
    });

    it("does not render the absence as a bare dash alone", () => {
      // docs/14 §6 forbids showing only a dash: it reads as a negative result.
      render(<Figure {...base} figure={absentFigure} />);
      expect(screen.getByText(absenceExplanation.titre)).toBeVisible();
    });
  });
});
