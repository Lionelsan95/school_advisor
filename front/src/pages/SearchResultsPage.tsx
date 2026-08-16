import { Link, useSearchParams } from "react-router-dom";
import { searchEstablishments } from "../api/establishments";
import type { SearchHit, SearchParams } from "../api/types";
import { ErrorState } from "../components/ErrorState";
import { ScopeDisclaimer } from "../components/ScopeDisclaimer";
import { SearchBar } from "../components/SearchBar";
import { SEARCH } from "../content/copy";
import { useApiResource } from "../hooks/useApiResource";
import styles from "./SearchResultsPage.module.css";

/**
 * FE-1 — the filtered, factual list.
 *
 * There is no sort control on this page, and deliberately not a disabled or
 * "coming soon" one either. The API refuses any sort parameter with a 400, and
 * offering the affordance at all would create a state that could later regress
 * into ordering by a result. The ordering the API applied is instead *stated*,
 * so the reader never has to infer it.
 *
 * Result rows carry no figure — see `SearchHit`. That is what makes it
 * impossible for this list to be read, or styled, as a ranking.
 */
const FILTER_KEYS = [
  "q",
  "type",
  "secteur",
  "filiere",
  "code_commune",
  "code_postal",
  "rayon_km",
] as const;

function toParams(search: URLSearchParams): SearchParams {
  const params: SearchParams = { limit: 20 };
  for (const key of FILTER_KEYS) {
    const value = search.get(key);
    if (value) (params as Record<string, string>)[key] = value;
  }
  return params;
}

function ResultCard({ hit }: { hit: SearchHit }) {
  return (
    <li className={styles.card}>
      <h3 className={styles.cardTitle}>
        <Link to={`/etablissements/${hit.uai}`}>{hit.nom}</Link>
      </h3>
      <p className={styles.cardMeta}>
        {[hit.commune, hit.code_postal].filter(Boolean).join(" · ")}
        {hit.distance_km !== null && ` · ${SEARCH.distance(hit.distance_km)}`}
      </p>
      <p className={styles.cardMeta}>
        {[hit.type, hit.statut_public_prive].filter(Boolean).join(" · ")}
        {hit.filieres.length > 0 && ` · ${hit.filieres.join(", ")}`}
      </p>
    </li>
  );
}

export function SearchResultsPage() {
  const [search, setSearch] = useSearchParams();
  const params = toParams(search);
  const resource = useApiResource(
    (signal) => searchEstablishments(params, signal),
    search.toString(),
  );

  const removeFilter = (key: string) => {
    const next = new URLSearchParams(search);
    next.delete(key);
    setSearch(next);
  };

  return (
    <main className={styles.page}>
      <SearchBar
        defaultValue={search.get("q") ?? ""}
        onSubmit={(q) => setSearch(q ? { q } : {})}
      />

      {resource.state === "loading" && <p role="status">{SEARCH.loading}</p>}

      {resource.state === "error" && <ErrorState error={resource.error} />}

      {resource.state === "success" && (
        <>
          <ScopeDisclaimer text={resource.data.rappel_de_portee} />

          <div className={styles.criteria}>
            <h2 className={styles.criteriaHeading}>{SEARCH.filtersHeading}</h2>
            <ul className={styles.chips}>
              {FILTER_KEYS.filter((key) => search.get(key)).map((key) => (
                <li key={key}>
                  <button
                    type="button"
                    className={styles.chip}
                    onClick={() => removeFilter(key)}
                    aria-label={SEARCH.removeFilter(
                      `${SEARCH.filterLabels[key] ?? key} : ${search.get(key)}`,
                    )}
                  >
                    {SEARCH.filterLabels[key] ?? key}: {search.get(key)}
                    <span aria-hidden="true"> ×</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <h2 className={styles.heading}>{SEARCH.heading}</h2>
          <p className={styles.count}>
            {resource.data.nombre_total === 1
              ? SEARCH.countOne
              : SEARCH.countMany(resource.data.nombre_total)}{" "}
            {/* State the ordering rather than let the reader infer it. */}
            <span className={styles.sort}>
              {SEARCH.sortExplained[resource.data.tri]}
            </span>
          </p>

          {resource.data.resultats.length === 0 ? (
            <div className={styles.empty}>
              <h3>{SEARCH.emptyTitle}</h3>
              <p>{SEARCH.emptyBody}</p>
            </div>
          ) : (
            <ul className={styles.results}>
              {resource.data.resultats.map((hit) => (
                <ResultCard key={hit.uai} hit={hit} />
              ))}
            </ul>
          )}
        </>
      )}
    </main>
  );
}
