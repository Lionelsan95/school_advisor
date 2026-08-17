import { useState } from "react";
import { SHARE } from "../content/copy";
import styles from "./ShareActions.module.css";

/**
 * F8 — share a stable link, or print the page to PDF.
 *
 * The labels say what actually happens. "Imprimer / Enregistrer en PDF" opens
 * the browser's print dialog; promising a one-click download would be a small
 * lie about a mechanism the reader is about to see for themselves.
 *
 * The link shared is the page's own canonical URL, which is already stable and
 * already carries everything needed to reproduce the view.
 */
export function ShareActions({ label }: { label: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 4000);
    } catch {
      // Clipboard access can be refused; the URL is in the address bar either
      // way, so this is not worth an error state.
      setCopied(false);
    }
  };

  return (
    <div className={`${styles.actions} no-print`} aria-label={label}>
      <button type="button" className={styles.button} onClick={copy}>
        {copied ? SHARE.copied : SHARE.copyLink}
      </button>
      <button
        type="button"
        className={styles.button}
        onClick={() => window.print()}
      >
        {SHARE.print}
      </button>
    </div>
  );
}
