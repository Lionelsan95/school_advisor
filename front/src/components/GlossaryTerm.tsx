import { useState } from "react";
import { useGlossaryTerm } from "../context/GlossaryContext";
import { GLOSSARY } from "../content/copy";
import { ExplanationPanel } from "./ExplanationPanel";
import { glossarySections } from "./explanationSections";
import styles from "./GlossaryTerm.module.css";

/**
 * FE-7 — a technical term with its definition one interaction away.
 *
 * Deliberately NOT a text scanner. The obvious implementation — search rendered
 * prose for known term names and inject links — was rejected: it would put
 * generated markup inside human-reviewed editorial content, which is precisely
 * the drift the review gate exists to prevent, and it would link the same word
 * differently depending on where it happened to appear.
 *
 * Instead the enumerable call sites are wrapped explicitly: indicator labels,
 * `filieres`, `sections`, `type_indicateur`. A term is linked because someone
 * decided it should be, not because a regexp matched.
 *
 * If the glossary could not be fetched, the label renders as plain text. A
 * definition is an aid; its absence must never withhold a figure.
 */
export function GlossaryTerm({
  termId,
  children,
}: {
  termId: string;
  children: React.ReactNode;
}) {
  const term = useGlossaryTerm(termId);
  const [open, setOpen] = useState(false);

  if (!term) return <>{children}</>;

  return (
    <>
      <button
        type="button"
        className={styles.trigger}
        onClick={() => setOpen(true)}
        aria-label={GLOSSARY.defineTerm(term.terme)}
      >
        {children}
        <span aria-hidden="true" className={styles.marker}>
          ⓘ
        </span>
      </button>
      {open && (
        <ExplanationPanel
          title={term.terme}
          sections={glossarySections(term)}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
