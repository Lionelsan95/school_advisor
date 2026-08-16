import type { Source } from "../api/types";
import { A11Y, FACT_SHEET, SOURCE_LINE } from "../content/copy";

/**
 * Provenance for a figure (F10).
 *
 * Every number shown by this product traces to an official dataset, a
 * documented calculation, or reviewed static content. This renders the first
 * case, and is a required prop of `Figure` so no figure can appear without it.
 */
export function SourceLink({ source, year }: { source: Source; year: number }) {
  const published = source.date_publication
    ? new Date(source.date_publication).toLocaleDateString("fr-FR")
    : null;

  return (
    <>
      <span>{SOURCE_LINE.session(year)}</span>
      <a href={source.url} target="_blank" rel="noopener noreferrer">
        {FACT_SHEET.sourceLink}
        <span className="visually-hidden"> ({A11Y.externalLink})</span>
      </a>
      {published && <span>{SOURCE_LINE.published(published)}</span>}
    </>
  );
}
