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

*(à compléter au fil de l'avancement)*
