# Résultats du spike technique

*Document rempli à l'issue du spike de Phase 0 (voir `06_Implementation_Roadmap.md`).
Ses constats font foi : en cas de contradiction avec une observation ultérieure,
signaler l'écart plutôt que réécrire ce fichier silencieusement (cf. `CLAUDE.md`,
section « Boundaries »).*

**Date d'exécution :** 15 août 2026
**Méthode générale :** exécution nationale (et non sur un seul département) via
l'endpoint `/exports/json` de l'API Explore v2.1. Les volumes réels (68 k
établissements, ~88 k lignes d'indicateurs) tiennent en mémoire, ce qui permet
de mesurer la population entière plutôt qu'un échantillon. Un taux limite mesuré
sur un seul département n'aurait pas permis de trancher un go/no-go.
**Scripts (jetables) :** `scripts/spike/` — voir le README de ce dossier.

---

## 0. Correctifs de référence apportés aux sources

Le glossaire ne listait pas l'identifiant du jeu de données IVAC, et les
anciennes versions des jeux IVAL (nécessaires à la section 2) n'y figuraient
pas. Identifiants confirmés en catalogue :

| Rôle | `dataset_id` | Lignes | Millésimes |
|---|---|---:|---|
| Annuaire | `fr-en-annuaire-education` | 67 896 | — |
| IVAC (collèges) | `fr-en-indicateurs-valeur-ajoutee-colleges` | 26 869 | 2022–2025 |
| IVAL GT | `fr-en-indicateurs-de-resultat-des-lycees-gt_v2` | 32 485 | 2012–2025 |
| IVAL PRO | `fr-en-indicateurs-de-resultat-des-lycees-pro_v2` | 28 258 | 2012–2025 |
| IVAL GT (ancienne version) | `fr-en-indicateurs-de-resultat-des-lycees-denseignement-general-et-technologique` | 27 808 | 2012–2023 |
| IVAL PRO (ancienne version) | `fr-en-indicateurs-de-resultat-des-lycees-denseignement-professionnels` | 24 236 | 2012–2023 |

---

## 1. Jointure Annuaire ↔ IVAC/IVAL (clé UAI)

- **Date du test :** 15 août 2026
- **Méthode :** extraction intégrale des quatre jeux de données, puis jointure
  sur l'UAI (`identifiant_de_l_etablissement` côté annuaire, `uai` côté
  indicateurs), sur le millésime le plus récent (2025).

### Précision de méthode : le dénominateur

L'annuaire contient 67 896 établissements de tous niveaux, dont 47 947 écoles
primaires que les IVAC/IVAL ne couvrent pas par construction. Rapporter les
correspondances à ce total produirait un « taux de jointure » d'environ 10 %,
dénué de sens. Deux questions distinctes ont donc été mesurées séparément :

- **A — Fiabilité de la jointure :** parmi les UAI présents dans un jeu
  d'indicateurs, combien retrouvent une fiche d'annuaire ? C'est la question
  qui décide de la faisabilité du produit.
- **B — Couverture :** parmi les établissements éligibles de l'annuaire
  (collège / lycée / EREA, état `OUVERT` — **14 621 UAI distincts**, pour
  14 692 lignes : l'écart de 71 correspond aux doublons multi-sites décrits en
  section 3), combien disposent d'indicateurs ? C'est une question de périmètre
  produit, pas un défaut de jointure.

Une ligne dont la valeur ajoutée est nulle **compte comme une jointure
réussie** : la ligne existe, seule la valeur est légitimement non diffusée.

### Résultat A — fiabilité de la jointure

| Source (millésime 2025) | Lignes | UAI distincts | Rattachés à l'annuaire |
|---|---:|---:|---:|
| IVAC (collèges) | 6 816 | 6 816 | 6 729 — **98,72 %** |
| IVAL GT | 2 346 | 2 346 | 2 323 — **99,02 %** |
| IVAL PRO | 2 014 | 2 014 | 1 990 — **98,81 %** |
| **Total** | **11 176** | — | **11 042 — 98,80 %** |

- **Taux de correspondance fiable obtenu :** **98,80 %**
- **Seuil de qualité visé :** 90 % (cf. `02_Architecture_Decisions.md`)
- **Verdict go/no-go :** **GO**, avec une marge confortable.

### Analyse des non-correspondances

Sur 119 UAI non rattachés, **114 relèvent de deux départements seulement** :
Var (83) — 71 cas — et Vaucluse (84) — 43 cas. La cause n'est pas la clé de
jointure mais **une lacune de l'annuaire lui-même** :

| Département | Lignes dans l'annuaire | Dont écoles |
|---|---:|---:|
| Var (83) | 120 | 50 |
| Vaucluse (84) | 213 | 122 |
| *Médiane métropolitaine* | *605* | — |
| *Lozère (48), dép. le moins peuplé* | *152* | — |

Le Var, département d'environ un million d'habitants, compte moins de fiches
que la Lozère. L'annuaire y est manifestement incomplet à la date du test.
Hors ces deux départements, seuls **5 UAI** sur 11 176 lignes restent
inexpliqués, soit un taux de défaut de clé résiduel de l'ordre de **0,04 %**.

**La clé UAI est donc fiable. Le risque réel est la complétude de l'annuaire,
pas la jointure.**

### Conséquences pour la suite

1. Le ticket DATA-4 impose déjà de journaliser les établissements non
   rattachés plutôt que de les écarter silencieusement : c'est confirmé comme
   nécessaire, pas théorique.
2. DATA-5 doit traiter **une chute du taux de rattachement** comme un signal
   d'alerte au même titre qu'un échec de requête : la référence mesurée est
   98,8 %, un passage sous ~95 % doit alerter.
3. La page « Méthodologie et transparence » (doc 12, § 11) doit annoncer la
   couverture réelle mesurée, y compris ce déficit départemental.

### Résultat B — couverture (question de périmètre, pas de jointure)

Part des établissements éligibles disposant d'indicateurs, tous millésimes :

| Type | Couverts | Total | Part |
|---|---:|---:|---:|
| Collège | 6 771 | 9 019 | 75,1 % |
| Lycée | 3 605 | 5 524 | 65,3 % |
| EREA | 8 | 78 | 10,3 % |

Détail par statut (collèges : public 77,4 %, privé 68,3 % ; lycées : public
72,0 %, privé 54,6 %). Le secteur privé n'est donc **pas** structurellement
absent des indicateurs — l'hypothèse d'une exclusion nette du hors-contrat est
infirmée ; l'écart est graduel.

**Conséquence produit :** entre un quart et un tiers des fiches d'établissement
n'afficheront aucun indicateur. L'état D04 de l'inventaire des écrans
(« Aucune donnée compatible actuellement intégrée ») n'est pas un cas marginal
mais un cas courant, à traiter comme tel dans les maquettes.

---

## 2. Continuité méthodologique des IVAL (ancienne vs nouvelle version)

- **Date du test :** 15 août 2026
- **Méthode :** comparaison des métadonnées, des schémas de champs, des
  effectifs par millésime, puis comparaison **valeur par valeur** sur l'année
  de recouvrement la plus récente (2023) pour 200 établissements par série.

### Constat

Trois natures de rupture ont été distinguées, car elles n'ont pas les mêmes
conséquences pour l'interface :

**a) Rupture de publication — avérée, sans effet utilisateur.**
Les jeux `_v2` republient la même série sous des noms de champs différents :

| Ancienne version | Version `_v2` |
|---|---|
| `code_etablissement` | `uai` |
| `taux_brut_de_reussite_total_series` | `taux_reu_total` |
| `taux_acces_brut_seconde_bac` | `taux_acces_2nde` |
| `effectif_presents_total_series` | `presents_total` |
| 145 champs (GT) / 130 (PRO) | 88 champs |

`va_reu_total` est typé **texte** dans l'ancienne version et **numérique**
dans la `_v2` (`"-5"` vs `-5.0`).

**b) Rupture de valeurs — aucune.**
Sur les 12 millésimes de recouvrement (2012–2023), les effectifs par année
sont **identiques des deux côtés** (12/12). Sur l'année 2023 :

| Série | Valeurs comparées | Écarts |
|---|---:|---:|
| GT | 800 | **0** |
| PRO | 600 | **0** |

La DEPP n'a pas recalculé la série : la `_v2` est une republication étendue
à 2024 et 2025. **Un historique continu 2012–2025 est donc méthodologiquement
défendable au niveau des indicateurs « total ».**

**c) Rupture de périmètre — avérée, à afficher.**
Les sous-indicateurs par série changent à la réforme du baccalauréat :

| Millésimes | Séries présentes | Indicateurs « total » |
|---|---|---|
| 2012–2020 | L, ES, S (+ séries techno) | renseignés |
| 2021–2025 | « générale » (`gnle`) uniquement | renseignés |

Dernière année avec L/ES/S : **2020**. Première année avec « générale » :
**2021**.

### Rupture(s) identifiée(s) et année(s) concernée(s)

- **2021** — réforme du baccalauréat : les séries L/ES/S disparaissent au
  profit d'une voie générale unique. Rupture **des sous-séries uniquement**.
- Aucune rupture sur `taux_reu_total`, `va_reu_total`, `taux_acces_2nde`, qui
  restent renseignés sur les 14 millésimes.

### Décision sur l'affichage de l'historique (F5)

1. L'historique F5 s'appuie sur les **indicateurs de niveau « total »**, seuls
   continus sur 2012–2025. C'est ce que le contrat d'API expose déjà.
2. Un historique par série n'est **pas** proposé au MVP. S'il l'était un jour,
   la courbe devrait être interrompue en 2021 et les deux périodes non reliées
   (cf. doc 11, § 8).
3. Une annotation neutre marque néanmoins 2021 sur l'axe, car la composition
   des candidats change même si l'agrégat reste comparable. Formulation à
   verser au contenu éditorial versionné, à valider par un humain avant
   publication (voir `CLAUDE.md`, workflow « Explanatory content change »).
4. `08_API_Contract.md` conserve le champ `methodology_breaks` : il portera
   l'année 2021 avec sa note, et non l'année 2019 de l'exemple provisoire.

### IVAC — pas de sujet équivalent

Un seul jeu de données, aucun renommage, **4 millésimes seulement (2022–2025)**.
L'écart de profondeur historique entre collèges (4 ans) et lycées (14 ans) est
une propriété de la source, à énoncer explicitement dans l'interface.

---

## 3. Prototype minimal du pipeline d'ingestion

- **Date du test :** 15 août 2026
- **Méthode :** chargement complet dans le PostgreSQL/PostGIS local
  (`docker compose up -d db`) via des tables préfixées `spike_`.

### Volume réel constaté

| Jeu | Lignes | Taille JSON estimée | Temps d'extraction |
|---|---:|---:|---:|
| Annuaire (11 champs) | 67 896 | ~14 MB | 3,9 s |
| IVAC | 26 869 | ~4,7 MB | 1,6 s |
| IVAL GT | 32 485 | ~5,1 MB | 2,3 s |
| IVAL PRO | 28 258 | ~4,4 MB | 1,9 s |

En base : **9,1 Mo** pour les établissements, **12 Mo** pour 87 612 lignes
d'indicateurs. Le volume total du projet se compte en **dizaines de mégaoctets**.
Cela confirme le verdict du comité d'architecture : le problème n'est pas
volumétrique, et toute infrastructure supplémentaire resterait injustifiée.

### Temps d'ingestion complet observé

Extraction complète des quatre sources : **< 10 secondes**.
Chargement en base par `executemany` naïf : **153 s** (établissements) et
**199 s** (indicateurs), soit ~440 lignes/s. C'est le seul poste coûteux, et il
est purement dû à la méthode d'insertion. **Recommandation pour DATA-3/DATA-4 :
utiliser `COPY` ou `execute_values`** ; l'ingestion complète doit alors
descendre bien en dessous de la minute. Aucune justification à un traitement
asynchrone ou à une file de messages.

### Problèmes rencontrés

**1. L'UAI n'est pas une clé unique dans l'annuaire — 74 doublons.**
Des établissements multi-sites partagent un même UAI :

```
0250047R  Collège Olympe de Gouges site de Pont de Roide (Pont-de-Roide)
0250047R  Collège Olympe de Gouges site de Saint-Hyppolyte (Saint-Hippolyte)
```

Le modèle de données esquissé dans `02_Architecture_Decisions.md` fait de
`uai` la clé de `Etablissement`. **DATA-2 doit trancher une règle de
déduplication avant de poser cette clé primaire** (champs `multi_uai` et
`etablissement_mere` de l'annuaire à examiner). Côté indicateurs en revanche,
le couple `(uai, année)` est **strictement unique** sur les trois jeux
(0 doublon sur 87 612 lignes) : le stockage append-only prévu pour F5 est
valide tel quel.

**2. Le seuil de non-diffusion ne s'observe pas comme documenté.**
La règle du glossaire (<20 candidats GT, <10 PRO) a été confrontée aux données
en utilisant `presents_total` comme effectif :

| Jeu | Lignes sous le seuil | ... portant malgré tout une valeur | Lignes au-dessus du seuil sans valeur |
|---|---:|---:|---:|
| IVAL GT (20) | 78 | 75 | 457 |
| IVAL PRO (10) | 24 | 21 | 472 |
| IVAC (20, `nb_candidats_g`) | 0 | 0 | 1 784 |

Deux causes identifiées :

- Les 75 lignes GT « sous le seuil mais avec valeur » appartiennent **toutes à
  2016**, anomalie ponctuelle de la source.
- Parmi les 186 lignes GT à 50 candidats ou plus sans valeur ajoutée,
  **113 concernent Mayotte (UAI en `976`)** : la valeur ajoutée n'y est pas
  calculée, pour une raison indépendante de l'effectif.

**Conséquence directe et importante pour F6 / API-4 :** le backend ne doit
**pas** dériver `sous_seuil_diffusion` d'un comptage de candidats, et
l'interface ne doit pas affirmer que toute valeur absente l'est « en raison du
seuil d'effectif ». Ce serait factuellement faux dans une part notable des cas,
et contraire au principe de traçabilité comme à la charte de neutralité
(doc 14, § 6 : ne pas transformer une absence en signal, ni lui prêter une
cause non présente dans la source).

L'absence doit être reprise **telle que la source la livre**, et le motif
affiché doit distinguer au minimum :
« valeur non diffusée » (motif publié par la DEPP) et
« valeur non disponible pour cet établissement » (motif non précisé par la
source). Le libellé exact relève du contenu éditorial versionné et doit être
validé par un humain — et la sémantique précise du seuil doit être confirmée
sur la documentation méthodologique DEPP avant de figer le texte de F6.

**3. Géolocalisation :** 133 lignes éligibles sur 14 692 (**0,91 %**) n'ont pas
de latitude/longitude. La recherche par proximité doit les traiter sans échouer,
et la fiche rester accessible. *(Décompte en lignes, non dédoublonné — soit
14 621 UAI distincts, cf. section 1.)*

**4. Détails techniques d'API à reporter en Phase 1 :**
- `/records` plafonne à 100 lignes par page avec un plafond d'`offset` :
  il ne permet pas de parcourir un jeu complet. **`/exports/json` est le seul
  endpoint viable** pour une extraction intégrale.
- L'endpoint de métadonnées renvoie du **gzip même lorsque la requête demande
  `Accept-Encoding: identity`**, contrairement à `/records` et `/exports`.
- Les champs `annee` (IVAL `_v2`) et `session` (IVAC) sont des **dates ISO**
  (`"2025-01-01T00:00:00+00:00"`), pas des entiers ; l'ancienne version des
  IVAL utilise, elle, un entier.
- Taux de valeurs nulles notables : `nb_candidats_p` / `taux_de_reussite_p`
  (IVAC) à 69 %, `statut_public_prive` (annuaire) à 2,9 %.

---

## Verdict global du spike

**Go / No-go pour la suite du développement : GO.**

Les deux hypothèses les plus risquées sont levées :

1. La jointure par UAI est fiable à **98,80 %**, très au-dessus du seuil de
   90 %. Les non-correspondances s'expliquent par une lacune de l'annuaire sur
   deux départements, non par la clé.
2. Les séries IVAL sont **continues en valeurs** sur 2012–2025 ; la seule
   rupture réelle porte sur les sous-séries, en 2021.

Le volume confirme qu'une architecture monolithique simple est le bon choix.

### Ajustements nécessaires avant la V1

| # | Ajustement | Ticket concerné |
|---|---|---|
| 1 | Trancher la déduplication des UAI multi-sites avant de poser la clé primaire | DATA-2 |
| 2 | Ne pas calculer `sous_seuil_diffusion` ; reprendre l'absence de la source et distinguer les motifs | DATA-4, API-4 |
| 3 | Confirmer la sémantique exacte du seuil sur la documentation méthodologique DEPP avant de figer le texte F6 | API-3 / API-4 |
| 4 | Utiliser `COPY` / `execute_values` plutôt qu'un `executemany` naïf | DATA-3, DATA-4 |
| 5 | Alerter sur une chute du taux de rattachement (référence 98,8 %, seuil d'alerte ~95 %) | DATA-5 |
| 6 | Porter l'année 2021 dans `methodology_breaks` (et non 2019) | API-7 |
| 7 | Traiter l'état « aucun indicateur » comme un cas courant (25–35 % des fiches), pas marginal | FE-2 |
| 8 | Annoncer la couverture réelle mesurée, déficit Var/Vaucluse compris | Page méthodologie |

### Limite assumée de ce spike

Le test de non-régression sur changement de schéma source exigé par `CLAUDE.md`
pour les adaptateurs d'ingestion **n'est pas couvert ici**. Les scripts de spike
portent des assertions d'exécution (`check_fields_present`) qui interrompent le
run si un champ attendu disparaît, mais il ne s'agit pas d'une suite de tests
automatisée. **Cette exigence reste entièrement à satisfaire en Phase 1
(DATA-3/4/5)** — voir l'entrée correspondante du journal de décisions.
