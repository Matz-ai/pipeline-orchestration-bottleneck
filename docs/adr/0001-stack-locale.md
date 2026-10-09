# ADR 0001 — Stack locale : Kestra, DuckDB, Python

- **Statut** : accepté
- **Date** : 2026-10-08

## Contexte

Le brief OC impose Kestra sur Docker, DuckDB et Python. Il laisse ouverts la
façon d'installer Kestra, celle d'exécuter Python et l'emplacement des
scripts. Le pipeline traite **3 petits fichiers Excel (~370 Ko)** une fois
par mois : la volumétrie ne justifie aucune infrastructure distribuée.

Le contexte de soutenance pèse aussi : l'évaluateur (« Laurent ») challenge
*l'implémentation de l'ordonnancement et les fonctionnalités principales de
Kestra*. Chaque choix ci-dessous doit donc pouvoir s'expliquer en une phrase.

## Décisions

### 1. Kestra `server standalone` + H2 (une image), pas le compose complet

| | Standalone + H2 | Compose officiel (Postgres) |
| - | - | - |
| Conteneurs | 1 | 2 |
| RAM | ~1,5-2 Go | ~2,5-3 Go |
| Démarrage | ~20 s (après build) | ~1-2 min |
| Persistance | volumes `kestra_db` + `kestra_storage` | volume Postgres |
| Usage visé | dev, démo, mono-utilisateur | production, plusieurs workers |

On reste sur une instance mono-utilisateur sur un poste Windows, avec un run
par mois. Postgres n'apporterait rien de visible en démo et alourdirait la
machine. **En soutenance** : c'est la première piste d'industrialisation à
citer (passer au compose Postgres, puis à Kubernetes, sans changer le flow).

**Pourquoi `standalone` et pas `server local`** (la commande « une ligne »
de la doc Kestra) : `server local` configure exactement la même chose (H2 +
stockage local), mais **force un port de management aléatoire**, codé en dur
dans `LocalCommand.java` et non surchargeable. Le healthcheck Docker ne
peut alors jamais trouver `/health`. Avec `server standalone`, la
configuration H2 est écrite **explicitement** dans `docker-compose.yml`
(base, file d'attente, stockage, port 8081), ce qui rend en plus le
fonctionnement lisible pour un relecteur.

**Version figée : `v2.0.5`** (= `latest-lts` au 08/10/2026), plutôt que
`latest`. Une mise à jour silencieuse de Kestra entre deux exécutions
mensuelles pourrait casser le flow sans qu'aucun fichier du repo n'ait changé.

### 2. Python exécuté dans le conteneur Kestra (`Process`), pas via le socket Docker

Par défaut, Kestra lance chaque tâche Python dans **un conteneur Docker
éphémère**. Il lui faut alors le socket Docker de l'hôte
(`/var/run/docker.sock`), ce qui donne au conteneur Kestra un contrôle
**root sur tout Docker**. C'est acceptable pour une démo, mais c'est un vrai
risque de sécurité, et cela fait aussi télécharger une image et lancer
`pip install pandas` à **chaque** exécution.

On construit à la place une **image custom** (`docker/kestra/Dockerfile`) :
image officielle + Python 3.11 + `pandas`, `openpyxl`, `duckdb` figés dans
`requirements.txt`. Les tâches utilisent `taskRunner: Process`, c'est-à-dire
qu'elles tournent directement dans ce conteneur.

- Pas de socket Docker monté, et Kestra tourne avec son utilisateur non-root.
- Run rapide, sans dépendance réseau le 15 du mois à 9 h (pas de PyPI).
- Versions des librairies identiques d'un run à l'autre.
- Ajouter une librairie demande de reconstruire l'image (`make up` le fait).
- Moins d'isolation entre tâches, ce qui ne pose pas de problème avec un
  seul flow.

### 3. DuckDB en fichier local, pas de serveur SQL

DuckDB est une base **embarquée** : un fichier (`data/warehouse.duckdb`) et
une librairie Python, comme SQLite mais orientée analytique. Il n'y a ni
serveur à administrer ni mot de passe, et le fichier s'ouvre aussi depuis
l'hôte pour inspecter les tables intermédiaires.

Conséquence pour le point 6 du mail de Laurent (« indisponibilité d'un
service tiers comme DuckDB ») : la panne réaliste n'est pas un serveur
injoignable, mais un **fichier verrouillé** (ouvert par un autre process) ou
un fichier **corrompu ou absent**. Le `retry` + handler `errors` ciblent
ces cas.

### 4. Scripts SQL/Python hors du YAML

Les scripts vivent dans `scripts/` et non inline dans le YAML Kestra :

- le YAML reste lisible et décrit **l'ordonnancement** (rôle de Kestra :
  *« un outil d'orchestration et non pas un outil de traitement »*, point de
  vigilance OC) ;
- les scripts sont **exécutables sans Kestra**, ce qui permet de reproduire
  les chiffres de Stéphane avant d'écrire le flow ;
- leurs diffs Git restent lisibles.

`./scripts` est monté en lecture seule dans le conteneur
(`/bottleneck/scripts`). Le mode d'injection dans le flow est tranché dans
l'[ADR 0002](0002-scripts-et-sorties-du-flow.md).

### 5. Chemins dans le conteneur : `/bottleneck/...`, pas `/app/data`

La base H2 de Kestra vit dans `/app/data` (volume `kestra_db`), son stockage
interne dans `/app/storage` (volume `kestra_storage`). Ces deux dossiers sont
créés dans l'image avec l'utilisateur `kestra` pour propriétaire : un volume
nommé vide hérite des droits du dossier de l'image. Sans ça, il appartiendrait
à root et Kestra, qui tourne en non-root, planterait au démarrage
(`AccessDeniedException: /app/data/database.mv.db`, vécu au 1ᵉʳ `up`). Monter
`./data` à cet endroit écraserait la base interne de Kestra. Les fichiers du
projet sont donc montés sous `/bottleneck/{data,scripts,flows}` et exposés
aux flows par des variables `ENV_*` (lisibles via `{{ envs.duckdb_path }}`).

### 6. Python 3.11

Python 3.11 est la version retenue pour le projet, et pandas, openpyxl et duckdb la supportent pleinement.
Elle est installée dans l'image par `uv`, ce qui ne dépend pas du Python
fourni par l'OS de l'image Kestra. Sur l'hôte, seul
`scripts/download_data.py` tourne, et il n'utilise que la bibliothèque
standard (n'importe quel Python ≥ 3.9).

### 7. `make.ps1` en plus du `Makefile`

Windows n'a pas `make` par défaut. Plutôt que de faire installer un outil
supplémentaire, `make.ps1` expose les mêmes cibles en PowerShell
(`.\make.ps1 up`). Le `Makefile` reste la référence documentée.

## Conséquences

- Un `make up` suffit : il construit l'image (~2-3 min la première fois) et
  démarre Kestra.
- L'authentification de l'UI est obligatoire depuis Kestra 1.0 : le compte
  est défini dans `.env`, qui n'est jamais commité.
- L'industrialisation (Postgres, workers séparés, secrets managés) reste une
  piste d'amélioration documentée, pas un prérequis.
