import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { HistoryPoint, MethodologyBreak } from "../src/api/types";
import { HistoryChart } from "../src/components/HistoryChart";
import { HistoryTable } from "../src/components/HistoryTable";

const BREAK_2021: MethodologyBreak = {
  annee: 2021,
  content_id: "rupture_bac_2021",
  version: 1,
  titre: "Changement de méthode en 2021",
  note: "La réforme du baccalauréat s'applique à partir de la session 2021.",
};

const contiguous: HistoryPoint[] = [
  { annee: 2018, valeur: 90 },
  { annee: 2019, valeur: 91 },
  { annee: 2020, valeur: 92 },
];

function polylines(container: HTMLElement) {
  return Array.from(container.querySelectorAll("polyline"));
}

describe("HistoryChart", () => {
  it("draws one continuous line when every year is present", () => {
    const { container } = render(
      <HistoryChart points={contiguous} breaks={[]} title="Taux" unit="%" />,
    );
    expect(polylines(container)).toHaveLength(1);
  });

  it("breaks the line across a year the source did not publish", () => {
    // Joining across a gap would draw a value nobody measured. Charter §10
    // requires missing years to be left empty, not interpolated.
    const withGap: HistoryPoint[] = [
      { annee: 2018, valeur: 90 },
      { annee: 2019, valeur: 91 },
      // 2020 absent entirely
      { annee: 2021, valeur: 93 },
    ];
    const { container } = render(
      <HistoryChart points={withGap} breaks={[]} title="Taux" unit="%" />,
    );
    expect(polylines(container).length).toBeGreaterThan(1);
  });

  it("breaks the line at a methodology rupture even when years are contiguous", () => {
    // The case that matters most: the stored series IS continuous across 2021,
    // so nothing in the data hints at the reform. The visual break has to
    // carry the warning by itself, or the reader compares across it.
    const acrossReform: HistoryPoint[] = [
      { annee: 2019, valeur: 90 },
      { annee: 2020, valeur: 91 },
      { annee: 2021, valeur: 92 },
      { annee: 2022, valeur: 93 },
    ];
    const { container } = render(
      <HistoryChart
        points={acrossReform}
        breaks={[BREAK_2021]}
        title="Taux"
        unit="%"
      />,
    );
    expect(polylines(container).length).toBe(2);
  });

  it("omits a value the source did not publish rather than plotting zero", () => {
    const withNull: HistoryPoint[] = [
      { annee: 2019, valeur: 90 },
      { annee: 2020, valeur: null },
      { annee: 2021, valeur: 92 },
    ];
    const { container } = render(
      <HistoryChart points={withNull} breaks={[]} title="Taux" unit="%" />,
    );
    // Two plotted points, not three — and certainly not a 0 standing in for
    // the year nobody published.
    expect(container.querySelectorAll("circle")).toHaveLength(2);
  });

  it("draws no axis at all when the series has no published value", () => {
    const { container } = render(
      <HistoryChart
        points={[{ annee: 2020, valeur: null }]}
        breaks={[]}
        title="Taux"
        unit="%"
      />,
    );
    // An empty chart frame invites the reader to look for a missing line.
    expect(container.querySelector("svg")).toBeNull();
  });
});

describe("HistoryTable (the charter-mandated equivalent table)", () => {
  it("shows every year the chart was given, including unpublished ones", () => {
    const withNull: HistoryPoint[] = [
      { annee: 2019, valeur: 90 },
      { annee: 2020, valeur: null },
    ];
    const { container } = render(
      <HistoryTable points={withNull} label="Taux de réussite" unit="%" />,
    );
    // Both are built from the same array, so chart and table cannot disagree
    // about which years exist — the table states the absence the chart omits.
    expect(container.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(container.textContent).toContain("Non publiée");
  });
});
