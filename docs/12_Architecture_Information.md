# Architecture de l’information

## 1. Arborescence publique

```text
Accueil / Recherche
├── Résultats
│   ├── Liste
│   ├── Carte optionnelle
│   └── Filtres
├── Fiche établissement
│   ├── Vue d’ensemble
│   ├── Indicateurs
│   ├── Historique
│   ├── Sources et détails
│   └── Partage / export
├── Comparaison
├── Comprendre les données
├── Glossaire
├── Méthodologie et transparence
└── Mentions légales / confidentialité / accessibilité
```

## 2. Navigation globale

### En-tête desktop

- logo / nom : retour à l’accueil ;
- Rechercher ;
- Comprendre les données ;
- Glossaire ;
- À propos des données ;
- accès à la comparaison uniquement lorsqu’au moins un établissement y a été ajouté.

### En-tête mobile

- nom du produit ;
- action de recherche ;
- menu compact ;
- indicateur de comparaison si actif.

### Pied de page

- rappel de neutralité ;
- sources officielles ;
- méthodologie ;
- accessibilité ;
- confidentialité ;
- mentions légales ;
- date de dernière synchronisation globale.

## 3. Accueil

Ordre de contenu :

1. promesse ;
2. champ de recherche ;
3. exemples de requêtes ;
4. engagements : officiel, expliqué, sans classement ;
5. rappel synthétique de portée ;
6. accès à « Comment lire les données ».

L’accueil ne comporte ni palmarès, ni établissement populaire, ni classement territorial.

## 4. Résultats

Ordre de contenu :

1. requête et nombre de résultats ;
2. critères interprétés et modifiables ;
3. mention du tri par proximité ;
4. bascule liste/carte ;
5. cartes établissement ;
6. pagination ou chargement progressif accessible.

### Carte établissement

- nom officiel ;
- type ;
- statut ;
- commune ;
- distance si une origine est définie ;
- sections principales ;
- année la plus récente disponible ;
- état de disponibilité des indicateurs ;
- actions « Voir la fiche » et « Ajouter à la comparaison ».

Aucun taux détaillé n’est affiché dans la liste : cela limite le balayage de type palmarès et concentre la lecture sur la fiche contextualisée.

## 5. Fiche établissement

Ordre de contenu :

1. identité, adresse, type, statut ;
2. date des dernières données et état de fraîcheur ;
3. rappel de portée permanent et compact ;
4. informations générales ;
5. indicateurs de la dernière année disponible ;
6. historique ;
7. sources et détails techniques ;
8. partage / export.

### Hiérarchie d’une carte indicateur

1. libellé ;
2. valeur ou état d’absence ;
3. année ;
4. phrase de lecture factuelle si nécessaire ;
5. action « Comprendre cet indicateur » ;
6. source.

## 6. Explication contextuelle

Sur desktop : panneau latéral.  
Sur mobile : panneau inférieur plein écran partiel, refermable et compatible clavier.

Ordre :

1. définition simple ;
2. comment lire la valeur ;
3. ce que l’indicateur mesure ;
4. ce qu’il ne mesure pas ;
5. méthode plus détaillée ;
6. source officielle ;
7. retour de clarté.

## 7. Historique

- un indicateur sélectionné à la fois sur mobile ;
- graphique et tableau équivalent ;
- années explicites ;
- aucune ligne de moyenne concurrentielle ;
- aucune prédiction ;
- aucune interprétation de tendance ;
- ruptures méthodologiques matérialisées ;
- années absentes non interpolées.

## 8. Comparaison

### Desktop

- en-têtes fixes des deux établissements ;
- groupes : identité, disponibilité, indicateurs, sources ;
- lignes symétriques ;
- définition commune par ligne.

### Mobile

Chaque indicateur forme un bloc : libellé, valeur A et année, valeur B et année, définition. Il n’y a pas de grand tableau horizontal nécessitant un défilement latéral.

### Actions

- remplacer A ou B ;
- retirer un établissement ;
- retourner aux résultats ;
- partager/exporter.

## 9. Comprendre les données

Page pédagogique destinée à une première découverte :

- pourquoi les taux bruts ne suffisent pas ;
- différence entre résultat observé et attendu ;
- valeur ajoutée ;
- taux d’accès ;
- seuils de diffusion ;
- limites générales.

Cette page ne cite aucun établissement comme exemple positif ou négatif.

## 10. Glossaire

- recherche alphabétique et textuelle ;
- termes officiels ;
- définition courte ;
- exemple générique ;
- source ;
- liens croisés entre notions.

Les occurrences dans l’interface ouvrent directement la bonne définition.

## 11. Méthodologie et transparence

- organismes producteurs ;
- jeux de données utilisés ;
- dernière synchronisation ;
- couverture mesurée ;
- transformations déterministes ;
- rôle exact de l’IA ;
- version des textes explicatifs ;
- règles de données manquantes ;
- limites temporelles ;
- ruptures méthodologiques ;
- contact ou canal de signalement.

## 12. URL et partage

Les URL doivent rester lisibles et stables :

```text
/
/recherche?q=...
/etablissements/{uai}/{slug}
/etablissements/{uai}/historique?indicateur=...
/comparaison?uai={uaiA},{uaiB}
/comprendre
/glossaire/{terme}
/methodologie
```

L’UAI garantit l’identité ; le slug améliore la lisibilité. Le backend ne doit jamais se fier au slug pour identifier l’établissement.
