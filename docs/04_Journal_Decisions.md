# Journal de décisions — projet Assistant Établissements Scolaires

*Document vivant — à mettre à jour à chaque choix structurant (produit, technique, éditorial).*
*Format : une entrée par décision, la plus récente en haut.*

---

## Comment l'utiliser

Ajoute une entrée à chaque fois que tu trancises un point qui pourrait être remis en question plus tard, ou que tu pourrais oublier d'avoir déjà décidé. Une ligne courte suffit — l'objectif est de ne jamais avoir à se reposer une question déjà tranchée sans savoir pourquoi.

**Gabarit d'entrée :**
```
### [Date] — [Titre court de la décision]
- **Contexte :** pourquoi la question se posait
- **Décision :** ce qui a été tranché
- **Alternatives écartées :** ce qu'on n'a pas choisi, et pourquoi
- **Réversibilité :** facile / coûteuse à revenir dessus
```

---

## Exemple (à retirer une fois les vraies décisions ajoutées)

### 2026-08-15 — Choix du moteur de base de données
- **Contexte :** besoin de trancher rapidement pour éviter la sur-ingénierie
- **Décision :** PostgreSQL + PostGIS
- **Alternatives écartées :** NoSQL et Elasticsearch, jugés disproportionnés pour le volume réel (~66 000 lignes)
- **Réversibilité :** coûteuse si le projet grossit fortement, mais peu probable à ce stade

---

## Décisions du projet

### 2026-08-15 — Identifiants de code en anglais, format JSON en français
- **Contexte :** `CLAUDE.md` impose des identifiants en anglais, mais tous les
  documents (glossaire, contrat d'API) emploient des noms français
  (`valeur_ajoutee`, `sous_seuil_diffusion`).
- **Décision :** code et colonnes de base en anglais ; le format d'échange JSON
  conserve les noms français de `08_API_Contract.md`. La conversion se fait au
  seul point de sérialisation.
- **Alternatives écartées :** noms français partout (contraire à une consigne
  explicite) ; anglais y compris sur le fil (romprait le contrat documenté).
- **Réversibilité :** coûteuse une fois l'API publiée ; facile aujourd'hui.

### 2026-08-15 — Multi-sites modélisés par une table `site` dédiée
- **Contexte :** 74 UAI désignent des établissements multi-sites (68 à deux
  sites, 6 à trois). L'UAI ne peut donc pas être clé primaire d'une table
  unique sans perdre un site.
- **Décision :** `etablissement` reste clé primaire `uai` ; une table `site`
  (1..n) porte nom, adresse et coordonnées de chaque implantation. Le site
  canonique est choisi de façon déterministe (`sequence` la plus basse) après
  tri sur des champs stables, pour qu'une réingestion identique donne le même
  résultat.
- **Alternatives écartées :** clé primaire de substitution avec `uai` non
  unique — rendrait `/etablissements/{uai}` ambigu ; « dernière ligne gagne » —
  ferait disparaître un site sans trace.
- **Réversibilité :** coûteuse (schéma).

### 2026-08-15 — Aucun champ `sous_seuil_diffusion` dans le modèle
- **Contexte :** vérification des catalogues de champs des trois jeux
  d'indicateurs : **aucune source ne publie de motif d'absence**. Seule
  l'absence de valeur est observable.
- **Décision :** ne pas créer le champ. Une valeur absente est un `NULL` sans
  motif. L'exigence d'API-4 (distinguer « non diffusée » de « non disponible »)
  n'est pas représentable à partir des données et reste bloquée sur la
  confirmation de la méthodologie DEPP.
- **Alternatives écartées :** conserver un booléen toujours nul pour respecter
  l'esquisse de `02_Architecture_Decisions.md` — un champ qui ne porte aucune
  information invite à lui faire dire quelque chose.
- **Réversibilité :** facile (ajout de colonne si une source le publie un jour).

### 2026-08-15 — Rechargement complet plutôt qu'upsert, et pas de clé étrangère
- **Contexte :** l'annuaire est un extrait complet sans marqueur de
  modification ; 1,2 % des lignes d'indicateurs référencent un UAI absent de
  l'annuaire.
- **Décision :** `replace_all` prend un instantané, vide les tables et les
  recharge par `COPY`, le tout dans une transaction (`TRUNCATE` est
  transactionnel sous Postgres). Aucune clé étrangère entre
  `indicateur_resultat` et `etablissement` : elle rejetterait des données
  officielles à cause de la lacune d'un autre jeu. Les non-rattachés sont
  journalisés.
- **Alternatives écartées :** upsert par UAI — ne détecterait pas les
  suppressions ; bascule par renommage de tables de staging — renomme
  silencieusement les index (voir `CLAUDE.md`, gotchas).
- **Réversibilité :** facile.

### 2026-08-15 — Spike de Phase 0 exécuté à l'échelle nationale, pas sur un département
- **Contexte :** le ticket SPIKE-1 suggérait « un département complet ». Un taux
  de correspondance limite mesuré sur un seul département n'aurait pas permis de
  trancher un go/no-go.
- **Décision :** exécuter la jointure sur la totalité des jeux de données via
  `/exports/json` (68 k établissements, 88 k lignes d'indicateurs, moins de
  10 s d'extraction).
- **Alternatives écartées :** échantillon départemental, écarté car le volume
  réel rend l'exhaustivité gratuite et supprime tout risque d'échantillonnage.
- **Réversibilité :** sans objet (mesure ponctuelle).

### 2026-08-15 — Go/no-go du spike : GO
- **Contexte :** deux hypothèses techniques bloquantes (fiabilité de la clé UAI,
  continuité méthodologique des IVAL).
- **Décision :** GO. Jointure fiable à 98,80 % (seuil visé : 90 %) ; séries IVAL
  identiques en valeurs entre ancienne et nouvelle version sur les 12 millésimes
  de recouvrement. Détails dans `05_Resultats_Spike_Technique.md`.
- **Alternatives écartées :** file de rapprochement semi-manuel pour les cas
  ambigus — inutile au vu du taux obtenu.
- **Réversibilité :** facile (le constat est daté et re-mesurable).

### 2026-08-15 — Méthode de mesure du taux de jointure : dénominateur restreint
- **Contexte :** l'annuaire contient 67 896 établissements de tous niveaux, dont
  47 947 écoles primaires hors périmètre IVAC/IVAL. Un taux brut aurait affiché
  ~10 % et n'aurait rien voulu dire.
- **Décision :** mesurer séparément (A) la fiabilité de la jointure — part des
  UAI d'indicateurs retrouvant une fiche d'annuaire — et (B) la couverture —
  part des établissements éligibles disposant d'indicateurs. Une valeur ajoutée
  nulle compte comme une jointure réussie.
- **Alternatives écartées :** taux unique rapporté à l'annuaire entier, écarté
  comme trompeur.
- **Réversibilité :** facile.

### 2026-08-15 — Historique F5 fondé sur les indicateurs « total », rupture marquée en 2021
- **Contexte :** le doute portait sur la possibilité d'afficher une série
  continue sur 13 ans. Le spike montre que la rupture réelle n'est pas entre les
  versions du jeu de données mais dans la composition des séries.
- **Décision :** F5 s'appuie sur `taux_reu_total`, `va_reu_total` et
  `taux_acces_2nde`, continus de 2012 à 2025. Aucun historique par série au MVP.
  L'année **2021** (réforme du baccalauréat) est portée dans
  `methodology_breaks`, en remplacement de l'exemple provisoire de 2019.
- **Alternatives écartées :** historique par série avec courbe interrompue —
  reporté hors MVP ; fusion silencieuse des deux périodes — contraire à la
  charte de neutralité.
- **Réversibilité :** facile.

### 2026-08-15 — `sous_seuil_diffusion` ne sera pas calculé par le backend
- **Contexte :** la règle du glossaire (<20 candidats GT, <10 PRO) ne se vérifie
  pas dans les données : 457 lignes IVAL GT au-dessus du seuil n'ont pas de
  valeur ajoutée (dont 113 à Mayotte, où elle n'est pas calculée), et 75 lignes
  sous le seuil en portent une (toutes en 2016).
- **Décision :** reprendre l'absence telle que la source la livre, sans la
  dériver d'un comptage. L'interface ne doit pas attribuer à toute valeur
  absente le motif du seuil d'effectif : ce serait faux dans une part notable
  des cas et contraire à la charte de neutralité (doc 14, § 6). Distinguer au
  minimum « valeur non diffusée » et « valeur non disponible ».
- **Alternatives écartées :** calcul du seuil côté backend, écarté comme
  factuellement inexact ; message unique pour toute absence, écarté pour la même
  raison.
- **Réversibilité :** coûteuse une fois le texte éditorial figé — d'où la
  nécessité de confirmer la sémantique DEPP avant de rédiger F6.

### 2026-08-15 — L'UAI n'est pas une clé unique dans l'annuaire
- **Contexte :** 74 UAI apparaissent deux fois dans l'annuaire (établissements
  multi-sites partageant un identifiant). Le modèle esquissé fait pourtant de
  `uai` la clé de `Etablissement`.
- **Décision :** ne pas poser `uai` en clé primaire avant d'avoir tranché une
  règle de déduplication (champs `multi_uai`, `etablissement_mere` à examiner).
  Point rattaché à DATA-2. Côté indicateurs, le couple `(uai, année)` est
  strictement unique : le stockage append-only reste valide.
- **Alternatives écartées :** déduplication implicite « dernière ligne gagne »,
  écartée car elle ferait disparaître un site sans trace.
- **Réversibilité :** coûteuse après création du schéma — à trancher avant DATA-2.

### 2026-08-15 — Test de changement de schéma source : reporté en Phase 1, non couvert par le spike
- **Contexte :** `CLAUDE.md` impose un test simulant un changement de schéma
  source pour toute évolution touchant l'ingestion. Le livrable de Phase 0 est
  un rapport, produit par des scripts jetables exécutés à la main.
- **Décision :** ne pas écrire de suite pytest pour les scripts de spike ; ils
  portent des assertions d'exécution (`check_fields_present`) qui interrompent
  le run si un champ attendu disparaît. **Cette exigence reste entièrement à
  satisfaire en Phase 1 (DATA-3/4/5)** et ne doit pas être considérée comme
  honorée par le spike.
- **Alternatives écartées :** suite de tests sur du code jetable, écartée comme
  sans valeur durable ; ignorer le sujet, écarté car c'est l'angle mort le plus
  critique du projet.
- **Réversibilité :** sans objet — dette explicitement enregistrée.

### 2026-08-15 — Lacune de couverture de l'annuaire sur le Var et le Vaucluse
- **Contexte :** 114 des 119 UAI non rattachés relèvent des départements 83 et
  84. Le Var compte 120 fiches dans l'annuaire, moins que la Lozère (152), pour
  un département d'environ un million d'habitants.
- **Décision :** traiter ce déficit comme un problème de complétude de la source
  et non de jointure ; l'annoncer sur la page « Méthodologie et transparence » ;
  faire de la chute du taux de rattachement un signal d'alerte d'ingestion
  (référence 98,8 %, seuil d'alerte ~95 %) — rattaché à DATA-5.
- **Alternatives écartées :** ignorer les non-correspondances, écarté ;
  compléter par une autre source, écarté au MVP (hors périmètre).
- **Réversibilité :** facile (la source peut se corriger d'elle-même).

---

## Décisions de la Phase 2 — API de lecture

### 2026-08-15 — Sémantique DEPP de l'absence confirmée : trois motifs, aucun publié
- **Contexte :** le ticket API-4 était bloqué sur la confirmation de la
  sémantique du seuil de non-diffusion. La documentation officielle a été
  consultée (*Guide méthodologique IVAC 2025*, « Conditions de publication des
  indicateurs » ; fiche catalogue DEPP des IVAL).
- **Constat :** l'absence d'une valeur ajoutée relève de **trois** situations
  documentées — trop peu de candidats, moins de 75 % d'informations retrouvées
  sur les élèves, et Mayotte (taux attendus non calculés). La DEPP les code
  `ND` / `NS` dans ses fichiers de travail, **mais aucun de ces codes ne
  survit à la publication en open data** : les trois cas arrivent en cellule
  vide. Vérifié sur l'API le 15/08/2026 (lignes à 143 et 655 candidats).
- **Décision :** le blocage d'API-4 est levé. Le motif est connu *en général* et
  inconnaissable *ligne à ligne* ; le contenu éditorial énumère donc les
  situations possibles sans en attribuer aucune.
- **Alternatives écartées :** attribuer le seuil d'effectif par défaut, écarté
  comme factuellement faux ; taire l'existence de motifs, écarté car cela
  priverait le lecteur d'une information vraie et publique.
- **Réversibilité :** facile côté texte, coûteuse côté attentes utilisateurs.

### 2026-08-15 — Une seule catégorie d'absence (« valeur non disponible »)
- **Contexte :** la charte (§ 6) et le journal demandaient de distinguer
  « valeur non diffusée » (motif publié) de « valeur non disponible » (motif
  non précisé).
- **Décision :** ne retenir **qu'une seule catégorie**. La première serait
  toujours vide : aucune source ne publie de motif, pour aucune ligne. La
  charte § 6 a été amendée en conséquence. Validé par revue humaine explicite
  (étape obligatoire du workflow « Explanatory content change »).
- **Alternatives écartées :** conserver les deux catégories avec une branche
  morte, écartée — du code jamais atteint et une distinction qu'aucune réponse
  ne peut faire.
- **Réversibilité :** facile (ajouter la seconde catégorie si une source
  publiait un jour un motif).

### 2026-08-15 — Le taux attendu est calculé et signalé comme tel
- **Contexte :** le contrat d'API promettait
  `taux_reussite_moyenne_academique` et `_nationale`. Vérification faite,
  **aucun des trois jeux de données ne publie de moyenne académique ou
  nationale par établissement**. Le taux *attendu*, lui, est reconstituable
  exactement : la DEPP définit la valeur ajoutée comme
  `taux constaté − taux attendu`.
- **Décision :** exposer `taux_reussite_attendu`, marqué `calcule: true` avec
  une `note_de_calcul`, conformément à la règle F10 du contrat sur les valeurs
  dérivées. Les deux champs de moyennes sont retirés du contrat.
- **Alternatives écartées :** n'exposer que la valeur ajoutée, écarté car le
  lecteur voit alors « +3 » sans point de repère ; publier le taux attendu sans
  le distinguer, écarté car il serait pris pour une donnée officielle.
- **Réversibilité :** facile.

### 2026-08-15 — Filières et sections ingérées depuis l'annuaire
- **Contexte :** le filtre `filiere` est un critère d'acceptation d'API-2, et le
  bloc identité prévoit `filieres` / `sections`. La Phase 1 ne lisait que 13
  champs de l'annuaire et n'en faisait pas partie.
- **Décision :** étendre `DIRECTORY_FIELDS` aux indicateurs `voie_*` et
  `section_*` / `ulis` / `segpa`, stockés en `text[]` sur `establishment`
  (migration 0002). Ce sont des descripteurs d'offre, jamais des résultats :
  ils peuvent filtrer, jamais ordonner.
- **Point d'attention :** l'annuaire n'est pas cohérent en types — `voie_*`,
  `section_*` et `segpa` arrivent en chaînes `"0"`/`"1"`, `ulis` en entier.
- **Alternatives écartées :** retirer `filiere` du contrat, écarté car cela
  réduisait silencieusement le périmètre d'un ticket ; table de jointure,
  écartée (listes courtes et fermées, sans attributs propres).
- **Réversibilité :** facile.

### 2026-08-15 — `effectif` retiré du contrat : la donnée n'existe pas
- **Contexte :** le bloc identité du contrat prévoyait `effectif` et
  `annee_effectif`.
- **Décision :** les retirer. L'annuaire ne publie aucun effectif. Les IVAL GT
  exposent bien `eff_2nde` / `eff_1ere` / `eff_term`, mais ce sont des effectifs
  de résultats propres aux lycées GT, pas une donnée d'identité comparable
  entre types d'établissement.
- **Réversibilité :** facile (une autre source pourrait la fournir plus tard).

### 2026-08-15 — Ports de lecture séparés des ports d'écriture
- **Contexte :** `ports.py` ne décrivait que le côté ingestion (`replace_all`,
  `append`).
- **Décision :** ajouter des ports de lecture distincts
  (`EstablishmentReader`, `IndicatorReader`, `SourceReferenceReader`) plutôt
  que d'élargir les dépôts existants. Rien de ce qui sert une requête HTTP ne
  doit pouvoir atteindre un `replace_all`. `SearchCriteria` n'a par
  construction aucun champ de tri : l'impossibilité de classer est structurelle,
  pas une vérification qu'un appelant pourrait oublier.
- **Réversibilité :** facile.

### 2026-08-15 — `source_reference` n'était alimentée par personne (lacune de Phase 1)
- **Contexte :** la table existait depuis la migration 0001 mais aucun code
  n'y écrivait. F10 (attribution de source) n'avait donc rien à lire.
- **Décision :** corriger rétroactivement — les adaptateurs exposent
  `source_references()` et l'ingestion les enregistre en fin de run réussi,
  dans la même transaction que les données. La date de publication vient de
  `data_processed` du catalogue ODS, et non de `modified`, qui bouge aussi sur
  une simple édition de métadonnées.
- **Réversibilité :** sans objet — correction d'un manque.

### 2026-08-15 — Connexion unique par requête, en lecture seule et REPEATABLE READ
- **Contexte :** une fiche d'établissement agrège trois requêtes. Empruntées
  séparément au pool, elles pouvaient encadrer un commit d'ingestion et livrer
  une identité d'avant le chargement avec des indicateurs d'après.
- **Décision :** le routeur emprunte une connexion pour toute la requête et la
  partage entre les lecteurs, dans une transaction REPEATABLE READ. Le pool est
  configuré en lecture seule : rien qui serve une requête HTTP n'a à écrire.
- **Alternatives écartées :** accepter la fenêtre d'incohérence, écartée — le
  projet applique déjà cette exigence côté écriture.
- **Réversibilité :** facile.

### 2026-08-15 — Revalidation humaine du contenu F3/F6/F7 récupéré
- **Contexte :** la reprise du travail Phase 2 ne permettait pas d'établir, à
  partir du dépôt seul, que la revue humaine obligatoire avait réellement eu
  lieu.
- **Décision :** le propriétaire du projet a relu et approuvé explicitement,
  sans modification, le contenu version 1 de
  `back/src/domain/explanatory_content.py` : les six blocs F3/F6, dont
  `valeur_non_disponible`, et le rappel de portée F7.
- **Alternatives écartées :** déduire l'approbation d'une mention écrite par un
  agent dans la documentation ; modifier le texte pendant la stabilisation.
- **Réversibilité :** toute évolution future du texte exige une nouvelle revue
  humaine explicite et une incrémentation de version.

### 2026-08-15 — Une fiche sans provenance est retenue et signalée en 503
- **Contexte :** le contrat impose une source pour chaque ligne de résultats,
  mais la première implémentation autorisait encore `source: null` si la table
  `source_reference` était incomplète.
- **Décision :** l'application lève une erreur d'intégrité, journalise le jeu
  de données, l'UAI et l'année concernés, puis l'API répond avec un message
  technique neutre et le statut 503. Aucun chiffre orphelin n'est publié.
- **Alternatives écartées :** retourner `source: null`, qui violerait F10 ;
  fabriquer une source de secours, qui briserait la traçabilité.
- **Réversibilité :** facile techniquement, mais contraire aux règles produit.

### 2026-08-15 — Référentiel officiel des communes ingéré avant les requêtes
- **Contexte :** le parcours Phase 3 doit comprendre « autour de Chaville » et
  les recherches par commune/code postal, mais l'API Phase 2 n'avait ni
  résolution de lieu ni centre de commune. Déduire un centre des coordonnées
  des établissements aurait inventé une donnée ; appeler un géocodeur à chaque
  requête aurait ajouté une dépendance réseau au chemin utilisateur.
- **Décision :** ingérer le référentiel officiel de `geo.api.gouv.fr` dans
  PostgreSQL avant les requêtes. Le payload complet est validé (schéma, codes
  uniques, tableaux de codes postaux, coordonnées et volume minimal de 30 000)
  avant toute publication. Un centre `null` reste `null`.
- **Atomicité :** les communes, les établissements, les références de source
  et l'audit du run partagent la même transaction. Le rollback restaure aussi
  les snapshots des communes et de la provenance.
- **Alternatives écartées :** géocodage à la volée ; centre moyen calculé à
  partir des établissements ; ajout d'un service ou cache réseau séparé.
- **Réversibilité :** facile côté adaptateur ; la table locale reste un port
  applicatif indépendant de la source HTTP.

### 2026-08-15 — Recherche textuelle déterministe limitée à l'identité
- **Contexte :** le langage naturel viendra en Phase 3, mais UAI, nom,
  commune et code postal doivent être résolus sans LLM et sans classement.
- **Décision :** la recherche porte uniquement sur l'identité et le site
  canonique, afin que la commune affichée soit toujours celle qui a correspondu.
  L'ordre est : niveau de correspondance factuelle, distance lorsqu'elle est
  fournie, puis clés alphabétiques/UAI stables. Aucun indicateur de résultat
  ne filtre ni n'ordonne.
- **Implémentation :** normalisation accent/casse et index trigrammes dans
  PostgreSQL (`unaccent`, `pg_trgm`, colonnes générées), sans Elasticsearch.
  Les réponses de recherche portent leur source officielle ; si elle manque,
  l'API retient tous les résultats et répond `503`.
- **Réversibilité :** facile pour les niveaux de correspondance ; toute
  extension doit rester factuelle et conserver la règle de neutralité.

### 2026-08-15 — Approbation humaine du contenu assistant version 1
- **Contexte :** le nouvel endpoint borné a besoin de quatre questions de
  clarification, d'un recentrage des demandes subjectives et d'un état
  explicite lorsque l'interpréteur LLM est indisponible. Aucun de ces textes ne
  doit être généré à la volée.
- **Décision :** le propriétaire du projet a approuvé explicitement le contenu
  version 1 de `back/src/domain/assistant_content.py`, sans modification. Les
  réponses du fournisseur ne sont jamais affichées : seules ces chaînes
  statiques peuvent parvenir à l'utilisateur.
- **Réversibilité :** toute évolution exige une nouvelle revue humaine et une
  incrémentation de `ASSISTANT_CONTENT_VERSION`.

### 2026-08-15 — Le tool assistant réutilise les cas d'usage, sans HTTP loopback
- **Contexte :** AGENT-1 exige que le LLM n'accède jamais directement à la
  base. Dans le monolithe, rappeler sa propre API par HTTP ajouterait une panne,
  une latence et une configuration réseau sans renforcer cette frontière.
- **Décision :** l'orchestrateur appelle les mêmes cas d'usage et schémas
  validés que les endpoints déterministes. Le fournisseur LLM ne reçoit aucun
  dépôt ni connexion et ne peut produire que le schéma `InterpretedSearch` ;
  seuls les adaptateurs PostgreSQL internes aux tools factuels lisent la base.
- **Alternative écartée :** boucle HTTP vers le même processus.
- **Réversibilité :** facile si les tools deviennent un service séparé plus tard.

### 2026-08-15 — Port d'interprétation indépendant du fournisseur, Anthropic en premier
- **Contexte :** la recherche complexe de Phase 3 a besoin d'une interprétation
  optionnelle, sans laisser un fournisseur produire des faits, des explications
  ou des critères implicites.
- **Décision :** l'application dépend du port neutre `QueryInterpreter` ; le
  premier adaptateur utilise Anthropic Messages. Clé, modèle, URL de base et
  délai sont configurés par l'environnement. L'adaptateur n'accepte qu'un seul
  appel forcé à un tool au schéma fermé, puis l'application vérifie
  indépendamment que chaque filtre de recherche rempli, ainsi que
  `needs_location=true`, est explicitement soutenu lexicalement par la demande
  originale ; `location_mode` et `needs_location=true` exigent en plus un
  marqueur de lieu exact ou de proximité reconnu. Le texte du fournisseur
  n'est jamais affiché.
- **Alternative écartée :** importer un SDK/comportement propre au fournisseur
  dans `domain` ou `application`, accepter une réponse libre, ou considérer un
  champ valide au seul motif qu'il respecte le schéma JSON.
- **Réversibilité :** un autre adaptateur peut implémenter le même port ; le
  contrat applicatif et les réponses HTTP restent inchangés.

### 2026-08-15 — Cache d'interprétations validées local au processus
- **Contexte :** les requêtes complexes répétées ne doivent pas repayer une
  interprétation LLM identique, mais mettre en cache les faits officiels
  risquerait de publier des résultats périmés après ingestion.
- **Décision :** conserver uniquement les objets `InterpretedSearch` validés
  dans un cache mémoire thread-safe TTL/LRU borné (256 entrées, 900 secondes
  par défaut, valeurs configurables par environnement). La clé opaque combine
  requête normalisée, fournisseur/modèle/version du prompt/digest du schéma,
  puis versions des sources et contenus éditoriaux. L'insertion intervient
  après la validation applicative ; erreurs fournisseur et interprétations
  invalides ne sont jamais stockées. Résolution de commune, recherche
  d'établissements et contrôles de provenance s'exécutent à chaque requête.
- **Invalidation :** une modification de référence source, contenu,
  fournisseur, modèle, version de prompt (`PROMPT_VERSION` est incrémenté avec
  le prompt) ou schéma produit une nouvelle clé ; les anciennes entrées
  expirent ensuite par TTL/LRU plutôt que par purge synchrone.
- **Alternatives écartées :** Redis, cache distribué et cache de réponses
  factuelles, non justifiés ou incompatibles avec l'actualisation des faits.
- **Limites acceptées :** cache indépendant par worker, froid au redémarrage et
  sans single-flight ; deux misses simultanés peuvent dupliquer un appel sans
  affecter la correction.

### 2026-08-15 — CI backend avec PostGIS jetable, sans fournisseur live
- **Contexte :** AGENT-3 exige l'exécution systématique de la suite
  adversariale et des gates backend, y compris les tests d'intégration qui
  détruisent leurs tables.
- **Décision :** GitHub Actions lance `Backend quality gates` sur chaque pull
  request et push vers `main`, avec permission dépôt en lecture seule et
  annulation des runs dépassés sur la même ref. Le job utilise Python 3.12 et
  `postgis/postgis:16-3.4`, avec des URL dédiées à `schools_db_test`. Il migre
  à head avant `pytest -ra`, puis exécute Ruff lint/format et `mypy src` depuis
  `back/`.
- **Déterminisme et secrets :** aucune clé Anthropic ni source publique live
  n'entre dans le job normal ; les contrats fournisseur restent mockés. Cela
  évite coût, variabilité réseau et exposition d'un secret.
- **Statut de preuve :** le workflow est configuré et son équivalent local a
  passé 510 tests sans skip, mais aucun run GitHub hébergé réussi n'a encore été
  observé. La présence du fichier ne clôt donc pas seule AGENT-3/Phase 3.

### 2026-08-16 — Un refus de classer n'est pas une panne
- **Contexte :** une demande purement subjective sans critère factuel
  exploitable (« Quel est le meilleur collège ? », sans commune ni type ni
  secteur) renvoyait le message générique « L'interprétation en langage naturel
  n'est pas disponible ». Le drapeau `subjective` était perdu lorsque
  `_validate_intent` rejetait l'intention.
- **Constat :** aucun classement n'était produit et aucun mot évaluatif n'était
  émis — la charte n'était donc pas enfreinte. Mais le produit présentait un
  **refus délibéré** comme une **panne technique**, et la réponse prévue par la
  charte (§ 12, « Ce service ne classe pas et ne recommande pas les
  établissements ») n'atteignait jamais l'utilisateur dans le cas précis pour
  lequel elle existe.
- **Décision :** distinguer deux causes dans `AssistantSearchUnavailable`
  (`UnavailableReason`) : `PROVIDER_UNAVAILABLE` (le fournisseur est
  injoignable — une panne que nous assumons) et `INTERPRETATION_REJECTED` (nous
  avons obtenu une interprétation et l'avons écartée — un refus). Le
  sérialiseur choisit alors entre deux textes **déjà approuvés** ; aucun
  nouveau contenu éditorial n'a été rédigé, donc aucune nouvelle validation
  humaine n'était requise.
- **Point subtil :** en cas de panne réelle sur une requête subjective, le
  message reste celui de la panne — mentir sur la cause dans l'autre sens
  serait la même faute — mais la position du service sur le classement est
  portée par `reformulation_neutre`. Une panne ne doit pas devenir un moyen de
  ne pas dire que nous ne classons pas.
- **Alternatives écartées :** afficher systématiquement la reformulation dès
  qu'une requête est subjective, écartée car elle aurait masqué les pannes
  réelles ; rédiger un troisième message, écartée car elle aurait exigé une
  nouvelle revue éditoriale pour un gain nul.
- **Réversibilité :** facile.

---

## Décisions de la Phase 4 — Frontend MVP

### 2026-08-16 — CORS ajouté au backend, plutôt qu'un proxy Vite
- **Contexte :** le frontend est servi sur `:5173` et l'API sur `:8000`. Aucun
  middleware CORS n'existait ; vérifié sur le service en marche, un préflight
  renvoyait 405 et aucun en-tête `access-control-*` n'était émis. Le navigateur
  aurait refusé chaque appel.
- **Décision :** ajouter `CORSMiddleware`, origines lues dans la configuration.
  Écarté : le proxy du serveur de développement Vite, qui ne résout que le
  développement — un bundle compilé n'a plus de serveur de développement — et
  qui rendrait l'application *same-origin* en local et *cross-origin* en
  production, soit exactement la divergence d'environnement que le patron de
  configuration du projet cherche à éviter.
- **Point subtil :** la configuration CORS vit dans une classe `CorsSettings`
  distincte. Le middleware doit être installé à la construction de
  l'application, donc à l'import ; or `Settings.database_url` est
  volontairement obligatoire. Passer par `Settings` rendait `main` impossible à
  importer sans base de données configurée et cassait la collecte des tests.
- **Réversibilité :** facile.

### 2026-08-16 — Neutralité imposée par la structure des composants
- **Contexte :** la charte (§ 9) interdit une liste de procédés visuels. Une
  simple discipline de relecture ne suffit pas : le raccourci fautif (colorer
  une valeur, trier par résultat) est toujours le plus commode à écrire.
- **Décision :** rendre le mauvais geste difficile à écrire, pas seulement
  interdit.
  - `Figure` est le seul composant autorisé à afficher un résultat chiffré, et
    n'expose **aucune** propriété `variant` / `tone` / `status`. Rien ne peut
    lui être transmis signifiant « bon » ou « mauvais ».
  - `source` y est une propriété **obligatoire** : aucun chemin de code
    n'affiche un nombre sans sa provenance.
  - Le texte d'une absence est un bloc renvoyé par l'API, jamais une phrase
    écrite dans le frontend — le composant ne peut donc pas attribuer une cause.
  - `SearchHit` ne porte aucun indicateur : la liste de résultats ne peut pas
    être triée ni colorée par une valeur, faute de donnée à brancher.
  - Aucun contrôle de tri n'existe sur la page de résultats, pas même désactivé.
  - `tokens.css` ne contient aucun couple rouge/vert. L'ambre signale une
    précaution méthodologique, le rouge une erreur technique — jamais un chiffre.
- **Alternatives écartées :** une bibliothèque de composants (MUI), écartée car
  ses primitives de « mise en avant », badges et notations sont à une propriété
  près d'enfreindre la charte.
- **Réversibilité :** coûteuse une fois des composants dérivés écrits.

### 2026-08-16 — Le tri appliqué est annoncé, jamais deviné
- **Contexte :** l'API classe par correspondance, proximité ou ordre
  alphabétique, et le renvoie dans `tri`.
- **Décision :** afficher en toutes lettres l'ordre appliqué (« Par
  correspondance avec votre recherche, puis par proximité »). Un lecteur qui
  ignore l'ordre d'une liste peut y lire un classement ; l'annoncer supprime
  l'ambiguïté et rend visible qu'aucune des options ne dépend d'un résultat.
- **Réversibilité :** facile.

### 2026-08-16 — Le rappel de portée d'accueil vit dans le frontend, sous contrôle
- **Contexte :** la charte (§ 7) définit deux textes de rappel : une « version
  courte », accompagnant les résultats, et une « version d'accueil ». Le
  backend n'implémente que la première (`SCOPE_DISCLAIMER`), servie avec chaque
  réponse. La page d'accueil énonce sa promesse *avant* toute recherche : il
  n'y a donc aucune réponse d'API pour la porter.
- **Décision :** reproduire la version d'accueil dans `front/src/content/copy.ts`
  et dans la balise `description` de `index.html`, **et faire de la charte la
  source de vérité vérifiée** : deux tests lisent
  `docs/14_Charte_Neutralite_Editoriale.md` et échouent si l'un ou l'autre texte
  s'en écarte d'un caractère. `index.html`, qui échappait au balayage, est
  désormais inclus.
- **Alternatives écartées :** exposer le texte via un nouvel endpoint, écarté —
  cela ferait dépendre d'un aller-retour réseau la phrase la plus importante de
  la page d'accueil, pour une chaîne constitutionnellement figée ; laisser la
  copie sans garde-fou, écarté — c'est précisément la dérive que la revue de
  neutralité a signalée.
- **Point subtil :** les tests frontend doivent donc être lancés avec la racine
  du dépôt montée, pas seulement `front/`, sinon la charte est introuvable.
  Documenté dans CLAUDE.md.
- **Réversibilité :** facile.

### 2026-08-16 — La comparaison est alignée côté serveur, pas côté client
- **Contexte :** la charte (§ 11) interdit de calculer un écart global, un
  nombre de critères remportés, une moyenne, un score pondéré, un verdict ou
  une recommandation. Le contrat esquissé en Phase 1 renvoyait deux fiches
  brutes (`{establishments: [A, B]}`) et laissait le client les apparier par
  année.
- **Décision :** aligner les lignes dans le backend. Remettre deux fiches
  brutes place les deux valeurs d'une même année côte à côte **dans le code
  client** — précisément l'endroit où les soustraire devient la ligne suivante
  la plus naturelle. Pré-alignées, les cellules se rendent une à une et le
  client ne détient jamais une paire en attente d'opération. Même raisonnement
  que l'absence de propriété `variant` sur `Figure` : rendre le geste interdit
  impossible à écrire, plutôt que simplement non écrit.
- **Union des années, pas intersection :** un lycée (IVAL, dès 2012) face à un
  collège (IVAC, dès 2022) produit les 14 lignes. L'intersection masquerait dix
  années réellement publiées pour rendre le tableau plus net.
- **Une année non publiée n'est pas une valeur absente :** deux contenus
  éditoriaux distincts. Une colonne vide à côté d'une colonne remplie se lit
  comme une défaite, alors qu'elle ne signifie souvent que « IVAC commence plus
  tard ».
- **Point de vigilance :** le mot « écart » apparaît légitimement dans la
  définition de la valeur ajoutée (écart entre résultat observé et attendu).
  Les contrôles automatiques interdisent donc ces termes sur les **clés**, et
  exemptent le bloc `explications` — tout en vérifiant que ce bloc est
  identique, octet pour octet, à celui servi par la fiche, pour que l'exemption
  ne serve pas à faire passer un texte réécrit.
- **`MAX_COMPARED = 2` :** doc 07 dit « deux (max trois) », mais doc 01 (F4) et
  doc 13 § 9 disent deux, et la maquette mobile de doc 13 suppose deux colonnes
  A/B. Les deux spécifications les plus détaillées l'emportent.
- **Réversibilité :** coûteuse une fois le contrat publié.

### 2026-08-16 — Approbation humaine du contenu éditorial de la Phase 5
- **Contexte :** la Phase 5 introduit une quantité importante de contenu
  éditorial nouveau, montré tel quel aux lecteurs. Comme
  `explanatory_content.py` (entrée du 15/08) et `assistant_content.py` (même
  date), il relève de l'étape de revue humaine explicite prévue par
  `CLAUDE.md`.
- **Contenu relu et approuvé par le propriétaire du projet, version 1 :**
  - `back/src/domain/glossary_content.py` — 16 termes. Cinq sont **dérivés**
    des blocs `ExplanatoryContent` existants (une seule rédaction de « ce
    qu'est la valeur ajoutée », pas deux qui divergeraient) ; onze sont
    nouvellement rédigés : UAI, DEPP, IVAC, IVAL, annuaire, secteur, filière,
    ULIS, SEGPA, seuil de diffusion, valeur non disponible.
  - `back/src/domain/explanatory_content.py` — nouveau bloc
    `YEAR_NOT_PUBLISHED` (`annee_non_publiee`), distinct de `ABSENT_VALUE`.
  - `back/src/domain/methodology_break.py` — note de rupture 2021.
  - `front/src/content/copy.ts` — sections HISTORY, COMPARE, GLOSSARY, SHARE.
- **Deux formulations méritent d'être signalées, car elles sont les plus
  proches de la règle F6 :** `seuil_de_diffusion` précise explicitement qu'il
  n'est **pas** le seul motif d'absence (la DEPP en documente trois, et
  l'export ouvert n'indique jamais lequel s'applique) ; `valeur_non_disponible`
  répète qu'une absence ne permet aucune conclusion. Un test interdit par
  ailleurs tout verbe de conseil (choisir, éviter, privilégier, conseiller)
  dans l'ensemble du glossaire.
- **Réversibilité :** facile côté texte ; le `version` de chaque entrée permet
  de détecter une modification ultérieure non relue.

### 2026-08-16 — Un export abrégé est un export non conforme
- **Contexte :** la page de comparaison n'imprimait que trois des six parties
  exigées par la charte (§ 4) pour chaque explication, là où la fiche en
  imprimait six. Elle perdait `comment_lire` et `methode` — soit, pour une
  absence, les phrases disant qu'elle « ne signifie ni un résultat élevé, ni un
  résultat faible » et qu'aucune valeur n'est jamais substituée.
- **Constat :** aucune alerte. Les tests d'impression ne couvraient que la
  fiche ; la seconde surface n'était pas testée du tout.
- **Décision :** rendre les deux blocs d'impression identiques, et tester la
  comparaison en affirmant qu'elle imprime **les mêmes** six parties que la
  fiche, plutôt que de les comparer à une liste écrite à la main qui pourrait
  dériver à son tour. Vérifié par mutation : le retrait du correctif fait
  échouer exactement les deux nouveaux tests.
- **Leçon retenue :** un critère d'acceptation formulé « intégralement » exige
  un test par surface d'export, pas un test par fonctionnalité.
- **Réversibilité :** sans objet — correction.
