# Glossaire métier — sources et données

*Document stable, change rarement. À mettre à jour uniquement si une source officielle change de terminologie.*
*Dernière mise à jour : Août 2026*

---

## Organismes et sources

**DEPP** — Direction de l'évaluation, de la prospective et de la performance. Service statistique du ministère de l'Éducation nationale, producteur des IVAC/IVAL.

**RAMSESE** — Répertoire académique et ministériel sur les établissements du système éducatif. Base source de l'annuaire de l'éducation.

**Opendatasoft** — Moteur technique utilisé par data.education.gouv.fr, exposant une API REST standardisée (Explore API v2.1).

## Identifiants et indicateurs

**UAI** — Identifiant officiel d'un établissement scolaire (Unité Administrative Immatriculée). Clé de jointure entre l'annuaire et les indicateurs de résultats, **confirmée fiable à 98,80 % par le spike technique** (15 août 2026).

> Attention : l'UAI **n'est pas unique dans l'annuaire** — 74 identifiants y
> apparaissent deux fois, des établissements multi-sites partageant un même UAI.
> Il ne peut donc pas servir de clé primaire sans règle de déduplication
> préalable (ticket DATA-2). Côté indicateurs en revanche, le couple
> `(uai, année)` est strictement unique. Voir
> `05_Resultats_Spike_Technique.md`, section 3.

**IVAC** — Indicateurs de Valeur Ajoutée des Collèges. Disponibles pour les années 2022 à 2025. Mesurent l'écart entre les résultats obtenus par les élèves au diplôme national du brevet et les résultats statistiquement attendus compte tenu de leur profil scolaire et social à l'entrée.

**IVAL** — Indicateurs de Valeur Ajoutée des Lycées. Disponibles pour les années 2012 à 2025 (deux séries : générale/technologique et professionnelle). Même logique que les IVAC, appliquée au baccalauréat et au parcours au lycée.

**Valeur ajoutée** — Différence entre les résultats obtenus par un établissement et les résultats attendus statistiquement, compte tenu des caractéristiques scolaires et sociodémographiques des élèves accueillis. Une valeur positive signifie des résultats supérieurs à l'attendu ; négative, l'inverse. Ne mesure ni l'ambiance, ni la qualité de vie scolaire, ni des critères individuels à l'enfant.

**Taux de réussite** — Proportion d'élèves reçus à l'examen (brevet ou baccalauréat) parmi les élèves présentés.

**Taux d'accès** — Probabilité qu'un élève entré dans l'établissement (en 2nde pour un lycée, par exemple) atteigne et réussisse l'examen terminal.

**Taux de mention** — Proportion de lauréats ayant obtenu une mention à l'examen.

## Règles de diffusion des données (contrainte métier importante)

> **Corrigé le 15/08/2026 (API-4)** sur la documentation officielle de la DEPP.
> La version précédente de cette section énonçait « 20 candidats en GT, 10 en
> PRO » comme *le* seuil de la valeur ajoutée. **C'est le seuil des taux bruts,
> pas celui de la valeur ajoutée**, et il a changé depuis. Voir
> `04_Journal_Decisions.md`, entrée « Sémantique DEPP de l'absence confirmée ».

Il faut distinguer deux seuils différents :

**Taux bruts** (réussite, mention) — non diffusés en dessous de **20 candidats**
en série générale/technologique et **10** en série professionnelle.

**Valeur ajoutée et taux attendus** — seuils plus stricts, et **relevés à
partir de la session 2024** :
- lycées généraux et technologiques : **40 candidats** (20 auparavant)
- lycées professionnels : **20 candidats** (10 auparavant)
- collèges, série générale du DNB : **40 candidats** (30 auparavant)

Cette règle existe pour préserver la fiabilité statistique sur de petits effectifs. Elle doit être respectée et explicitée dans le produit (cf. fonctionnalité F6), jamais contournée ou estimée en interne.

> **Le seuil n'est pas le seul motif d'absence, et aucun motif n'est publié.**
> Le *Guide méthodologique IVAC 2025* (« Conditions de publication des
> indicateurs ») en documente trois : effectif insuffisant, informations
> retrouvées pour moins de 75 % des élèves, et Mayotte (taux attendus non
> calculés). La DEPP les code `ND` ou `NS` — **mais ces codes ne survivent pas
> à la publication en open data** : les trois cas arrivent en cellule vide.
> Le produit ne doit donc **pas** dériver l'absence d'un comptage de candidats,
> ni attribuer un motif particulier à une valeur manquante. C'est ce que
> mesurait déjà le spike (`05_Resultats_Spike_Technique.md`, section 3,
> problème n°2) ; la documentation officielle en donne l'explication.

## Typologie des établissements

**Statut** : public / privé sous contrat / privé hors contrat.

**Types de dispositifs et sections rencontrés dans les données** :
- **ULIS** — Unité Localisée pour l'Inclusion Scolaire
- **SEGPA** — Section d'Enseignement Général et Professionnel Adapté
- **EREA** — Établissement Régional d'Enseignement Adapté
- **REP / REP+** — Réseau d'Éducation Prioritaire (renforcé)
- Sections particulières : internationale, européenne, sport-études, arts, cinéma, théâtre

## Sources API techniques (référence rapide)

Base : `https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/{dataset_id}`

| Rôle | `dataset_id` |
|---|---|
| Annuaire de l'éducation | `fr-en-annuaire-education` |
| IVAC (collèges) | `fr-en-indicateurs-valeur-ajoutee-colleges` |
| IVAL générale/technologique | `fr-en-indicateurs-de-resultat-des-lycees-gt_v2` |
| IVAL professionnelle | `fr-en-indicateurs-de-resultat-des-lycees-pro_v2` |
| IVAL GT — ancienne version (2012–2023) | `fr-en-indicateurs-de-resultat-des-lycees-denseignement-general-et-technologique` |
| IVAL PRO — ancienne version (2012–2023) | `fr-en-indicateurs-de-resultat-des-lycees-denseignement-professionnels` |

Les anciennes versions ne sont utiles que pour vérifier la continuité
méthodologique : le spike a établi qu'elles ne contiennent aucune valeur absente
des jeux `_v2` (cf. `05_Resultats_Spike_Technique.md`, section 2).

- Fiches de résultats officielles (lecture humaine) : `https://www.education.gouv.fr/les-indicateurs-de-resultats-des-colleges-et-des-lycees-377729`
