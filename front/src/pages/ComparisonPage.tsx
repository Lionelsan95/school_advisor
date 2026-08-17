import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { compareEstablishments } from "../api/establishments";
import type { Explanation } from "../api/types";
import { ComparisonTable } from "../components/ComparisonTable";
import { ErrorState } from "../components/ErrorState";
import { ExplanationPanel } from "../components/ExplanationPanel";
import { ScopeDisclaimer } from "../components/ScopeDisclaimer";
import { ShareActions } from "../components/ShareActions";
import { COMPARE, SEARCH, SHARE } from "../content/copy";
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

      <ShareActions label={SHARE.label} />

      <ComparisonTable
        establishments={comparison.etablissements}
        rows={comparison.lignes}
        explanations={comparison.explications}
        onExplain={setOpenExplanation}
      />

      <section className="print-only">
        <h2>{SHARE.explanationsHeading}</h2>
        {Object.values(comparison.explications).map((block) => (
          // All six parts the charter (§4) requires, exactly as the fact sheet
          // prints them. An abridged version here dropped `comment_lire` and
          // `methode` — which for an absence are the sentences saying it is
          // "ni un résultat élevé, ni un résultat faible" and that no value is
          // ever substituted. Losing those is precisely the shortened export
          // F8 forbids.
          <article key={block.content_id}>
            <h3>{block.titre}</h3>
            <p>{block.definition_simple}</p>
            <p>{block.comment_lire}</p>
            <p>{block.ce_que_cela_mesure}</p>
            <p>{block.ce_que_cela_ne_mesure_pas}</p>
            {block.methode && <p>{block.methode}</p>}
            <p>{block.source}</p>
          </article>
        ))}
        <p>{SHARE.printedOn(new Date().toLocaleDateString("fr-FR"))}</p>
      </section>

      {openExplanation && (
        <ExplanationPanel
          explanation={openExplanation}
          onClose={() => setOpenExplanation(null)}
        />
      )}
    </main>
  );
}
