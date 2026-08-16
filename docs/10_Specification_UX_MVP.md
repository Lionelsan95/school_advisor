# Spécification UX du MVP

> **Statut d'implémentation : cible MVP.** La fiche REST, la recherche
> déterministe par coordonnées/type/secteur/filière, UAI/nom/commune/code
> postal et la résolution officielle de communes sont disponibles. Le
> frontend, l'autocomplétion et l'interprétation de phrases restent à livrer.

## 1. Finalité

Établissements en clair aide un citoyen à trouver, lire et comprendre les données publiques officielles relatives aux résultats des collèges et lycées, sans transformer ces données en classement ou en conseil personnalisé.

### Proposition de valeur

> Les données officielles des collèges et lycées, expliquées simplement.

### Promesse de confiance

> Ici, pas de classement ni de recommandation. Chaque donnée est présentée avec sa date, sa source, sa signification et ses limites.

## 2. Utilisateur prioritaire

### Parent en recherche d’information

- dispose de peu de temps ;
- ne maîtrise pas le vocabulaire statistique de la DEPP ;
- cherche souvent par nom d’établissement ou par zone géographique ;
- veut comprendre sans recevoir une décision toute faite ;
- utilise fréquemment un téléphone.

### Utilisateurs secondaires

- journaliste local ;
- citoyen curieux ;
- élu ou agent territorial.

Le MVP ne comporte pas de parcours professionnel spécialisé.

## 3. Besoins prioritaires

1. Retrouver un établissement ou un ensemble d’établissements pertinents.
2. Savoir comment la demande a été comprise.
3. Lire la dernière donnée disponible sans jargon.
4. Comprendre précisément un indicateur et ses limites.
5. Vérifier l’année, la source et la fraîcheur de la donnée.
6. Examiner l’évolution annuelle lorsque la méthode le permet.
7. Placer deux établissements côte à côte sans verdict automatique.
8. Comprendre ce que signifie l’absence d’une donnée et les limites de ce que
   la source permet d’en dire.

## 4. Principes de conception

### P1 — Expliquer sans conclure

L’interface décrit les données. Elle ne traduit pas une valeur en jugement, conseil ou action recommandée.

### P2 — Montrer l’interprétation de la requête

Toute recherche en langage naturel est convertie en critères visibles et modifiables. L’utilisateur ne dépend jamais d’une boîte noire conversationnelle.

### P3 — Proximité avant performance

Les résultats géographiques sont triés par correspondance puis proximité. Aucun tri par taux, valeur ajoutée ou résultat n’est disponible.

### P4 — Explication à proximité de la donnée

Chaque indicateur donne accès, sans changement de contexte, à : ce qu’il mesure, ce qu’il ne mesure pas, son mode de lecture et sa source.

### P5 — Absence explicite et sans motif inventé

Une valeur absente possède une explication compréhensible. Le symbole `—` ne
doit jamais être le seul contenu affiché, et l'interface n'attribue aucune
cause à la ligne lorsque la source n'en publie pas.

### P6 — Traçabilité visible

Chaque valeur présente au minimum une année et un accès à sa source. Les transformations déterministes sont documentées.

### P7 — Divulgation progressive

La fiche commence par une synthèse factuelle. Les détails statistiques, identifiants et méthodes restent disponibles sans surcharger la première lecture.

### P8 — Accessibilité par défaut

La couleur n’est jamais l’unique porteur de sens. Navigation clavier, lecteurs d’écran, contrastes AA, zones tactiles d’au moins 44 × 44 px et alternative tabulaire aux graphiques sont requis.

## 5. Périmètre fonctionnel V1

### Inclus

- recherche par nom, commune, code postal ou phrase naturelle ;
- critères visibles : type, statut, zone/rayon, sections ou dispositifs lorsque disponibles ;
- liste factuelle et, en option, carte géographique ;
- fiche d’établissement ;
- indicateurs disponibles, définitions et limites ;
- historique compatible avec la méthodologie confirmée ;
- comparaison de deux établissements ;
- glossaire contextuel et page complète ;
- page méthodologie et transparence ;
- partage par lien et export PDF conservant sources et limites ;
- signalement « explication peu claire » sans compte.

### Exclus

- compte utilisateur et favoris synchronisés ;
- profil d’enfant ;
- recommandation ou classement ;
- avis d’utilisateurs ;
- alertes ;
- comparaison de plus de deux établissements ;
- données immobilières, transport ou vie de quartier ;
- application mobile native ;
- assistant conversationnel généraliste ;
- back-office éditorial complet.

## 6. Décision sur l’usage de l’IA

Le produit utilise une recherche hybride.

1. Une requête simple est traitée sans LLM : nom, UAI, commune ou code postal.
2. Une requête complexe peut être convertie par le LLM en critères structurés autorisés.
3. Les critères produits sont validés côté serveur et affichés à l’utilisateur.
4. Le LLM ne génère ni explication d’indicateur, ni jugement, ni résumé de performance.
5. Si l’interprétation est incertaine, le produit demande une précision ciblée ou propose des critères modifiables.
6. La recherche reste utilisable si le service LLM est indisponible.

## 7. Modèle de navigation

Navigation publique simple :

- Rechercher
- Comprendre les données
- Glossaire
- À propos / Méthodologie

La comparaison est un contexte de travail, accessible après ajout d’un premier établissement. Elle n’occupe pas une entrée principale vide.

## 8. Ligne directrice visuelle

Style : service d’information contemporain, calme et rigoureux.

- interface claire, à forte lisibilité ;
- bleu profond comme couleur d’action et de confiance ;
- gris neutres pour les structures ;
- ambre pour les avertissements méthodologiques ;
- rouge réservé aux erreurs techniques ;
- ni vert ni rouge pour exprimer une performance ;
- chiffres lisibles mais non spectaculaires ;
- iconographie fonctionnelle, sans trophée, médaille ou classement.

La définition précise des tokens interviendra après validation des wireframes.

## 9. Données d’exemple

Les maquettes emploient des établissements fictifs et des valeurs plausibles. Toute maquette doit porter la mention « Données fictives de démonstration » afin d’éviter l’attribution de faux résultats à un établissement réel.

## 10. Mesure de succès UX

Les tests qualitatifs doivent vérifier que l’utilisateur :

- reformule correctement la promesse du produit ;
- retrouve un établissement sans assistance ;
- distingue taux de réussite et valeur ajoutée ;
- identifie au moins une limite de l’indicateur consulté ;
- retrouve l’année et la source ;
- comprend qu’une donnée non diffusée n’est ni nulle ni défavorable ;
- ne rapporte aucun verdict ou classement attribué au produit.

## 11. Critères de passage aux maquettes haute fidélité

Les wireframes doivent être validés avant stylisation si :

- le parcours principal est réalisable sur mobile et desktop ;
- toutes les données possèdent leurs états d’absence ;
- la comparaison ne crée pas de gagnant visuel ;
- les sources et années restent accessibles ;
- le rappel de portée est visible sans empêcher l’usage ;
- la recherche montre et permet de corriger son interprétation.

## 12. Risques et arbitrages

| Risque | Arbitrage retenu |
|---|---|
| L’interface ressemble à un palmarès | Aucun tri de performance, aucun score, aucune mise en avant du maximum |
| Le LLM invente ou reformule librement | Sortie bornée en critères autorisés, contenus explicatifs versionnés |
| L’utilisateur est noyé dans les limites | Résumé permanent court, détail à la demande |
| L’historique suggère une tendance | Aucun commentaire automatique ; rupture méthodologique visible |
| Le mobile rend la comparaison illisible | Comparaison par indicateur successif, avec deux valeurs alignées |
| Le périmètre paraît incomplet | Couverture et date de synchronisation annoncées explicitement |
| Le produit devient trop vaste pour un solopreneur | Pas de compte, de personnalisation, d’alertes ni de verticales annexes |
