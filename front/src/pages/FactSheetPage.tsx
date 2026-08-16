import { useState } from "react";
import { useParams } from "react-router-dom";
import { getFactSheet } from "../api/establishments";
import type { Explanation, ResultYear } from "../api/types";
import { ErrorState } from "../components/ErrorState";
import { ExplanationPanel } from "../components/ExplanationPanel";
import { Figure } from "../components/Figure";
import { ScopeDisclaimer } from "../components/ScopeDisclaimer";
import { FACT_SHEET, SEARCH } from "../content/copy";
import { useApiResource } from "../hooks/useApiResource";
import styles from "./FactSheetPage.module.css";

/**
 * FE-2 — the full fact sheet.
 *
 * Years are rendered in the order the API returned them (most recent first).
 * Nothing here re-sorts, aggregates or compares: the page is a faithful
 * rendering of one establishment's published record.
 */

/** Which indicators a year block shows, and which explanation each maps to. */
const INDICATORS: Array<{
  key: keyof Pick<
    ResultYear,
    | "taux_reussite"
    | "taux_reussite_attendu"
    | "valeur_ajoutee_reussite"
    | "taux_acces"
    | "valeur_ajoutee_acces"
    | "taux_mention"
    | "valeur_ajoutee_mention"
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
    key: "valeur_ajoutee_acces",
    labelKey: "valeur_ajoutee_acces",
    explanationId: "valeur_ajoutee",
    unit: FACT_SHEET.units.points,
  },
  {
    key: "taux_mention",
    labelKey: "taux_mention",
    explanationId: "taux_mention",
    unit: FACT_SHEET.units.rate,
  },
  {
    key: "valeur_ajoutee_mention",
    labelKey: "valeur_ajoutee_mention",
    explanationId: "valeur_ajoutee",
    unit: FACT_SHEET.units.points,
  },
];

export function FactSheetPage() {
  const { uai = "" } = useParams();
  const [openExplanation, setOpenExplanation] = useState<Explanation | null>(null);
  const resource = useApiResource((signal) => getFactSheet(uai, signal), uai);

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

  const sheet = resource.data;
  const absence = sheet.explications.valeur_non_disponible;

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>{sheet.identite.nom}</h1>
        <p className={styles.meta}>
          {[
            sheet.identite.adresse,
            sheet.identite.code_postal,
            sheet.identite.commune,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
        <p className={styles.meta}>
          {[sheet.identite.type, sheet.identite.statut_public_prive]
            .filter(Boolean)
            .join(" · ")}
          {sheet.identite.filieres.length > 0 &&
            ` · ${sheet.identite.filieres.join(", ")}`}
          {sheet.identite.sections.length > 0 &&
            ` · ${sheet.identite.sections.join(", ")}`}
        </p>
      </header>

      <ScopeDisclaimer text={sheet.rappel_de_portee} />

      {sheet.identite.sites.length > 1 && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>{FACT_SHEET.sitesHeading}</h2>
          <p className={styles.note}>{FACT_SHEET.multiSiteNote}</p>
          <ul>
            {sheet.identite.sites.map((site, index) => (
              <li key={`${site.nom}-${index}`}>
                {[site.nom, site.adresse, site.code_postal, site.commune]
                  .filter(Boolean)
                  .join(" · ")}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>{FACT_SHEET.resultsHeading}</h2>

        {sheet.resultats.length === 0 ? (
          <div className={styles.empty}>
            <h3>{FACT_SHEET.noResultsTitle}</h3>
            <p>{FACT_SHEET.noResultsBody}</p>
          </div>
        ) : (
          sheet.resultats.map((year) => (
            <article
              key={`${year.annee}-${year.type_indicateur}`}
              className={styles.year}
            >
              <h3 className={styles.yearTitle}>
                {FACT_SHEET.yearLabel(year.annee)}
                <span className={styles.yearMeta}>
                  {year.type_indicateur}
                  {year.candidats_presents !== null &&
                    ` · ${FACT_SHEET.candidates(year.candidats_presents)}`}
                </span>
              </h3>
              <dl className={styles.figures}>
                {INDICATORS.map((indicator) => (
                  <Figure
                    key={indicator.key}
                    figure={year[indicator.key]}
                    label={FACT_SHEET.labels[indicator.labelKey]}
                    unit={indicator.unit}
                    year={year.annee}
                    explanation={sheet.explications[indicator.explanationId]}
                    absenceExplanation={absence}
                    source={year.source}
                    onExplain={setOpenExplanation}
                  />
                ))}
              </dl>
            </article>
          ))
        )}
      </section>

      {sheet.derniere_synchronisation && (
        <p className={styles.sync}>
          {FACT_SHEET.lastSync(
            new Date(sheet.derniere_synchronisation).toLocaleDateString("fr-FR"),
          )}
        </p>
      )}

      {openExplanation && (
        <ExplanationPanel
          explanation={openExplanation}
          onClose={() => setOpenExplanation(null)}
        />
      )}
    </main>
  );
}
