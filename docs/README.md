# Socle UX — Établissements en clair

**Statut :** référence de conception du MVP  
**Version :** 1.0 — 15 août 2026

Ce dossier transforme la vision produit en règles directement utilisables pour concevoir les wireframes, les maquettes et l’interface web.

## Ordre de lecture

1. `01_Specification_UX_MVP.md` — objectifs, périmètre et décisions structurantes
2. `02_Parcours_Utilisateurs.md` — parcours nominal et scénarios alternatifs
3. `03_Architecture_Information.md` — navigation, pages et hiérarchie du contenu
4. `04_Inventaire_Ecrans_Etats.md` — écrans, états et critères d’acceptation
5. `05_Charte_Neutralite_Editoriale.md` — vocabulaire, règles visuelles et garde-fous

## Autorité documentaire

En cas de contradiction :

1. le principe « l’outil explique, il ne juge pas » prévaut ;
2. la vision produit et les règles métier officielles prévalent ;
3. ce socle UX prévaut sur une maquette visuelle ;
4. une maquette validée prévaut sur une interprétation libre lors du développement.

## Décisions déjà prises

- Produit web responsive, sans application native en V1.
- Accès sans compte et sans personnalisation liée à un enfant.
- Collèges et lycées, couverture nationale selon les données réellement intégrées.
- Recherche hybride : déterministe par défaut, LLM uniquement pour convertir une phrase complexe en critères.
- Deux établissements au maximum en comparaison.
- Aucun classement, score, verdict, recommandation ou tri par résultat.
- Aucune couleur de performance rouge/verte.
- Contenu explicatif éditorial, figé et versionné.
- Conception mobile prioritaire, avec conformité WCAG 2.2 niveau AA visée.
- Nom de travail : **Établissements en clair**. Il ne constitue pas encore un choix de marque définitif.

## Dépendances non bloquantes

Le spike technique doit encore confirmer :

- la fiabilité de la jointure par UAI ;
- la continuité méthodologique des historiques IVAL ;
- la couverture réelle obtenue après ingestion.

Ces inconnues influencent les données affichables, pas l’architecture générale de l’expérience.
