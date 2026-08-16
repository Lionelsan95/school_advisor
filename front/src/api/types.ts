/**
 * Types mirroring `back/src/interfaces/api/schemas.py` one-for-one.
 *
 * French keys are kept exactly as the API sends them. Renaming them here would
 * create a second vocabulary to keep in sync for no benefit — the backend
 * already decided that French is the wire format and English is the code
 * identifier, and that boundary lives on the server (see the journal entry
 * "Identifiants de code en anglais, format JSON en français").
 *
 * Nothing in the frontend may widen these types to make a computation
 * possible. In particular `SearchHit` has no result figure, by design: the API
 * withholds figures from search rows so no client can sort or colour a list by
 * them. Adding one here would defeat that at the first convenient moment.
 */

/** Provenance of a figure or a response (F10). */
export interface Source {
  dataset_id: string;
  url: string;
  derniere_synchronisation: string;
  date_publication: string | null;
}

/**
 * One number, or the documented absence of one (F6).
 *
 * `valeur === null` means the source published nothing. `explication_absence`
 * is the *id* of a static explanatory block, never a sentence: the text is
 * looked up from `FactSheet.explications`, so the UI can only ever show
 * wording the backend already vetted, and can never state a cause the source
 * did not give.
 */
export interface Figure {
  valeur: number | null;
  calcule: boolean;
  note_de_calcul: string | null;
  explication_absence: string | null;
}

/** A static explanatory block, in the six parts the editorial charter requires. */
export interface Explanation {
  content_id: string;
  version: number;
  titre: string;
  definition_simple: string;
  comment_lire: string;
  ce_que_cela_mesure: string;
  ce_que_cela_ne_mesure_pas: string;
  methode: string | null;
  source: string;
}

export interface Site {
  nom: string;
  adresse: string | null;
  code_postal: string | null;
  commune: string | null;
  code_commune: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface Identity {
  nom: string;
  type: string;
  statut_public_prive: string | null;
  adresse: string | null;
  code_postal: string | null;
  commune: string | null;
  code_departement: string | null;
  filieres: string[];
  sections: string[];
  sites: Site[];
}

export interface ResultYear {
  annee: number;
  type_indicateur: string;
  candidats_presents: number | null;
  taux_reussite: Figure;
  taux_reussite_attendu: Figure;
  valeur_ajoutee_reussite: Figure;
  taux_acces: Figure;
  valeur_ajoutee_acces: Figure;
  taux_mention: Figure;
  valeur_ajoutee_mention: Figure;
  source: Source;
}

export interface FactSheet {
  uai: string;
  identite: Identity;
  resultats: ResultYear[];
  explications: Record<string, Explanation>;
  rappel_de_portee: string;
  derniere_synchronisation: string | null;
}

/**
 * A search result row. Identity only — deliberately no figure.
 * See the docstring on `SearchHitOut` in schemas.py for why.
 */
export interface SearchHit {
  uai: string;
  nom: string;
  type: string;
  statut_public_prive: string | null;
  commune: string | null;
  code_postal: string | null;
  code_departement: string | null;
  filieres: string[];
  latitude: number | null;
  longitude: number | null;
  distance_km: number | null;
}

export interface FiltersApplied {
  q: string | null;
  code_commune: string | null;
  code_postal: string | null;
  type: string | null;
  secteur: string | null;
  filiere: string | null;
  latitude: number | null;
  longitude: number | null;
  rayon_km: number | null;
  limit: number;
  offset: number;
}

/**
 * How the API ordered the results. Descriptive of the mechanism, never a
 * judgement — and never derived from a result indicator.
 */
export type SortMode =
  | "correspondance_puis_proximite"
  | "correspondance"
  | "proximite"
  | "alphabetique";

export interface SearchResponse {
  resultats: SearchHit[];
  nombre_total: number;
  tri: SortMode;
  filtres_appliques: FiltersApplied;
  rappel_de_portee: string;
  source: Source;
}

export interface CommuneHit {
  code: string;
  nom: string;
  codes_postaux: string[];
  code_departement: string;
  latitude: number | null;
  longitude: number | null;
}

export interface CommuneSearchResponse {
  resultats: CommuneHit[];
  source: Source;
}

/** Search parameters the API accepts. There is deliberately no sort field. */
export interface SearchParams {
  q?: string;
  type?: string;
  secteur?: string;
  filiere?: string;
  code_commune?: string;
  code_postal?: string;
  lat?: number;
  lng?: number;
  rayon_km?: number;
  limit?: number;
  offset?: number;
}

/** One year of one selected indicator series, for the history chart (F5). */
export interface HistoryPoint {
  annee: number;
  valeur: number | null;
}

/**
 * A year from which a series stops being strictly comparable.
 *
 * Present only when the establishment's own history spans it. The note is
 * static reviewed content from the API — the chart must never compose its own
 * explanation of why the reader should not read across the year.
 */
export interface MethodologyBreak {
  annee: number;
  content_id: string;
  version: number;
  titre: string;
  note: string;
}

export interface HistoryResponse {
  uai: string;
  nom: string;
  points: ResultYear[];
  ruptures_methodologiques: MethodologyBreak[];
  annees_couvertes: number[];
  explications: Record<string, Explanation>;
  rappel_de_portee: string;
}

/** Which figure of a result year the chart is showing. */
export type HistorySeriesKey =
  | "taux_reussite"
  | "taux_reussite_attendu"
  | "valeur_ajoutee_reussite"
  | "taux_acces"
  | "valeur_ajoutee_acces"
  | "taux_mention"
  | "valeur_ajoutee_mention";
