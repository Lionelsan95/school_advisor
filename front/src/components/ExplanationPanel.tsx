import { useEffect, useRef } from "react";
import { FACT_SHEET } from "../content/copy";
import styles from "./ExplanationPanel.module.css";

/**
 * Renders a titled set of explanatory sections.
 *
 * Takes already-assembled [heading, body] pairs rather than an `Explanation`,
 * so an indicator block and a glossary term can share one panel instead of two
 * components with the same CSS drifting apart. Callers supply the headings from
 * `copy.ts`; this component chooses layout and never wording.
 *
 * Every body string comes from the API.
 */
export function ExplanationPanel({
  title,
  sections,
  onClose,
}: {
  title: string;
  /** [heading, body] pairs. A null body is skipped. */
  sections: Array<[string, string | null]>;
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

  return (
    <div
      className={styles.panel}
      role="dialog"
      aria-modal="true"
      aria-labelledby="explanation-title"
    >
      <div className={styles.header}>
        <h2 id="explanation-title" className={styles.title}>
          {title}
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
