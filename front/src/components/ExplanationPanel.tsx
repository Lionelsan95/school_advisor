import { useEffect, useRef } from "react";
import type { Explanation } from "../api/types";
import { EXPLANATION_SECTIONS, FACT_SHEET } from "../content/copy";
import styles from "./ExplanationPanel.module.css";

/**
 * Renders one static explanatory block in the six parts docs/14 §4 requires.
 *
 * Every string displayed comes from the API. This component chooses layout,
 * never wording — the headings below are the only text it contributes, and
 * they are structural labels rather than commentary on any value.
 */
export function ExplanationPanel({
  explanation,
  onClose,
}: {
  explanation: Explanation;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const sections: Array<[string, string | null]> = [
    [EXPLANATION_SECTIONS.definition, explanation.definition_simple],
    [EXPLANATION_SECTIONS.howToRead, explanation.comment_lire],
    [EXPLANATION_SECTIONS.measures, explanation.ce_que_cela_mesure],
    [EXPLANATION_SECTIONS.doesNotMeasure, explanation.ce_que_cela_ne_mesure_pas],
    [EXPLANATION_SECTIONS.method, explanation.methode],
    [EXPLANATION_SECTIONS.source, explanation.source],
  ];

  return (
    <div
      className={styles.panel}
      role="dialog"
      aria-modal="true"
      aria-labelledby="explanation-title"
    >
      <div className={styles.header}>
        <h2 id="explanation-title" className={styles.title}>
          {explanation.titre}
        </h2>
        <button
          ref={closeRef}
          type="button"
          className={styles.close}
          onClick={onClose}
        >
          {FACT_SHEET.explainClose}
        </button>
      </div>

      {sections.map(([heading, body]) =>
        body ? (
          <section key={heading} className={styles.section}>
            <h3 className={styles.sectionTitle}>{heading}</h3>
            <p className={styles.sectionBody}>{body}</p>
          </section>
        ) : null,
      )}
    </div>
  );
}
