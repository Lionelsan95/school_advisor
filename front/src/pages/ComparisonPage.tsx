import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { compareEstablishments } from "../api/establishments";
import type { Explanation } from "../api/types";
import { ComparisonTable } from "../components/ComparisonTable";
import { ErrorState } from "../components/ErrorState";
import { ExplanationPanel } from "../components/ExplanationPanel";
import { ScopeDisclaimer } from "../components/ScopeDisclaimer";
import { COMPARE, SEARCH } from "../content/copy";
import { useApiResource } from "../hooks/useApiResource";
import styles from "./ComparisonPage.module.css";

/**
 * FE-5 / F4 — two establishments side by side.
 *
 * There is no summary, no conclusion and no "which is better" affordance
 * anywhere on this page, and the response it renders contains nothing from
 * which one could be derived.
 */
export function ComparisonPage() {
  const [search] = useSearchParams();
  const [openExplanation, setOpenExplanation] = useState<Explanation | null>(null);
  const uais = search.getAll("uai");

  const resource = useApiResource(
    (signal) => compareEstablishments(uais, signal),
    uais.join(","),
  );

  if (uais.length !== 2) {
    return (
      <main className={styles.page}>
        <h1 className={styles.title}>{COMPARE.heading}</h1>
        <div className={styles.empty}>
          <p>{COMPARE.needTwo}</p>
        </div>
      </main>
    );
  }

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

  const comparison = resource.data;

  return (
    <main className={styles.page}>
      <h1 className={styles.title}>{COMPARE.heading}</h1>
      <p className={styles.intro}>{COMPARE.intro}</p>

      <ScopeDisclaimer text={comparison.rappel_de_portee} />

      <ComparisonTable
        establishments={comparison.etablissements}
        rows={comparison.lignes}
        explanations={comparison.explications}
        onExplain={setOpenExplanation}
      />

      {openExplanation && (
        <ExplanationPanel
          explanation={openExplanation}
          onClose={() => setOpenExplanation(null)}
        />
      )}
    </main>
  );
}
