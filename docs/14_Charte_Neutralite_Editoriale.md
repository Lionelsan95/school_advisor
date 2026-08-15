# Charte de neutralité éditoriale et visuelle

## 1. Règle supérieure

> L’outil explique, il ne juge pas.

Cette règle s’applique aux textes, couleurs, graphiques, tris, composants, métadonnées, exports, titres de page et contenus générés pour le référencement.

## 2. Voix du produit

La voix est :

- factuelle ;
- pédagogique ;
- précise ;
- calme ;
- transparente sur l’incertitude et les limites.

Elle n’est pas :

- promotionnelle ;
- prescriptive ;
- alarmiste ;
- familière ;
- technocratique ;
- faussement certaine.

Le produit s’adresse à l’utilisateur avec « vous » et privilégie des phrases courtes.

## 3. Formulations de référence

| Situation | Formulation retenue | Formulation interdite |
|---|---|---|
| Proposition | Comprendre les données officielles | Trouver la meilleure école |
| Taux élevé | Taux de réussite observé : 92 % | Excellent taux de réussite |
| Taux faible | Taux de réussite observé : 68 % | Mauvais résultat |
| Valeur ajoutée positive | Résultat observé supérieur de 4 points au résultat statistiquement attendu | L’établissement surperforme |
| Valeur ajoutée négative | Résultat observé inférieur de 3 points au résultat statistiquement attendu | L’établissement sous-performe |
| Égalité | Les deux valeurs affichées sont identiques pour cette année | Les établissements sont équivalents |
| Historique | Valeurs disponibles de 2022 à 2025 | Tendance positive sur quatre ans |
| Donnée absente | Valeur non diffusée en raison du seuil d’effectif | Résultat insuffisant / N.A. |
| Donnée ancienne | Dernières données disponibles : 2023 | Résultats obsolètes |
| Comparaison | Placer les données côte à côte | Trouver le meilleur établissement |
| Requête subjective | Ce service ne classe pas les établissements | Voici nos meilleurs résultats |

## 4. Structure obligatoire d’une explication

Chaque indicateur possède un contenu éditorial versionné comprenant :

1. **Définition simple** — une ou deux phrases.
2. **Comment lire cette valeur** — formulation descriptive adaptée à l’unité.
3. **Ce que cela mesure** — périmètre exact.
4. **Ce que cela ne mesure pas** — limites nécessaires.
5. **Méthode** — détail facultatif mais accessible.
6. **Source et millésime** — lien officiel et date.

Aucune de ces sections n’est rédigée librement par le LLM en production.

## 5. Valeur ajoutée

Forme recommandée :

> Résultat observé par rapport au résultat statistiquement attendu : **+4 points**

Explication immédiatement disponible :

> Cette différence tient compte de certaines caractéristiques scolaires et sociodémographiques des élèves accueillis. Elle ne mesure pas à elle seule la qualité globale de l’établissement.

Le signe `+` ou `−` reste affiché car il fait partie de la donnée, mais il ne reçoit aucune couleur de performance.

## 6. Données non diffusées

Texte de référence :

> **Valeur non diffusée**  
> La DEPP ne publie pas cette valeur lorsque l’effectif est inférieur au seuil prévu pour préserver la fiabilité statistique. Cette absence ne permet de tirer aucune conclusion sur l’établissement.

Il est interdit :

- d’estimer la valeur ;
- de remplacer l’absence par zéro ;
- d’afficher uniquement un tiret ;
- d’associer l’absence à une couleur négative ;
- de suggérer que le seuil reflète la qualité.

## 7. Rappel de portée

Version courte, utilisée sur les pages principales :

> Ces indicateurs décrivent certains résultats scolaires. Ils ne mesurent pas l’ambiance, l’accompagnement quotidien, le bien-être des élèves ni l’adéquation avec un enfant.

Version d’accueil :

> Ce service présente et explique des données publiques officielles. Il ne classe pas les établissements et ne recommande aucun choix.

Ces rappels ne sont ni fermables définitivement, ni présentés comme des erreurs.

## 8. Sources

Les libellés privilégient :

- « Source officielle » ;
- « Données publiées par… » ;
- « Année de référence » ;
- « Dernière synchronisation ».

Ne pas utiliser « selon notre IA », puisque l’IA n’est pas la source de la donnée.

## 9. Règles visuelles

### Interdits

- rouge/vert pour différencier les résultats ;
- podium, étoiles, trophées, médailles ;
- flèches automatiques de hausse ou baisse ;
- score circulaire ou jauge de qualité ;
- badge « recommandé », « populaire » ou « meilleur choix » ;
- surbrillance du maximum ;
- ordre automatique par valeur ;
- carte thermique de performance dans le MVP.

### Autorisés

- couleurs neutres cohérentes par type d’information ;
- ambre pour une précaution méthodologique ;
- rouge pour une erreur technique qui nécessite une action ;
- icône d’information pour une définition ;
- icône de calendrier pour un millésime ;
- icône de lien externe pour une source ;
- axe centré sur zéro pour la valeur ajoutée, uniquement si les tests confirment sa compréhension.

## 10. Graphiques

- titre descriptif, jamais conclusif ;
- unités et années explicites ;
- valeurs exactes accessibles ;
- aucune courbe de projection ;
- aucune moyenne nationale ou locale ajoutée sans justification méthodologique et décision produit ultérieure ;
- années manquantes laissées vides ;
- ruptures méthodologiques visibles ;
- tableau équivalent obligatoire.

## 11. Comparaison

Le mot « comparaison » désigne une mise en parallèle, pas une évaluation.

Le produit ne calcule pas :

- nombre de critères remportés ;
- moyenne des indicateurs ;
- écart global ;
- score pondéré ;
- verdict textuel ;
- recommandation finale.

## 12. Réponse aux demandes de recommandation

Réponse type :

> Ce service ne classe pas les établissements et ne peut pas vous dire lequel choisir. Il peut vous aider à consulter leurs données officielles, à comprendre chaque indicateur et à en connaître les limites.

Le produit peut ensuite proposer une action factuelle pertinente.

## 13. Rôle éditorial de l’IA

L’IA peut :

- détecter l’intention de recherche ;
- extraire une commune, un rayon, un type ou un statut ;
- signaler une ambiguïté ;
- produire une reformulation contrôlée à partir de gabarits.

L’IA ne peut pas :

- commenter une performance ;
- résumer librement une fiche ;
- expliquer librement un indicateur ;
- inférer une cause ;
- recommander un établissement ;
- compléter une donnée absente ;
- établir une tendance.

## 14. Contrôle avant publication

Toute nouvelle interface ou formulation doit répondre « non » aux questions suivantes :

1. Peut-elle être comprise comme un classement ?
2. Fait-elle ressortir spontanément un gagnant ?
3. Attribue-t-elle une cause non présente dans la source ?
4. Cache-t-elle l’année ou la provenance ?
5. Transforme-t-elle une absence de donnée en signal négatif ?
6. Présente-t-elle une hypothèse comme un fait ?
7. Invite-t-elle l’utilisateur à choisir ou éviter un établissement ?

Une seule réponse « oui » bloque la publication jusqu’à correction ou décision documentée.
