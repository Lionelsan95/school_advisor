# Vision & Produit — Assistant d'exploration des données publiques scolaires

*Document de référence condensé — à remplacer (pas empiler) en cas d'évolution du PRD complet.*
*Dernière mise à jour : Août 2026*

---

## Principe directeur (non négociable)

> **L'outil explique, il ne juge pas.**

Chaque fonctionnalité, chaque ligne de contenu, chaque choix d'UX doit être arbitré à l'aune de ce principe. En cas de doute sur une fonctionnalité ("est-ce qu'elle pousse l'utilisateur vers une conclusion ?"), la réponse par défaut est de la simplifier ou de la retirer.

L'outil ne recommande jamais un établissement, ne classe pas, ne dit jamais "bon" ou "mauvais". Il traduit une donnée publique officielle en langage clair, sourcé et contextualisé — et laisse l'utilisateur tirer ses propres conclusions.

## Problème adressé

Les données publiques sur les établissements scolaires (annuaire, indicateurs de résultats DEPP) sont officielles et gratuites, mais publiées sous forme de fichiers/API bruts, avec un vocabulaire statistique inaccessible à un non-spécialiste (valeur ajoutée, IVAC, IVAL...). Une information censée être un service public reste hors de portée du citoyen lambda.

## Ce que le produit n'est pas
- Un comparateur qui classe ou note
- Un système de recommandation
- Un outil d'aide à la décision immobilière ou scolaire complet
- Un outil de conseil personnalisé

## Personas

**Principal — Parent en recherche d'information.** Envisage un choix d'établissement ou un déménagement. Non-statisticien, peu de temps, méfiant vis-à-vis des classements médiatiques non vérifiés. Besoin : une donnée officielle fiable, comprise, sans conclusion imposée.

**Secondaire — Citoyen curieux / journaliste local / élu.** Comprendre la situation d'un établissement à des fins d'information ou de suivi de politique publique locale.

**Secondaire (hors MVP) — Professionnel de l'orientation.** CIO, enseignant, travailleur social.

## Périmètre — In scope (MVP)

| # | Fonctionnalité | Essentiel |
|---|---|---|
| F1 | Recherche en langage naturel | Requête libre → liste factuelle, tri par défaut = proximité, jamais par "qualité" |
| F2 | Fiche établissement neutre | Données + définitions + contexte, zéro qualificatif évaluatif |
| F3 | Explicateur systématique | Bloc figé "ce que ça mesure / ne mesure pas" sur chaque indicateur — contenu éditorial validé, jamais généré librement par le LLM |
| F4 | Vue côte-à-côte | Deux fiches en parallèle, sans score agrégé ni surlignage "meilleur" |
| F5 | Historique pluriannuel | Courbe brute (jusqu'à 13 ans lycées, 4 ans collèges), sans interprétation de tendance |
| F6 | Transparence données manquantes | État explicite « valeur non disponible », sans attribuer à une ligne un motif que la source ne publie pas |
| F7 | Rappel de portée permanent | Mention systématique et non désactivable sur les limites du périmètre |
| F8 | Export / partage de fiche | PDF/lien, conserve intégralement F3/F6/F7 |
| F9 | Glossaire intégré | Accessible à tout moment, termes cliquables partout dans l'interface |
| F10 | Sourcing visible | Lien vers la source officielle sur chaque donnée chiffrée |

## Explicitement hors scope (et pourquoi)

| Écarté | Raison |
|---|---|
| Classement / scoring agrégé | Contraire au principe directeur |
| Recommandation personnalisée ("profil enfant") | Glisse vers du conseil individualisé |
| Alertes proactives | Pousse à l'action, connote l'urgence de décision |
| Autres verticales (immobilier, transport) | Dilue le périmètre "résultats scolaires uniquement" |
| Avis/notes d'utilisateurs | Source non officielle, biaisée |

## Entonnoir utilisateur (résumé)

Découverte (cadrage immédiat sur la neutralité) → Requête en langage naturel → Résultats factuels → Fiche établissement détaillée → Approfondissement optionnel (comparaison, historique, glossaire) → Sortie avec rappel des limites et sources.

**KPI de sortie du funnel : la compréhension et la confiance, pas la conversion vers une action.**

## Limites assumées publiquement
- Décalage temporel : jusqu'à un an entre la donnée et la situation réelle d'un établissement
- Couverture partielle : certaines valeurs ne sont pas publiées ; la source
  ouverte ne précise pas le motif applicable à chaque ligne
- Périmètre volontairement restreint : résultats scolaires uniquement, pas l'ambiance, la vie scolaire, l'encadrement au quotidien
- Pas de couverture nationale garantie à 100% dès le MVP

## Métriques de succès

Volontairement **absents** : taux de conversion, temps passé à "décider", taux de clic vers une action.

Présents : taux de complétion de lecture d'une fiche, taux de consultation du glossaire, taux de retour, taux de signalement "explication pas claire", et surtout un KPI de gouvernance : **0% de perception de recommandation** en test utilisateur qualitatif.
