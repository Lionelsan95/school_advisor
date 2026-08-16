# Inventaire des écrans et états

> **Statut d'implémentation : critères cibles des Phases 3 à 5.** Aucun
> frontend n'existe encore. La recherche backend par UAI/nom/commune/code
> postal et la résolution de communes existent ; l'autocomplétion, l'année sur
> les cartes de résultat et les états détaillés
> ci-dessous ne doivent pas être lus comme des capacités déjà présentes dans
> l'API déterministe actuelle.

## 1. Matrice des écrans

| ID | Écran | Priorité | Desktop | Mobile |
|---|---|---:|---:|---:|
| E01 | Accueil / recherche | P0 | Oui | Oui |
| E02 | Résultats en liste | P0 | Oui | Oui |
| E03 | Filtres | P0 | Barre/panneau | Panneau |
| E04 | Carte géographique | P1 | Oui | Repliable |
| E05 | Fiche établissement | P0 | Oui | Oui |
| E06 | Explication indicateur | P0 | Panneau latéral | Panneau inférieur |
| E07 | Historique | P0 conditionnel | Oui | Oui |
| E08 | Comparaison | P0 | Oui | Oui |
| E09 | Glossaire | P1 | Oui | Oui |
| E10 | Comprendre les données | P1 | Oui | Oui |
| E11 | Méthodologie | P0 | Oui | Oui |
| E12 | Export PDF | P1 | Document | Document |

P0 : indispensable à la validation du produit.  
P1 : nécessaire avant ouverture publique, mais ne bloque pas les premiers tests de wireframes.

## 2. États transverses obligatoires

Chaque écran consommant des données doit prévoir :

- initial ;
- chargement ;
- succès complet ;
- succès partiel ;
- vide ;
- erreur récupérable ;
- erreur persistante ;
- données anciennes ;
- fonctionnement sans LLM lorsque pertinent.

Les squelettes de chargement doivent conserver la structure sans simuler de faux chiffres.

## 3. États de recherche

| ID | État | Comportement attendu |
|---|---|---|
| R01 | Champ vide | Exemples et instruction courte |
| R02 | Saisie nom | Autocomplétion déterministe |
| R03 | Phrase complexe | Chargement puis critères interprétés |
| R04 | Ambiguïté | Choix ciblé, aucune sélection arbitraire |
| R05 | Requête subjective | Refus du classement + exploration factuelle |
| R06 | Aucun résultat | Critères répétés + pistes neutres |
| R07 | LLM indisponible | Recherche structurée maintenue |
| R08 | Erreur service | Réessayer + explication non technique |

## 4. États des données établissement

| ID | État | Libellé utilisateur |
|---|---|---|
| D01 | Disponible | Valeur + unité + année |
| D02 | Valeur absente | Valeur non disponible — la source ne précise pas le motif applicable à cette ligne |
| D03 | Non applicable | Indicateur non applicable à cet établissement |
| D04 | Non intégré | Aucune donnée compatible actuellement intégrée |
| D05 | Ancien | Dernières données disponibles : [année] |
| D06 | Source en retard | Synchronisation en attente de vérification |
| D07 | Erreur locale | Impossible d’afficher cette donnée pour le moment |

Les états D02 à D07 comportent un lien « Pourquoi ? ».

## 5. Critères d’acceptation — Accueil

- La promesse est comprise sans défilement sur un mobile courant.
- Le champ accepte nom, localité et phrase naturelle.
- Trois exemples maximum sont proposés.
- Le caractère officiel, expliqué et non classant est visible.
- Le rappel de portée est présent.
- Aucun contenu ne valorise un établissement.

## 6. Critères d’acceptation — Résultats

- Les critères interprétés sont visibles et modifiables.
- Le rayon par défaut de 10 km est explicite lorsqu’il est inféré.
- Le tri « proximité » est visible.
- Aucun tri de performance n’existe dans le DOM ou l’interface.
- Chaque résultat expose l’année de données ou son indisponibilité.
- Ajouter à la comparaison ne nécessite pas de compte.
- La carte utilise des marqueurs identiques.

## 7. Critères d’acceptation — Fiche

- Identité, type, statut et commune sont visibles avant les indicateurs.
- Chaque valeur expose une année.
- Chaque indicateur ouvre son explication sans perdre la position de lecture.
- Chaque donnée chiffrée donne accès à sa source.
- Le rappel de portée est permanent mais non modal.
- L’UAI et les détails techniques restent disponibles sans dominer la page.
- Les états d’absence utilisent une phrase complète.

## 8. Critères d’acceptation — Historique

- Le graphique possède un tableau équivalent.
- Aucun commentaire automatique de hausse, baisse ou stabilité n’est produit.
- Les années absentes ne sont pas interpolées.
- Les ruptures méthodologiques interrompent la continuité visuelle.
- Le graphique est compréhensible sans dépendre de la couleur.
- La valeur exacte et l’année sont accessibles au clavier.

## 9. Critères d’acceptation — Comparaison

- Deux établissements maximum.
- Aucun score global.
- Aucun maximum coloré, coché ou typographiquement favorisé.
- Les années restent associées à chaque valeur.
- Une différence d’année déclenche un avertissement.
- Les définitions sont communes aux deux colonnes.
- La version mobile ne requiert aucun défilement horizontal.
- Un export conserve limites, années et sources.

## 10. Critères d’acceptation — Accessibilité

- Objectif WCAG 2.2 AA.
- Focus clavier visible.
- Ordre de tabulation logique.
- Libellés de formulaire persistants.
- Erreurs annoncées aux technologies d’assistance.
- Contraste texte normal au moins 4,5:1.
- Cibles tactiles au moins 44 × 44 px, sauf exception normative documentée.
- Graphiques accompagnés d’un tableau.
- Aucune information transmise uniquement par couleur, position ou survol.
- L’interface reste utilisable à 200 % de zoom.

## 11. Critères d’acceptation — Performance perçue

- L’interface de recherche répond immédiatement à la saisie.
- Une recherche déterministe ne dépend pas du LLM.
- Un état de progression apparaît pour une interprétation complexe.
- Les changements de filtre évitent les sauts de mise en page.
- Les composants principaux sont conçus pour un rendu côté serveur ou une hydratation progressive, sans l’imposer à ce stade.

## 12. Lot de wireframes à produire

### Lot A — parcours critique

- E01 accueil mobile et desktop ;
- E02 résultats mobile et desktop ;
- E05 fiche mobile et desktop ;
- E06 explication mobile et desktop ;
- E08 comparaison mobile et desktop.

### Lot B — profondeur et confiance

- E07 historique ;
- E09 glossaire ;
- E10 comprendre ;
- E11 méthodologie ;
- états R04, R05, R06, R07, D02, D04 et D05.

Le lot A doit être validé avant le lot B, sauf l’état D02 qui doit apparaître dès la première fiche pour tester la compréhension des données absentes.
