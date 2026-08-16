import { ApiError } from "../api/client";
import { ERRORS } from "../content/copy";
import styles from "./ErrorState.module.css";

/**
 * Explains why nothing is shown, in the terms the API contract distinguishes.
 *
 * A 503 here is not a crash: it means the API holds data but not its
 * provenance and withheld it deliberately. Presenting that as a technical
 * failure would misdescribe an editorial decision — the same mistake the
 * assistant's refusal-vs-outage distinction exists to avoid.
 */
export function ErrorState({ error }: { error: Error }) {
  const api = error instanceof ApiError ? error : null;

  let title = ERRORS.genericTitle;
  let body = ERRORS.genericBody;
  let tone = styles.technical;

  if (api?.isNotFound) {
    title = ERRORS.notFoundTitle;
    body = ERRORS.notFoundBody;
    tone = styles.informational;
  } else if (api?.isBadRequest) {
    title = ERRORS.badRequestTitle;
    body = ERRORS.badRequestBody;
    tone = styles.informational;
  } else if (api?.isProvenanceWithheld) {
    title = ERRORS.provenanceTitle;
    body = ERRORS.provenanceBody;
    tone = styles.informational;
  }

  return (
    <div className={`${styles.state} ${tone}`} role="alert">
      <h2 className={styles.title}>{title}</h2>
      <p className={styles.body}>{body}</p>
    </div>
  );
}
