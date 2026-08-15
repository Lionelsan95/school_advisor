# Glossaire métier — sources et données

*Document stable, change rarement. À mettre à jour uniquement si une source officielle change de terminologie.*
*Dernière mise à jour : Août 2026*

---

## Organismes et sources

**DEPP** — Direction de l'évaluation, de la prospective et de la performance. Service statistique du ministère de l'Éducation nationale, producteur des IVAC/IVAL.

**RAMSESE** — Répertoire académique et ministériel sur les établissements du système éducatif. Base source de l'annuaire de l'éducation.

**Opendatasoft** — Moteur technique utilisé par data.education.gouv.fr, exposant une API REST standardisée (Explore API v2.1).

## Identifiants et indicateurs

**UAI** — Identifiant officiel d'un établissement scolaire (Unité Administrative Immatriculée). Clé technique probable pour la jointure entre l'annuaire et les indicateurs de résultats — à confirmer par le spike technique.

**IVAC** — Indicateurs de Valeur Ajoutée des Collèges. Disponibles pour les années 2022 à 2025. Mesurent l'écart entre les résultats obtenus par les élèves au diplôme national du brevet et les résultats statistiquement attendus compte tenu de leur profil scolaire et social à l'entrée.

**IVAL** — Indicateurs de Valeur Ajoutée des Lycées. Disponibles pour les années 2012 à 2025 (deux séries : générale/technologique et professionnelle). Même logique que les IVAC, appliquée au baccalauréat et au parcours au lycée.

**Valeur ajoutée** — Différence entre les résultats obtenus par un établissement et les résultats attendus statistiquement, compte tenu des caractéristiques scolaires et sociodémographiques des élèves accueillis. Une valeur positive signifie des résultats supérieurs à l'attendu ; négative, l'inverse. Ne mesure ni l'ambiance, ni la qualité de vie scolaire, ni des critères individuels à l'enfant.

**Taux de réussite** — Proportion d'élèves reçus à l'examen (brevet ou baccalauréat) parmi les élèves présentés.

**Taux d'accès** — Probabilité qu'un élève entré dans l'établissement (en 2nde pour un lycée, par exemple) atteigne et réussisse l'examen terminal.

**Taux de mention** — Proportion de lauréats ayant obtenu une mention à l'examen.

## Règles de diffusion des données (contrainte métier importante)

Les résultats en valeur ajoutée **ne sont pas diffusés** :
- en dessous de **20 candidats** en série générale/technologique
- en dessous de **10 candidats** en série professionnelle

Cette règle existe pour préserver la fiabilité statistique sur de petits effectifs. Elle doit être respectée et explicitée dans le produit (cf. fonctionnalité F6), jamais contournée ou estimée en interne.

## Typologie des établissements

**Statut** : public / privé sous contrat / privé hors contrat.

**Types de dispositifs et sections rencontrés dans les données** :
- **ULIS** — Unité Localisée pour l'Inclusion Scolaire
- **SEGPA** — Section d'Enseignement Général et Professionnel Adapté
- **EREA** — Établissement Régional d'Enseignement Adapté
- **REP / REP+** — Réseau d'Éducation Prioritaire (renforcé)
- Sections particulières : internationale, européenne, sport-études, arts, cinéma, théâtre

## Sources API techniques (référence rapide)

- Annuaire de l'éducation : `https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-annuaire-education/records`
- IVAL générale/technologique : dataset `fr-en-indicateurs-de-resultat-des-lycees-gt_v2`
- IVAL professionnelle : dataset `fr-en-indicateurs-de-resultat-des-lycees-pro_v2`
- Fiches de résultats officielles (lecture humaine) : `https://www.education.gouv.fr/les-indicateurs-de-resultats-des-colleges-et-des-lycees-377729`
