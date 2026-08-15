# Parcours utilisateurs

## 1. Parcours principal — Explorer une zone

### Intention

Un parent cherche des lycées généraux autour d’une commune et souhaite comprendre les données disponibles.

### Séquence

1. L’accueil explique la promesse et les limites en deux phrases.
2. L’utilisateur saisit : « lycées généraux autour de Chaville ».
3. Le système identifie une requête complexe et produit des critères structurés.
4. La page de résultats affiche : type « lycée général et technologique », centre « Chaville », rayon par défaut « 10 km », tous statuts.
5. Une phrase précise que « autour » a été interprété comme 10 km.
6. L’utilisateur peut modifier chaque critère sans reformuler sa recherche.
7. Les résultats sont triés par correspondance, puis distance.
8. L’utilisateur ouvre une fiche.
9. Il consulte les informations générales et la dernière année disponible.
10. Il ouvre l’explication de la valeur ajoutée dans un panneau contextuel.
11. Il affiche l’historique lorsque disponible.
12. Il ajoute l’établissement à la comparaison.
13. Il revient aux résultats et choisit un second établissement.
14. La comparaison affiche deux colonnes symétriques, sans verdict.
15. L’utilisateur peut partager le lien ou exporter les données avec leurs explications.

### Fin réussie

L’utilisateur comprend les valeurs, leur date et leurs limites. Le produit ne lui dit pas quel établissement choisir.

## 2. Recherche directe par nom

1. L’utilisateur saisit un nom d’établissement.
2. L’autocomplétion affiche nom, type, commune et code postal.
3. Si un résultat est suffisamment certain, l’utilisateur ouvre directement la fiche.
4. Si plusieurs établissements portent un nom proche, une liste de désambiguïsation est affichée.

Le LLM n’est pas sollicité pour ce parcours.

## 3. Requête ambiguë

Exemple : « collège Victor-Hugo » sans commune.

Le système affiche les correspondances possibles et demande :

> Plusieurs établissements correspondent à ce nom. Dans quelle commune cherchez-vous ?

Aucun établissement n’est sélectionné arbitrairement.

## 4. Requête subjective ou interdite

Exemple : « Quel est le meilleur lycée de Versailles ? »

Réponse retenue :

> Ce service ne classe pas les établissements et ne peut pas désigner le meilleur. Vous pouvez toutefois consulter les établissements de Versailles et comprendre leurs indicateurs officiels.

Actions proposées :

- Voir les lycées de Versailles
- Comprendre les indicateurs

Le système extrait uniquement le type et la localisation. Le mot « meilleur » n’est jamais transformé en tri de performance.

## 5. Aucun résultat

Le produit :

- répète les critères appliqués ;
- explique qu’aucun établissement correspondant n’a été trouvé dans les données actuellement couvertes ;
- propose d’élargir le rayon, de retirer un filtre ou de vérifier l’orthographe ;
- distingue clairement « aucun résultat » de « service indisponible ».

## 6. Établissement sans indicateur

La fiche générale reste accessible.

Message :

> Nous disposons des informations générales de cet établissement, mais aucun indicateur de résultats compatible n’est disponible dans les données actuellement intégrées.

La page propose la méthodologie et la source, sans suggérer de conclusion.

## 7. Valeur sous le seuil de diffusion

La carte d’indicateur affiche « Valeur non diffusée » au lieu d’un nombre.

Le détail explique :

> La DEPP ne publie pas cette valeur lorsque l’effectif est inférieur au seuil prévu pour préserver la fiabilité statistique. Cette absence ne permet de tirer aucune conclusion sur l’établissement.

Le produit ne tente aucune estimation.

## 8. Historique avec rupture méthodologique

Si le spike confirme une rupture :

- la courbe est visuellement interrompue ;
- une annotation neutre marque le changement ;
- les périodes incompatibles ne sont pas reliées ;
- le tableau conserve les valeurs et leur version méthodologique ;
- aucun calcul de tendance ne traverse la rupture.

## 9. Comparaison avec années différentes

Un avertissement est placé avant les indicateurs :

> Les dernières données disponibles ne portent pas sur la même année. Elles sont présentées côte à côte, mais ne constituent pas une comparaison temporelle équivalente.

Chaque valeur conserve son année. Aucun alignement artificiel n’est calculé.

## 10. Recherche sans LLM disponible

Le produit maintient :

- la recherche par nom ;
- la recherche par commune ou code postal ;
- les filtres structurés.

Message non bloquant :

> La recherche en phrase complète est momentanément indisponible. Vous pouvez rechercher par établissement ou par localité.

## 11. Données anciennes

Lorsque la dernière année dépasse la fraîcheur normale attendue, la fiche affiche :

> Dernières données disponibles : [année]. Elles peuvent ne pas refléter la situation actuelle de l’établissement.

La donnée reste consultable, avec sa date de synchronisation.

## 12. Partage et export

Le partage par lien conserve la page et son contexte d’année.

Le PDF conserve obligatoirement :

- identité de l’établissement ;
- valeurs et années ;
- définitions essentielles ;
- données non diffusées et leurs motifs ;
- rappel de portée ;
- sources ;
- date de génération.

Un export tronqué de ces éléments est considéré comme non conforme.

## 13. Signalement d’une explication peu claire

Une action discrète « Cette explication est-elle claire ? » propose Oui / Non.

En cas de réponse négative, l’utilisateur peut choisir :

- vocabulaire trop technique ;
- explication trop longue ;
- limite difficile à comprendre ;
- autre commentaire facultatif.

Aucun compte n’est requis et aucune donnée sensible n’est demandée.
