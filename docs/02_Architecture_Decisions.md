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
  ├── Orchestration LLM (interprétation bornée ; aucun contenu libre affiché)
  ├── Contenu éditorial versionné servi séparément à la sérialisation
  └── Job planifié d'ingestion (cron interne + alerte si échec/schéma inattendu)
        │
PostgreSQL + PostGIS (établissements, indicateurs annuels, append-only sur l'historique)
        │
Cache TTL/LRU borné d'interprétations validées (local au processus ; jamais de faits)
        ▲
        │ ingestion périodique, snapshot de rollback avant réimport
API Annuaire éducation + API IVAC/IVAL + Geo API communes
(sources externes, hors contrôle, jamais appelées pendant une requête utilisateur)
```

## Décisions actées

| Décision | Raison |
|---|---|
| **Backend monolithique unique**, pas de microservices/queue/Kubernetes | Complexité opérationnelle non justifiée par le volume et la taille d'équipe |
| **PostgreSQL + PostGIS**, pas de NoSQL ni Elasticsearch | Volume faible, besoin géospatial simple, stack largement maîtrisée |
| **Ingestion périodique découplée**, jamais d'appel direct aux API sources en temps réel par requête utilisateur | Protège l'utilisateur d'une panne/lenteur des API gouvernementales, hors de tout contrôle |
| **Table d'indicateurs append-only** (jamais d'écrasement des années précédentes) | Nécessaire pour l'historique pluriannuel (F5) |
| **Contenu explicatif F3/F6/F7 figé et versionné**, jamais généré librement par le LLM en production | Garantit la neutralité, l'auditabilité, la cohérence |
| **Cache TTL/LRU borné d'interprétations validées**, local au processus ; jamais de faits | Maîtrise du coût LLM sans servir de données officielles périmées |
| **Alerte obligatoire sur échec d'ingestion ou changement de schéma source** | Angle mort identifié comme le plus critique — API gouvernementales peuvent changer sans préavis fort |

## Alternatives explicitement écartées

- **Moteur de recherche à facettes sans LLM** : zéro risque de dérive de ton, mais ne répond pas au besoin central (langage naturel). Écarté.
- **Microservices dès la V1** : sur-ingénierie pour ce volume et cette équipe. Écarté, réévaluable seulement si un goulot d'étranglement réel apparaît (ex. l'ingestion devient lourde).
- **NoSQL / Elasticsearch** : pas de besoin de recherche plein texte complexe actuellement. PostgreSQL full-text à envisager avant tout changement de moteur.

### Limites opérationnelles du cache d'interprétation

Le cache est une structure en mémoire thread-safe par processus/worker, froide
après chaque redémarrage. Il n'ajoute ni Redis ni cohérence distribuée, non
justifiés à ce volume. Il n'est pas single-flight : deux misses simultanés
peuvent dupliquer un appel Anthropic, sans contourner la validation ni modifier
le contrat ou les garanties de neutralité.
L'invalidation est logique par version dans la clé, pas une suppression globale
synchrone ; les anciennes entrées disparaissent ensuite par TTL/LRU. Les faits
et leur provenance sont relus à chaque requête.

## Modèle de données actuel

Le schéma réel est défini par toutes les migrations sous
`back/alembic/versions/`. Les colonnes sont en anglais ; les noms français de
`08_API_Contract.md` appartiennent uniquement au format JSON.

```
establishment (PK uai)
├── identité administrative, type, secteur, état d'ouverture
├── filieres[], sections[]
└── date de mise à jour source

site (PK uai, sequence)
└── nom, adresse, commune, coordonnées, commune normalisée — 1..n sites par UAI

commune (PK code officiel)
└── nom normalisé, codes_postaux[], département, centre officiel nullable

indicator_result (PK uai, year, indicator_type)
└── valeurs brutes nullable, append-only, sans motif d'absence inventé

source_reference (PK dataset_id)
└── URL, publication et dernière synchronisation

ingestion_run
└── audit de chaque tentative, dont communes_loaded
```

Il n'existe volontairement ni champ `sous_seuil_diffusion`, ni effectif
d'identité, ni clé étrangère entre `indicator_result` et `establishment`. Les
établissements multi-sites sont préservés, les absences restent sans cause ligne à ligne,
et les indicateurs officiels non rattachés à l'annuaire ne sont pas rejetés.
Les noms d'établissements et communes sont normalisés par colonnes générées et
indexés avec `pg_trgm`/`unaccent` dans PostgreSQL ; aucun moteur de recherche
supplémentaire n'est nécessaire.

## Contrainte spécifique : traçabilité des réponses

Conséquence architecturale directe du principe de neutralité : toute donnée ou texte affiché à l'utilisateur doit être traçable à son origine (donnée officielle brute / calcul déterministe documenté / contenu éditorial figé versionné). Aucune sortie ne doit reposer uniquement sur "ce que le LLM a décidé de dire" sans traçabilité. À prévoir dans le schéma de logging dès la V1.

### Les trois origines dans l'API actuelle

Chaque nombre et chaque texte d'une réponse relève de l'une des trois. La
provenance officielle et les calculs sont visibles dans la réponse ; la version
du contenu assistant reste traçable dans le dépôt mais n'est pas un champ du
contrat HTTP :

| Origine | Où elle vit | Comment le lecteur la reconnaît |
|---|---|---|
| Donnée officielle brute | tables `establishment`, `site`, `commune`, `indicator_result` | objet `source` au niveau pertinent ; les objets de figure indicateur portent aussi `calcule: false`, les autres champs officiels reposent sur cette provenance englobante |
| Calcul déterministe documenté | `application/` (ex. `expected_rate()`) | l'objet de figure porte `calcule: true` + une `note_de_calcul` qui énonce la formule |
| Contenu éditorial figé versionné | `back/src/domain/explanatory_content.py` et `assistant_content.py` | les blocs explicatifs F3/F6 exposent `content_id` + `version`; le rappel F7 et les chaînes assistant sont centralisés/versionnés dans le dépôt, avec `ASSISTANT_CONTENT_VERSION` non exposé sur le fil |

### Procédure de mise à jour du contenu éditorial (ticket API-3)

Le contenu F3/F6/F7 et le contenu assistant sont des **modules Python
versionnés**, pas une table ni un
fichier de configuration. Raison : il change au rythme d'une décision
éditoriale (rarement), il doit être relu par un humain avant d'exister, et le
mettre en base permettrait de le modifier en production sans revue ni trace —
exactement ce que la charte interdit. Dans le dépôt, il hérite gratuitement de
la revue de code, de l'historique git et du blâme ligne à ligne.

Pour le modifier :

1. Rédiger la modification dans `explanatory_content.py` et **incrémenter le
   `version` de l'entrée touchée**, ou dans `assistant_content.py` et
   incrémenter `ASSISTANT_CONTENT_VERSION`.
2. **Revue humaine explicite et obligatoire.** Aucun agent ne franchit cette
   étape seul ; `commit-writer` doit refuser de s'exécuter si elle n'a pas eu
   lieu (voir `CLAUDE.md`, « Explanatory content change »).
3. `neutrality-checker`, puis les tests de cohérence de contenu (un même
   `content_id` rend toujours exactement le même texte).
4. Répercuter dans `14_Charte_Neutralite_Editoriale.md` si le texte de
   référence de la charte est concerné.

Le `version` n'est pas décoratif : il permet à un test ou à un cache de
détecter qu'un texte a bougé sans qu'on le lui ait dit.

## Risques / angles morts identifiés (à surveiller activement)

1. L'ingestion détecte les champs manquants, volumes suspects et chutes du taux
   de rattachement ; Phase 6 doit encore relier ces erreurs à un canal d'alerte
   réel plutôt qu'au seul journal CRITICAL.
2. La recherche en langage naturel est bornée par un tool au schéma fermé et
   une validation sémantique indépendante. Le workflow CI est configuré ; le
   premier run GitHub hébergé réussi reste à observer avant de considérer la
   preuve opérationnelle acquise.
3. Le référentiel de communes et la recherche déterministe sont locaux ; leur
   risque restant est la dérive du schéma Geo API, couverte par validation
   obligatoire et seuil de volume avant publication.
4. La pression à sur-ingénierer reste à surveiller : aucun service, queue ou
   moteur supplémentaire n'est justifié par les volumes mesurés.

## Prochaine étape technique

Le prérequis déterministe et la frontière d'interprétation de Phase 3 sont
implémentés : UAI, nom, commune et code postal sont recherchables ; les centres
officiels sont locaux ; un port indépendant du fournisseur utilise Anthropic
comme premier adaptateur et n'accepte qu'un critère explicitement soutenu par
la demande. Le cache borné d'interprétations validées est également
implémenté. Le workflow backend CI est configuré ; la seule preuve Phase 3
restante est l'observation de son premier run GitHub hébergé réussi, incluant
la suite adversariale sans skip inattendu.
