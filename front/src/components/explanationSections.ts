import type { Explanation, GlossaryTerm } from "../api/types";
import { EXPLANATION_SECTIONS, GLOSSARY } from "../content/copy";

/**
 * Adapters turning API content into the panel's [heading, body] pairs.
 *
 * Kept beside the panel so the six-part order the charter (§4) prescribes is
 * declared once, rather than at every call site where it could drift.
 */
export function explanationSections(
  block: Explanation,
): Array<[string, string | null]> {
  return [
    [EXPLANATION_SECTIONS.definition, block.definition_simple],
    [EXPLANATION_SECTIONS.howToRead, block.comment_lire],
    [EXPLANATION_SECTIONS.measures, block.ce_que_cela_mesure],
    [EXPLANATION_SECTIONS.doesNotMeasure, block.ce_que_cela_ne_mesure_pas],
    [EXPLANATION_SECTIONS.method, block.methode],
    [EXPLANATION_SECTIONS.source, block.source],
  ];
}

export function glossarySections(
  term: GlossaryTerm,
): Array<[string, string | null]> {
  return [
    [EXPLANATION_SECTIONS.definition, term.definition],
    [GLOSSARY.exampleHeading, term.exemple],
    [EXPLANATION_SECTIONS.source, term.source],
  ];
}
