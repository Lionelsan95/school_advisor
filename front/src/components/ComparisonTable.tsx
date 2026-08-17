import type {
  ComparisonIdentity,
  ComparisonRow,
  Explanation,
  ResultYear,
} from "../api/types";
import { FACT_SHEET } from "../content/copy";
import { Figure } from "./Figure";
import styles from "./ComparisonTable.module.css";

/**
 * Two establishments' records, in parallel (F4).
 *
 * Every number here is rendered by the very same `<Figure>` the fact sheet
 * uses, unchanged. That is the enforcement, not a convenience: `Figure` has no
 * prop for emphasis or tone, so "same visual weight across all compared
 * establishments" (FE-5's acceptance criterion) is inherited rather than
 * re-earned. A bespoke cell renderer would have to promise that again, and
 * could quietly stop keeping the promise.
 *
 * The props accept only the backend's already-aligned rows. There is no path
 * through which two values for a year arrive as a pair, which is what makes
 * the computations the charter (§11) forbids — a gap, a winner, a score —
 * un-buildable here rather than merely absent.
 */
export interface ComparisonTableProps {
  establishments: ComparisonIdentity[];
  rows: ComparisonRow[];
  explanations: Record<string, Explanation>;
  onExplain: (explanation: Explanation) => void;
}

const INDICATORS: Array<{
  key: keyof Pick<
    ResultYear,
    | "taux_reussite"
    | "taux_reussite_attendu"
    | "valeur_ajoutee_reussite"
    | "taux_acces"
    | "taux_mention"
  >;
  labelKey: keyof typeof FACT_SHEET.labels;
  explanationId: string;
  unit: string;
}> = [
  {
    key: "taux_reussite",
    labelKey: "taux_reussite",
    explanationId: "taux_reussite",
    unit: FACT_SHEET.units.rate,
  },
  {
    key: "taux_reussite_attendu",
    labelKey: "taux_reussite_attendu",
    explanationId: "taux_attendu",
    unit: FACT_SHEET.units.rate,
  },
  {
    key: "valeur_ajoutee_reussite",
    labelKey: "valeur_ajoutee_reussite",
    explanationId: "valeur_ajoutee",
    unit: FACT_SHEET.units.points,
  },
  {
    key: "taux_acces",
    labelKey: "taux_acces",
    explanationId: "taux_acces",
    unit: FACT_SHEET.units.rate,
  },
  {
    key: "taux_mention",
    labelKey: "taux_mention",
    explanationId: "taux_mention",
    unit: FACT_SHEET.units.rate,
  },
];

export function ComparisonTable({
  establishments,
  rows,
  explanations,
  onExplain,
}: ComparisonTableProps) {
  const absence = explanations.valeur_non_disponible;
  const yearAbsence = explanations.annee_non_publiee;

  return (
    <div className={styles.wrap}>
      {rows.map((row) => (
        <section key={row.annee} className={styles.year}>
          <h3 className={styles.yearTitle}>{FACT_SHEET.yearLabel(row.annee)}</h3>

          <div className={styles.columns}>
            {row.cellules.map((cell) => {
              const identity = establishments.find((e) => e.uai === cell.uai);
              return (
                <div key={cell.uai} className={styles.column}>
                  <h4 className={styles.columnTitle}>{identity?.nom ?? cell.uai}</h4>

                  {cell.resultat === null ? (
                    // Not a blank. A blank beside a filled column reads as a
                    // loss; this says the year was never published for this
                    // establishment, which is usually just IVAC starting later.
                    <p className={styles.yearAbsent}>
                      <span className={styles.yearAbsentTitle}>
                        {yearAbsence.titre}
                      </span>
                      <span className={styles.yearAbsentBody}>
                        {yearAbsence.definition_simple}
                      </span>
                    </p>
                  ) : (
                    <dl className={styles.figures}>
                      {INDICATORS.map((indicator) => (
                        <Figure
                          key={indicator.key}
                          figure={cell.resultat![indicator.key]}
                          label={FACT_SHEET.labels[indicator.labelKey]}
                          unit={indicator.unit}
                          year={row.annee}
                          explanation={explanations[indicator.explanationId]}
                          glossaryTermId={indicator.explanationId}
                          absenceExplanation={absence}
                          source={cell.resultat!.source}
                          onExplain={onExplain}
                        />
                      ))}
                    </dl>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
