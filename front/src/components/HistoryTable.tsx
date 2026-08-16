import type { HistoryPoint } from "../api/types";
import { HISTORY } from "../content/copy";
import styles from "./HistoryTable.module.css";

/**
 * The equivalent data table the charter (§10) requires beside every chart.
 *
 * It is built from the *same* `points` array the chart receives, deliberately:
 * a table assembled from a second query could show a different set of years
 * than the picture next to it, and the reader would have no way to tell which
 * was right. Exact values are accessible here, which is the other thing §10
 * asks for — a chart alone makes a value approximate.
 */
export function HistoryTable({
  points,
  label,
  unit,
}: {
  points: HistoryPoint[];
  label: string;
  unit: string;
}) {
  return (
    <table className={styles.table}>
      <caption className={styles.caption}>{HISTORY.tableCaption(label)}</caption>
      <thead>
        <tr>
          <th scope="col">{HISTORY.year}</th>
          <th scope="col">
            {label} ({unit})
          </th>
        </tr>
      </thead>
      <tbody>
        {points.map((point) => (
          <tr key={point.annee}>
            <th scope="row">{point.annee}</th>
            <td>
              {point.valeur === null ? (
                // An absent year is stated, never shown as a bare dash or a
                // zero — both would read as a result.
                <span className={styles.absent}>{HISTORY.notPublished}</span>
              ) : (
                point.valeur.toLocaleString("fr-FR", { maximumFractionDigits: 1 })
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
