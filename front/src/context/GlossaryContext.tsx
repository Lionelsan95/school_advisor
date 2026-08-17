import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { getGlossary } from "../api/glossary";
import type { GlossaryTerm } from "../api/types";

/**
 * The glossary, fetched once and shared with the whole tree.
 *
 * Fetched whole rather than a request per term: it is a few dozen short
 * entries, and shipping it once is what lets a term be linked inline wherever
 * it appears without a round trip.
 *
 * Not persisted. Like the comparison selection, this is interface state — and
 * the glossary is content the API owns, so caching it across sessions would
 * mean a reader could see a definition the backend has since revised, silently
 * outside the review gate.
 *
 * A failed fetch is deliberately not an error state. A missing definition must
 * never stop a figure from being shown: `GlossaryTerm` then renders its label
 * as plain text, which is exactly the pre-glossary behaviour.
 */
const GlossaryMapContext = createContext<Map<string, GlossaryTerm>>(new Map());

export function GlossaryProvider({ children }: { children: ReactNode }) {
  const [terms, setTerms] = useState<Map<string, GlossaryTerm>>(new Map());

  useEffect(() => {
    const controller = new AbortController();
    getGlossary(controller.signal)
      .then((response) => {
        setTerms(new Map(response.termes.map((term) => [term.term_id, term])));
      })
      .catch(() => {
        // Silent by design — see the note above.
      });
    return () => controller.abort();
  }, []);

  return (
    <GlossaryMapContext.Provider value={terms}>{children}</GlossaryMapContext.Provider>
  );
}

export function useGlossaryTerm(termId: string | undefined): GlossaryTerm | undefined {
  const terms = useContext(GlossaryMapContext);
  return termId ? terms.get(termId) : undefined;
}
