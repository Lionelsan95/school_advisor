import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getHistory } from "../api/establishments";
import type { HistoryPoint, HistorySeriesKey } from "../api/types";
import { ErrorState } from "../components/ErrorState";
import { HistoryChart } from "../components/HistoryChart";
import { HistoryTable } from "../components/HistoryTable";
import { ScopeDisclaimer } from "../components/ScopeDisclaimer";
import { FACT_SHEET, HISTORY, SEARCH } from "../content/copy";
import { useApiResource } from "../hooks/useApiResource";
import styles from "./HistoryPage.module.css";

/**
 * FE-4 / F5 — one indicator's series over the published years.
 *
 * One indicator is shown at a time. Overlaying several would invite comparing
 * their shapes, which is a step toward the aggregate reading the charter
 * refuses; and on a mobile viewport it is unreadable anyway (docs/12 §7).
 *
 * The selector below chooses *which series to look at*. It is not a sort — the
 * years are always in chronological order, and no ordering here depends on a
 * value.
 */
const SERIES: Array<{ key: HistorySeriesKey; labelKey: keyof typeof FACT_SHEET.labels; unit: string }> = [
  { key: "taux_reussite", labelKey: "taux_reussite", unit: FACT_SHEET.units.rate },
  {
    key: "valeur_ajoutee_reussite",
    labelKey: "valeur_ajoutee_reussite",
    unit: FACT_SHEET.units.points,
  },
  { key: "taux_acces", labelKey: "taux_acces", unit: FACT_SHEET.units.rate },
  { key: "taux_mention", labelKey: "taux_mention", unit: FACT_SHEET.units.rate },
];

export function HistoryPage() {
  const { uai = "" } = useParams();
  const [seriesKey, setSeriesKey] = useState<HistorySeriesKey>("taux_reussite");
  const resource = useApiResource((signal) => getHistory(uai, signal), uai);

  if (resource.state === "loading") {
    return (
      <main className={styles.page}>
        <p role="status">{SEARCH.loading}</p>
      </main>
    );
  }
  if (resource.state === "error") {
    return (
      <main className={styles.page}>
        <ErrorState error={resource.error} />
      </main>
    );
  }

  const history = resource.data;
  const series = SERIES.find((item) => item.key === seriesKey) ?? SERIES[0];
  const label = FACT_SHEET.labels[series.labelKey];

  // One point per year for the selected figure. A year whose figure was not
  // published keeps its place with a null value, so the table can state the
  // absence and the chart can break the line rather than bridge it.
  const points: HistoryPoint[] = history.points.map((row) => ({
    annee: row.annee,
    valeur: row[series.key].valeur,
  }));

  const covered = history.annees_couvertes;
  const from = covered[0];
  const to = covered[covered.length - 1];

  return (
    <main className={styles.page}>
      <p className={styles.back}>
        <Link to={`/etablissements/${history.uai}`}>{HISTORY.backToSheet}</Link>
      </p>
      <h1 className={styles.title}>{history.nom}</h1>
      <h2 className={styles.subtitle}>{HISTORY.heading}</h2>

      <ScopeDisclaimer text={history.rappel_de_portee} />

      {covered.length > 0 && (
        <p className={styles.coverage}>{HISTORY.coverage(from, to)}</p>
      )}

      <label className={styles.selectorLabel} htmlFor="series">
        {HISTORY.seriesLabel}
      </label>
      <select
        id="series"
        className={styles.selector}
        value={seriesKey}
        onChange={(event) => setSeriesKey(event.target.value as HistorySeriesKey)}
      >
        {SERIES.map((item) => (
          <option key={item.key} value={item.key}>
            {FACT_SHEET.labels[item.labelKey]}
          </option>
        ))}
      </select>

      <HistoryChart
        points={points}
        breaks={history.ruptures_methodologiques}
        title={HISTORY.chartTitle(label, from, to)}
        unit={series.unit}
      />

      {/* The rupture note is API-supplied static content. The chart shows a
          break; this says what it means. */}
      {history.ruptures_methodologiques.map((item) => (
        <aside key={item.annee} className={styles.break}>
          <h3 className={styles.breakTitle}>
            {item.titre} ({item.annee})
          </h3>
          <p className={styles.breakNote}>{item.note}</p>
        </aside>
      ))}

      {/* Charter §10 requires an equivalent table beside every chart. */}
      <div className={styles.tableWrap}>
        <HistoryTable points={points} label={label} unit={series.unit} />
      </div>
    </main>
  );
}
