import styles from "./ScopeDisclaimer.module.css";

/**
 * FE-3 / F7 — the permanent scope reminder.
 *
 * The text always comes from the API (`rappel_de_portee`), never from this
 * file: it is reviewed editorial content on the backend, and re-authoring it
 * here would create a second copy that could drift out of review.
 *
 * Not dismissible. docs/14 §7 requires that this reminder can never be closed
 * permanently and is never presented as an error, so there is no close button
 * and no dismissed state to persist — the component has nowhere to store one.
 */
export function ScopeDisclaimer({ text }: { text: string }) {
  return (
    <aside className={styles.disclaimer} aria-label="Portée des données">
      <p className={styles.text}>{text}</p>
    </aside>
  );
}
