/**
 * All French user-facing wording authored by the frontend.
 *
 * **This file is editorial content, not code that may be freely edited.**
 * Like `back/src/domain/explanatory_content.py`, any change requires the
 * explicit human review CLAUDE.md mandates for user-facing copy, before
 * commit. Keeping every string here — rather than inline in JSX — is what
 * makes that review possible at all, and what lets the neutrality test scan a
 * single surface.
 *
 * What is NOT here, on purpose: anything the API already returns. The scope
 * disclaimer, the indicator explanations, the absence wording and the
 * assistant's messages are static content that has already been reviewed on
 * the backend. The frontend renders them; it must never re-author them, or the
 * two would drift and only one would be under review.
 *
 * Voice, per docs/14 §2: factual, pedagogical, precise, calm, transparent
 * about limits. Never promotional, prescriptive, alarmist or falsely certain.
 * No evaluative wording anywhere — `tests/neutrality.test.ts` enforces this
 * against the same forbidden-word list the backend uses.
 */

export const SITE = {
  name: "Établissements en clair",
  tagline: "Comprendre les données publiques sur les établissements scolaires",
};

export const NAV = {
  search: "Rechercher",
  understand: "Comprendre les données",
  glossary: "Glossaire",
  methodology: "À propos des données",
  skipToContent: "Aller au contenu principal",
};

export const HOME = {
  title: "Comprendre les données officielles des établissements scolaires",
  intro:
    "Ce service présente et explique des données publiques officielles. " +
    "Il ne classe pas les établissements et ne recommande aucun choix.",
  searchLabel: "Rechercher un établissement",
  searchHint:
    "Par nom, commune, code postal ou identifiant UAI. Exemple : « collège à Abbeville ».",
  searchPlaceholder: "Nom, commune, code postal ou UAI",
  submit: "Rechercher",
  commitmentsTitle: "Ce que fait ce service",
  commitments: [
    {
      title: "Des données officielles",
      body:
        "Chaque chiffre provient d'un jeu de données publié par le ministère " +
        "de l'Éducation nationale, avec sa date de publication et un lien vers " +
        "la source.",
    },
    {
      title: "Des indicateurs expliqués",
      body:
        "Chaque indicateur est accompagné de ce qu'il mesure, de ce qu'il ne " +
        "mesure pas, et de sa méthode de calcul.",
    },
    {
      title: "Aucun classement",
      body:
        "Les résultats ne sont jamais ordonnés par valeur, ni comparés pour " +
        "désigner un établissement plutôt qu'un autre.",
    },
  ],
};

export const SEARCH = {
  heading: "Résultats",
  countOne: "1 établissement correspond à votre recherche.",
  countMany: (n: number) => `${n} établissements correspondent à votre recherche.`,
  showing: (shown: number, total: number) =>
    `${shown} affichés sur ${total}.`,
  sortLabel: "Ordre d'affichage",
  sortExplained: {
    correspondance: "Par correspondance avec votre recherche.",
    correspondance_puis_proximite:
      "Par correspondance avec votre recherche, puis par proximité.",
    proximite: "Par distance depuis le point indiqué.",
    alphabetique: "Par commune, puis par nom.",
  },
  filtersHeading: "Critères appliqués",
  removeFilter: (label: string) => `Retirer le critère : ${label}`,
  clearFilters: "Retirer tous les critères",
  viewSheet: "Voir la fiche",
  loading: "Recherche en cours…",
  emptyTitle: "Aucun établissement ne correspond à ces critères",
  emptyBody:
    "Vous pouvez élargir la zone de recherche, retirer un critère, ou " +
    "vérifier l'orthographe du nom ou de la commune.",
  distance: (km: number) => `à ${km.toLocaleString("fr-FR")} km`,
  filterLabels: {
    q: "Recherche",
    type: "Type",
    secteur: "Statut",
    filiere: "Filière",
    code_commune: "Commune",
    code_postal: "Code postal",
    rayon_km: "Rayon",
  } as Record<string, string>,
};

export const FACT_SHEET = {
  identityHeading: "Identité de l'établissement",
  resultsHeading: "Indicateurs de résultats",
  sitesHeading: "Sites de cet établissement",
  multiSiteNote:
    "Cet établissement occupe plusieurs sites publiés sous le même " +
    "identifiant. Les indicateurs portent sur l'ensemble.",
  yearLabel: (year: number) => `Session ${year}`,
  candidates: (n: number) => `${n.toLocaleString("fr-FR")} candidats présents`,
  explainAction: "Comprendre cet indicateur",
  explainClose: "Fermer l'explication",
  noResultsTitle: "Aucun indicateur de résultats pour cet établissement",
  noResultsBody:
    "Les indicateurs de valeur ajoutée ne sont publiés que pour les collèges " +
    "et les lycées. Les autres établissements figurent dans l'annuaire sans " +
    "résultats d'examen.",
  lastSync: (date: string) => `Dernière synchronisation : ${date}`,
  sourceLink: "Consulter la source officielle",
  computedBadge: "Calculé par ce service",
  labels: {
    taux_reussite: "Taux de réussite",
    taux_reussite_attendu: "Taux attendu",
    valeur_ajoutee_reussite: "Valeur ajoutée (réussite)",
    taux_acces: "Taux d'accès",
    valeur_ajoutee_acces: "Valeur ajoutée (accès)",
    taux_mention: "Taux de mention",
    valeur_ajoutee_mention: "Valeur ajoutée (mention)",
  },
  units: {
    rate: "%",
    points: "points",
  },
};

export const ERRORS = {
  genericTitle: "Les données n'ont pas pu être affichées",
  genericBody:
    "Une difficulté technique empêche l'affichage. Vous pouvez réessayer.",
  retry: "Réessayer",
  notFoundTitle: "Établissement introuvable",
  notFoundBody:
    "Aucun établissement ne correspond à cet identifiant dans l'annuaire " +
    "officiel. Il a pu fermer, ou l'identifiant est inexact.",
  badRequestTitle: "Identifiant non valide",
  badRequestBody:
    "Cet identifiant ne correspond pas au format d'un UAI (sept chiffres " +
    "suivis d'une lettre).",
  provenanceTitle: "Données non publiées faute de provenance",
  provenanceBody:
    "Le service dispose de ces données mais pas de leur source. Elles ne sont " +
    "pas affichées, afin de ne présenter aucun chiffre sans origine vérifiable.",
};

/**
 * Section headings for an explanatory block. Structural labels only — the
 * bodies always come from the API. Named after the six parts docs/14 §4
 * requires, so the panel's structure is auditable against the charter.
 */
export const EXPLANATION_SECTIONS = {
  definition: "Définition",
  howToRead: "Comment lire cette valeur",
  measures: "Ce que cela mesure",
  doesNotMeasure: "Ce que cela ne mesure pas",
  method: "Méthode",
  source: "Source et millésime",
};

export const SOURCE_LINE = {
  session: (year: number) => `Session ${year} · `,
  published: (date: string) => ` · publiée le ${date}`,
};

export const A11Y = {
  loading: "Chargement en cours",
  externalLink: "Ouvre un nouvel onglet",
  absentValue: "Valeur non disponible",
};

/**
 * History chart (F5). Titles are descriptive, never conclusive: the charter
 * (§10) rules out a heading that states what the series shows ("progression",
 * "amélioration") rather than what it is.
 */
export const HISTORY = {
  heading: "Évolution année par année",
  seriesLabel: "Indicateur affiché",
  year: "Année",
  notPublished: "Non publiée",
  noSeriesData: "Aucune valeur publiée pour cet indicateur.",
  chartTitle: (label: string, from: number, to: number) =>
    `${label}, de ${from} à ${to}`,
  tableCaption: (label: string) => `Valeurs exactes — ${label}`,
  coverage: (from: number, to: number) => `Valeurs disponibles de ${from} à ${to}.`,
  breakHeading: "Changement de méthode",
  backToSheet: "Revenir à la fiche",
};

/**
 * Comparison (F4). Charter §11: "comparaison" means placing data in parallel,
 * not evaluating it. Nothing here summarises, concludes or names a preference,
 * and no string below refers to a difference between the two columns.
 */
export const COMPARE = {
  heading: "Comparaison",
  intro:
    "Les données des deux établissements sont présentées côte à côte, année " +
    "par année. Aucun écart n'est calculé et aucun établissement n'est " +
    "désigné.",
  add: "Ajouter à la comparaison",
  remove: "Retirer de la comparaison",
  selectedCount: (n: number) => `${n} établissement(s) sélectionné(s) sur 2`,
  open: "Voir la comparaison",
  clear: "Vider la sélection",
  needTwo: "Sélectionnez deux établissements pour les comparer.",
  yearColumn: "Année",
};

/** Glossary (F9). Definitions come from the API; these are the page's chrome. */
export const GLOSSARY = {
  heading: "Glossaire",
  intro:
    "Les termes employés dans ce service, définis à partir des publications " +
    "officielles.",
  filterLabel: "Filtrer les termes",
  noMatch: "Aucun terme ne correspond à cette recherche.",
  related: "Voir aussi :",
};

/**
 * Share and export (F8). The labels describe the actual mechanism: printing
 * opens the browser dialog, and the "link" is the page's own stable URL.
 */
export const SHARE = {
  label: "Partager ou exporter",
  copyLink: "Copier le lien",
  copied: "Lien copié",
  print: "Imprimer ou enregistrer en PDF",
  printedOn: (date: string) => `Page consultée le ${date}.`,
  explanationsHeading: "Définitions des indicateurs",
};
