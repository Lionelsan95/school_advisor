import { useState } from "react";
import { getGlossary } from "../api/glossary";
import { ErrorState } from "../components/ErrorState";
import { ScopeDisclaimer } from "../components/ScopeDisclaimer";
import { GLOSSARY, SEARCH } from "../content/copy";
import { useApiResource } from "../hooks/useApiResource";
import styles from "./GlossaryPage.module.css";

/**
 * FE-7 / F9 — every term the interface uses, defined in one place.
 *
 * Terms are alphabetical. Nothing here is ordered by importance, and no term
 * is highlighted over another: a glossary that promotes some entries starts
 * telling the reader what matters.
 */
export function GlossaryPage() {
  const [query, setQuery] = useState("");
  const resource = useApiResource((signal) => getGlossary(signal), "glossary");

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

  const normalised = query.trim().toLowerCase();
  const terms = normalised
    ? resource.data.termes.filter(
        (term) =>
          term.terme.toLowerCase().includes(normalised) ||
          term.definition.toLowerCase().includes(normalised),
      )
    : resource.data.termes;

  const byId = new Map(resource.data.termes.map((term) => [term.term_id, term]));

  return (
    <main className={styles.page}>
      <h1 className={styles.title}>{GLOSSARY.heading}</h1>
      <p className={styles.intro}>{GLOSSARY.intro}</p>

      <ScopeDisclaimer text={resource.data.rappel_de_portee} />

      <label className={styles.searchLabel} htmlFor="glossary-search">
        {GLOSSARY.filterLabel}
      </label>
      <input
        id="glossary-search"
        className={styles.search}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />

      {terms.length === 0 ? (
        <p className={styles.empty}>{GLOSSARY.noMatch}</p>
      ) : (
        <dl className={styles.list}>
          {terms.map((term) => (
            <div key={term.term_id} id={term.term_id} className={styles.entry}>
              <dt className={styles.term}>{term.terme}</dt>
              <dd className={styles.body}>
                <p className={styles.definition}>{term.definition}</p>
                {term.exemple && <p className={styles.example}>{term.exemple}</p>}
                <p className={styles.source}>{term.source}</p>
                {term.termes_associes.length > 0 && (
                  <p className={styles.related}>
                    {GLOSSARY.related}{" "}
                    {term.termes_associes.map((id, index) => (
                      <span key={id}>
                        {index > 0 && ", "}
                        <a href={`#${id}`}>{byId.get(id)?.terme ?? id}</a>
                      </span>
                    ))}
                  </p>
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </main>
  );
}
