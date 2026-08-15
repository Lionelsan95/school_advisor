# Architecture & Décisions techniques — résumé de référence

*Document condensé, issu de la revue d'architecture par comité. À remplacer en cas d'évolution majeure.*
*Dernière mise à jour : Août 2026*

---

## Verdict de fond du comité d'architecture

> Le principal risque de ce projet n'est pas que l'architecture soit trop simple. C'est qu'elle soit trop compliquée pour la taille réelle du problème.

Contraintes réelles à garder en tête pour toute décision future :
- Volumétrie faible (~66 000 établissements, quelques dizaines de milliers de lignes d'indicateurs/an) — pas un problème de big data
- Fraîcheur des sources faible (annuel pour IVAC/IVAL, hebdomadaire pour l'annuaire) — pas de besoin de temps réel
- Criticité faible-modérée — une indisponibilité de 30 min n'a pas de conséquence grave
- Équipe : solopreneur / petite structure — pas une architecture "grande DSI"

## Architecture retenue (schéma de référence)

```
Client web (responsive, pas d'app native en V1)
        │ HTTPS
Backend monolithique unique
  ├── API applicative (recherche, fiches, F1-F10)
  ├── Orchestration LLM (tool use borné, contenu figé injecté pour F3/F6/F7)
  └── Job planifié d'ingestion (cron interne + alerte si échec/schéma inattendu)
        │
PostgreSQL + PostGIS (établissements, indicateurs annuels, append-only sur l'historique)
        │
Cache de réponses (requêtes fréquentes, réduit le coût LLM)
        ▲
        │ ingestion périodique, snapshot de rollback avant réimport
API Annuaire éducation + API IVAC/IVAL (sources externes, hors contrôle)
```

## Décisions actées

| Décision | Raison |
|---|---|
| **Backend monolithique unique**, pas de microservices/queue/Kubernetes | Complexité opérationnelle non justifiée par le volume et la taille d'équipe |
| **PostgreSQL + PostGIS**, pas de NoSQL ni Elasticsearch | Volume faible, besoin géospatial simple, stack largement maîtrisée |
| **Ingestion périodique découplée**, jamais d'appel direct aux API sources en temps réel par requête utilisateur | Protège l'utilisateur d'une panne/lenteur des API gouvernementales, hors de tout contrôle |
| **Table d'indicateurs append-only** (jamais d'écrasement des années précédentes) | Nécessaire pour l'historique pluriannuel (F5) |
| **Contenu explicatif F3/F6/F7 figé et versionné**, jamais généré librement par le LLM en production | Garantit la neutralité, l'auditabilité, la cohérence |
| **Cache de réponses** (pas seulement de données) | Maîtrise du coût LLM à l'échelle |
| **Alerte obligatoire sur échec d'ingestion ou changement de schéma source** | Angle mort identifié comme le plus critique — API gouvernementales peuvent changer sans préavis fort |

## Alternatives explicitement écartées

- **Moteur de recherche à facettes sans LLM** : zéro risque de dérive de ton, mais ne répond pas au besoin central (langage naturel). Écarté.
- **Microservices dès la V1** : sur-ingénierie pour ce volume et cette équipe. Écarté, réévaluable seulement si un goulot d'étranglement réel apparaît (ex. l'ingestion devient lourde).
- **NoSQL / Elasticsearch** : pas de besoin de recherche plein texte complexe actuellement. PostgreSQL full-text à envisager avant tout changement de moteur.

## Modèle de données (esquisse)

```
Etablissement
├── uai (id officiel)
├── nom, type, statut_public_prive
├── adresse, code_postal, commune, latitude, longitude
├── filieres[], sections[]
├── effectif, annee_effectif
└── date_maj_source

IndicateurResultat
├── uai (FK Etablissement)
├── annee
├── type_indicateur (IVAC | IVAL_GT | IVAL_PRO)
├── taux_reussite, taux_acces, taux_mention
├── valeur_ajoutee (nullable si sous seuil)
├── sous_seuil_diffusion (bool)
└── date_publication_source

SourceReference
├── id, url_source
├── date_derniere_synchronisation
└── dataset_origine
```

## Contrainte spécifique : traçabilité des réponses

Conséquence architecturale directe du principe de neutralité : toute donnée ou texte affiché à l'utilisateur doit être traçable à son origine (donnée officielle brute / calcul déterministe documenté / contenu éditorial figé versionné). Aucune sortie ne doit reposer uniquement sur "ce que le LLM a décidé de dire" sans traçabilité. À prévoir dans le schéma de logging dès la V1.

## Risques / angles morts identifiés (à surveiller activement)

1. **Le plus critique** : absence de stratégie de détection de panne silencieuse sur l'ingestion (changement de schéma API source) — doit être couvert avant la V1.
2. Jointure Annuaire ↔ IVAC/IVAL (clé UAI) non encore vérifiée — traité comme spike go/no-go, pas un simple ticket.
3. Continuité méthodologique des IVAL (ancienne vs nouvelle version du dataset) à vérifier avant d'afficher une série continue sur 13 ans.
4. Reformulations libres du LLM (hors contenu figé) — surface à risque de dérive de neutralité, nécessite tests de non-régression automatisés, pas seulement des audits manuels.
5. Pression potentielle à "sur-ingénierer" pour paraître scalable — à résister consciemment en V1/V2, tant qu'aucun besoin réel observé ne le justifie.

## Prochaine étape technique

Spike de 3 à 5 jours avant tout développement produit :
1. Test réel de la jointure UAI, mesure du taux de correspondance fiable (seuil de qualité à définir, ex. 90%)
2. Vérification de la continuité méthodologique IVAL ancien/nouveau format
3. Prototype minimal du pipeline d'ingestion (un seul job, PostgreSQL local)

→ Doit produire un rapport de décision go/no-go avant d'engager la suite.
