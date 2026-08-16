import type { Explanation, Figure as FigureData, Source } from "../api/types";
import { FACT_SHEET } from "../content/copy";
import { SourceLink } from "./SourceLink";
import styles from "./Figure.module.css";

/**
 * The only component allowed to render a numeric result anywhere in this app.
 *
 * Its props are the enforcement mechanism, not its implementation:
 *
 *   - There is no `variant`, `tone`, `status` or `emphasis` prop. Nothing can
 *     be passed in to mean "good" or "bad", so a value cannot be coloured by
 *     its magnitude even by mistake. The one conditional inside is
 *     `valeur === null`, which is about presence, never about size or sign.
 *   - `source` is required. There is no code path that renders a number
 *     without its provenance beside it, which is the API's own invariant
 *     carried into the UI.
 *   - `explanation` is a block returned by the API, never a string written
 *     here. The component cannot render a sentence the backend has not
 *     already reviewed — which is what makes it structurally unable to
 *     attribute a cause to an absence.
 *   - `year` is required. A figure without its session is untraceable, and
 *     docs/14 §14 question 4 forbids hiding the year.
 */
export interface FigureProps {
  figure: FigureData;
  label: string;
  unit?: string;
  year: number;
  /** The static block explaining this indicator, from `FactSheet.explications`. */
  explanation: Explanation;
  /** The block explaining what an absent value means, from the same source. */
  absenceExplanation: Explanation;
  source: Source;
  onExplain: (explanation: Explanation) => void;
}

/**
 * Formats a number for display, keeping the sign when there is one.
 *
 * The sign is part of the data and is always shown for value-added figures
 * (docs/14 §5) — but it carries no colour, which is the point of the rule.
 */
function formatValue(value: number, unit?: string): string {
  const formatted = value.toLocaleString("fr-FR", {
    maximumFractionDigits: 1,
    signDisplay: unit === FACT_SHEET.units.points ? "always" : "auto",
  });
  return unit ? `${formatted} ${unit}` : formatted;
}

export function Figure({
  figure,
  label,
  unit,
  year,
  explanation,
  absenceExplanation,
  source,
  onExplain,
}: FigureProps) {
  const isAbsent = figure.valeur === null;
  const describedBy = `${explanation.content_id}-${year}-desc`;

  return (
    <div className={styles.figure}>
      <dt className={styles.label}>
        {label}
        <button
          type="button"
          className={styles.explainButton}
          onClick={() => onExplain(isAbsent ? absenceExplanation : explanation)}
          aria-label={`${FACT_SHEET.explainAction} : ${label}`}
        >
          {FACT_SHEET.explainAction}
        </button>
      </dt>

      <dd className={styles.value} aria-describedby={describedBy}>
        {isAbsent ? (
          // An absence is stated, never styled as a negative result and never
          // rendered as a bare dash — docs/14 §6 forbids both.
          <span className={styles.absent}>
            <span aria-hidden="true">—</span>
            <span className={styles.absentText}>{absenceExplanation.titre}</span>
          </span>
        ) : (
          <span className={styles.number}>{formatValue(figure.valeur!, unit)}</span>
        )}

        {figure.calcule && figure.note_de_calcul !== null && (
          <span className={styles.computed} title={figure.note_de_calcul}>
            {FACT_SHEET.computedBadge}
          </span>
        )}
      </dd>

      {/* No visually-hidden restatement of the absence here: the visible text
          above already says it, and duplicating it made a screen reader
          announce "Valeur non disponible" twice. */}
      <p id={describedBy} className={styles.provenance}>
        <SourceLink source={source} year={year} />
      </p>
    </div>
  );
}
