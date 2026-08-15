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
