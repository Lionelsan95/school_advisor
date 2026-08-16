/**
 * Fixtures shaped exactly like real API responses.
 *
 * The absent-value case is not invented: it mirrors UAI 9760127J (Mayotte,
 * 655 candidates in 2019), which publishes a success rate but no value added.
 * It is the case a threshold-based message would mislabel, and the reason the
 * absence wording says nothing about cause.
 */
import type { Explanation, FactSheet, Figure, Source } from "../src/api/types";

export const source: Source = {
  dataset_id: "fr-en-indicateurs-de-resultat-des-lycees-gt_v2",
  url: "https://data.education.gouv.fr/explore/dataset/x/information/",
  derniere_synchronisation: "2026-08-15T17:20:39.036978Z",
  date_publication: "2026-04-03",
};

export const presentFigure: Figure = {
  valeur: 94,
  calcule: false,
  note_de_calcul: null,
  explication_absence: null,
};

export const computedFigure: Figure = {
  valeur: 97,
  calcule: true,
  note_de_calcul: "Calculé par ce service : taux constaté − valeur ajoutée.",
  explication_absence: null,
};

export const absentFigure: Figure = {
  valeur: null,
  calcule: false,
  note_de_calcul: null,
  explication_absence: "valeur_non_disponible",
};

export const explanation: Explanation = {
  content_id: "taux_reussite",
  version: 1,
  titre: "Taux de réussite",
  definition_simple: "La part des élèves présents à l'examen qui l'ont obtenu.",
  comment_lire: "La valeur est exprimée en pourcentage des candidats présents.",
  ce_que_cela_mesure: "Le rapport entre diplômés et présents.",
  ce_que_cela_ne_mesure_pas: "Ce taux ne tient pas compte du profil des élèves.",
  methode: "Taux constaté = diplômés ÷ présents.",
  source: "Publié par la DEPP.",
};

export const absenceExplanation: Explanation = {
  content_id: "valeur_non_disponible",
  version: 1,
  titre: "Valeur non disponible",
  definition_simple:
    "Cette valeur n'est pas publiée dans les données officielles pour cette année.",
  comment_lire:
    "L'absence de valeur n'est pas un résultat. Elle ne signifie ni un résultat élevé, ni un résultat faible.",
  ce_que_cela_mesure: "La source publie l'absence sans en indiquer le motif.",
  ce_que_cela_ne_mesure_pas:
    "Il n'est pas possible de savoir laquelle de ces situations s'applique.",
  methode: "Aucun calcul n'est effectué pour remplacer une valeur absente.",
  source: "Conditions de publication décrites par la DEPP.",
};

export const factSheet: FactSheet = {
  uai: "9760127J",
  identite: {
    nom: "Lycée Younoussa Bamana",
    type: "lycee",
    statut_public_prive: "public",
    adresse: "1 rue Example",
    code_postal: "97600",
    commune: "Mamoudzou",
    code_departement: "976",
    filieres: ["generale", "technologique"],
    sections: [],
    sites: [],
  },
  resultats: [
    {
      annee: 2019,
      type_indicateur: "IVAL_GT",
      candidats_presents: 655,
      taux_reussite: { ...presentFigure, valeur: 57 },
      taux_reussite_attendu: absentFigure,
      valeur_ajoutee_reussite: absentFigure,
      taux_acces: absentFigure,
      valeur_ajoutee_acces: absentFigure,
      taux_mention: absentFigure,
      valeur_ajoutee_mention: absentFigure,
      source,
    },
  ],
  explications: {
    taux_reussite: explanation,
    taux_attendu: { ...explanation, content_id: "taux_attendu", titre: "Taux attendu" },
    valeur_ajoutee: {
      ...explanation,
      content_id: "valeur_ajoutee",
      titre: "Valeur ajoutée",
    },
    taux_acces: { ...explanation, content_id: "taux_acces", titre: "Taux d'accès" },
    taux_mention: {
      ...explanation,
      content_id: "taux_mention",
      titre: "Taux de mention",
    },
    valeur_non_disponible: absenceExplanation,
  },
  rappel_de_portee:
    "Ces indicateurs décrivent certains résultats scolaires. Ils ne mesurent pas l'ambiance…",
  derniere_synchronisation: "2026-08-15T17:20:39.036978Z",
};
