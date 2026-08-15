# Socle UX — Établissements en clair

**Statut :** référence de conception du MVP  
**Version :** 1.0 — 15 août 2026

Ce dossier transforme la vision produit en règles directement utilisables pour concevoir les wireframes, les maquettes et l’interface web.

## Ordre de lecture

1. `10_Specification_UX_MVP.md` — objectifs, périmètre et décisions structurantes
2. `11_Parcours_Utilisateurs.md` — parcours nominal et scénarios alternatifs
3. `12_Architecture_Information.md` — navigation, pages et hiérarchie du contenu
4. `13_Inventaire_Ecrans_Etats.md` — écrans, états et critères d’acceptation
5. `14_Charte_Neutralite_Editoriale.md` — vocabulaire, règles visuelles et garde-fous

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

## Dépendances levées par le spike technique (15 août 2026)

Les trois inconnues sont désormais mesurées — voir `05_Resultats_Spike_Technique.md` :

- **jointure par UAI** : fiable à 98,80 % (seuil visé 90 %) → **GO** ;
- **continuité méthodologique IVAL** : valeurs identiques entre ancienne et
  nouvelle version ; seule rupture réelle en **2021** (réforme du baccalauréat),
  et uniquement sur les sous-séries ;
- **couverture réelle** : 75 % des collèges et 65 % des lycées disposent
  d'indicateurs. L'état « aucun indicateur disponible » est donc un cas
  **courant**, à traiter comme tel dans les maquettes, et non un cas limite.

Point de vigilance éditorial ouvert : le motif affiché pour une valeur absente
ne peut pas être systématiquement le seuil d'effectif (cf.
`05_Resultats_Spike_Technique.md`, section 3). La formulation de référence de la
charte doit être revue par un humain avant d'être implémentée.
