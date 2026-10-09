# Workflow Kestra — documentation tâche par tâche

> **Étape OC 2 (tâches nominales).** Ce document décrit le flow
> [`flows/bottleneck_pipeline.yaml`](../flows/bottleneck_pipeline.yaml) :
> ce que fait chaque tâche, ce qu'elle lit et écrit, le type de tâche Kestra
> choisi et **pourquoi**. La spécification de l'enchaînement (tests compris)
> est dans [architecture-flux.md](architecture-flux.md) ; les choix
> structurants dans l'[ADR 0002](adr/0002-scripts-et-sorties-du-flow.md).
>
> Tests, retry et gestion d'erreurs : [strategie-tests.md](strategie-tests.md).

## 1. Le flow en un coup d'œil

| Clé | Valeur | Pourquoi |
| --- | --- | --- |
| `id` | `bottleneck_pipeline` | Identifiant stable : il apparaît dans l'URL de l'UI et dans l'API. |
| `namespace` | `bottleneck` | Le « dossier » du projet dans Kestra (flows, fichiers, droits). |
| `labels` | `projet`, `etape-oc` | Filtrer les exécutions dans l'UI. |
| Tâches | 11 tâches nominales + 11 tests, 1 `Parallel`, 2 `Sequential` | Une tâche Kestra = une étape du diagramme (Livrable 1), avec le même `id`. |
| Durée d'un run | ≈ 11 s | Mesuré au test de fumée (2026-10-09). |

```text
ingest → clean_erp → clean_liaison → clean_web → dedup_web → merge
       → compute_ca → zscore → export_rapport_ca
       → exports_vins (Parallel) ┬─ export_millesimes → test
                                 └─ export_ordinaires → test
(chaque tâche est suivie de son test_<id>)
```

## 2. Les fonctionnalités Kestra utilisées

| Fonctionnalité | Où dans le flow | Ce qu'elle apporte |
| --- | --- | --- |
| **Flow déclaratif en YAML** | tout le fichier | L'ordonnancement se lit comme une liste : l'ordre des tâches **est** l'ordre d'exécution. Le YAML se versionne et se relit dans Git. |
| **Namespace** | `namespace: bottleneck` | Regroupe ce qui appartient au projet. |
| **Tâches de script** `python.Commands` / `shell.Commands` | T0, T7, T8, T9 / T1 → T6 | Kestra lance une commande et suit son code retour : 0 = succès, autre chose = échec et arrêt du flow. La logique reste dans les scripts. |
| **Task runner `Process`** | `taskRunner` sur chaque tâche | La commande tourne **dans le conteneur Kestra** (Python et DuckDB déjà installés), pas dans un conteneur Docker éphémère (ADR 0001 §2). |
| **Expressions Pebble** `{{ envs.… }}` | chemins des scripts, de la base, des sorties | Aucun chemin en dur : tout vient des variables `ENV_*` du conteneur, elles-mêmes issues de `.env`. |
| **Tâche de flux `Parallel`** | `exports_vins` | Le **branching** recommandé par OC : les 2 extractions démarrent en même temps. Si l'une échoue, l'autre est interrompue (`onChildFailure: FAIL` par défaut). |
| **`outputFiles`** | T8, T9a, T9b | Kestra archive le fichier produit **avec l'exécution** : téléchargeable dans l'onglet *Outputs*, un exemplaire par run mensuel. |
| **Tâche de flux `Sequential`** | `branche_millesimes`, `branche_ordinaires` | Dans chaque branche du `Parallel`, l'export puis son test, dans cet ordre. |
| **`retry`** | les 11 tâches nominales | 3 tentatives à 1 min d'écart : une panne passagère (base verrouillée) ne fait pas échouer le run. |
| **`errors`** | niveau flow | Exécuté seulement si le flow échoue : log `ERROR` avec la tâche en cause. |
| **Trigger `Schedule`** | `schedule_mensuel` | Lance le flow le 15 du mois à 9 h, heure de Paris (`0 9 15 * *`). |
| **Topologie, Gantt, Logs** | UI, après exécution | La topologie montre le graphe des tâches ; le Gantt montre la durée de chacune et le parallélisme ; les logs reprennent ce qu'affichent les scripts (« 825 lignes », « 30 millésimes »…). |

## 3. Tâche par tâche

Toutes les tables vivent dans `data/warehouse.duckdb`
(`{{ envs.duckdb_path }}`). Les scripts sont lus sur le montage
`/bottleneck/scripts` (`{{ envs.scripts_dir }}`).

| # | `id` | Rôle | Entrée → sortie | Type Kestra | Pourquoi ce type |
| --- | --- | --- | --- | --- | --- |
| T0 | `ingest` | Charger les 3 exports bruts, sans filtre | `erp.xlsx`, `liaison.xlsx`, `web.xlsx` → `raw_erp`, `raw_liaison`, `raw_web` | `scripts.python.Commands` → [`ingest.py`](../scripts/python/ingest.py) | Lire de l'Excel demande pandas/openpyxl. On évite l'extension DuckDB `excel` : elle se télécharge au 1ᵉʳ run, et le run de 9 h ne doit pas dépendre du réseau. |
| T1 | `clean_erp` | Dédoublonner l'ERP | `raw_erp` → `erp_dedup` | `scripts.shell.Commands` → `duckdb -bail -f` [`01_clean_erp.sql`](../scripts/sql/01_clean_erp.sql) | Transformation ensembliste : c'est du SQL. Le CLI DuckDB exécute le fichier tel quel ; `-bail` fait échouer la tâche à la 1ʳᵉ erreur (ADR 0002 §2). |
| T2 | `clean_liaison` | Dédoublonner la table de liaison | `raw_liaison` → `liaison_dedup` | `shell.Commands` → [`02_clean_liaison.sql`](../scripts/sql/02_clean_liaison.sql) | Idem T1. |
| T3 | `clean_web` | Supprimer les lignes sans `sku` | `raw_web` → `web_nettoye` | `shell.Commands` → [`03_clean_web.sql`](../scripts/sql/03_clean_web.sql) | Idem T1. C'est le script « suppression des valeurs manquantes » du livrable OC. |
| T4 | `dedup_web` | Dédoublonner le web | `web_nettoye` → `web_dedup` | `shell.Commands` → [`04_dedup_web.sql`](../scripts/sql/04_dedup_web.sql) | Idem T1. Séparé de T3 pour qu'un test vérifie chaque étape (Conv E). |
| T5 | `merge` | Réconcilier ERP et web **via la liaison** | 3 tables `*_dedup` → `fusion` | `shell.Commands` → [`05_merge.sql`](../scripts/sql/05_merge.sql) | Jointures : SQL. |
| T6 | `compute_ca` | CA par produit et CA total | `fusion` → `ca_par_produit`, `ca_total` | `shell.Commands` → [`06_ca.sql`](../scripts/sql/06_ca.sql) | Agrégation en `DECIMAL` (au centime, sans erreur d'arrondi). |
| T7 | `zscore` | Classer chaque vin millésime / ordinaire | `fusion` → `vins_zscore` + vues `vins_millesimes`, `vins_ordinaires` | `scripts.python.Commands` → [`zscore.py`](../scripts/python/zscore.py) | Calcul statistique imposé en Python par le brief. Seuil lu dans `ENV_ZSCORE_THRESHOLD` (2). |
| T8 | `export_rapport_ca` | Produire le rapport Excel (Livrable 3) | `ca_par_produit`, `ca_total` → `…_3_rapport_ca_<mmaaaa>.xlsx` | `python.Commands` + `outputFiles` → [`export_rapport_ca.py`](../scripts/python/export_rapport_ca.py) | 2 onglets (CA par produit, CA total) mis en forme pour le métier : openpyxl. Lecture seule de la base. |
| T9 | `exports_vins` | Branching des 2 extractions | — | `core.flow.Parallel` | Les 2 extractions ne dépendent pas l'une de l'autre et ne font que lire : elles peuvent tourner en même temps. |
| T9a | `export_millesimes` | Liste des vins premium pour Laure (Livrable 4) | `vins_millesimes` → `…_4_vins_millesimes_<mmaaaa>.csv` | `python.Commands` + `outputFiles` → [`export_vins.py millesimes`](../scripts/python/export_vins.py) | Un seul script paramétré pour les 2 listes : même format, pas de code dupliqué. |
| T9b | `export_ordinaires` | Liste des vins ordinaires pour Maria (Livrable 5) | `vins_ordinaires` → `…_5_vins_ordinaires_<mmaaaa>.csv` | `python.Commands` + `outputFiles` → [`export_vins.py ordinaires`](../scripts/python/export_vins.py) | Idem T9a. |

### Formats des sorties

| Fichier | Contenu | Format |
| --- | --- | --- |
| `ZINZEN_Mathieu_3_rapport_ca_072026.xlsx` | onglet **CA par produit** (714 lignes, tri par CA décroissant) + onglet **CA total** (70 568,60 €, 714 produits, 385 vendus) | montants au format `€`, en-tête figé |
| `ZINZEN_Mathieu_4_vins_millesimes_072026.csv` | 30 vins, z-score décroissant | `;`, virgule décimale, UTF-8 avec BOM |
| `ZINZEN_Mathieu_5_vins_ordinaires_072026.csv` | 684 vins, z-score décroissant | idem |

Les CSV suivent les conventions d'Excel en français : Laure et Maria les
ouvrent d'un double-clic, accents et décimales compris. Colonnes :
`product_id`, `sku`, `nom_produit`, `prix`, `quantite_vendue`, `z_score`.

Les noms suivent la convention OC `Nom_Prenom_<n°>_<nom>_<mmaaaa>` ; nom,
prénom et date viennent de `ENV_LIVRABLE_*` (`.env`). S'ils sont vides,
l'export échoue avec un message explicite.

## 4. Choix d'implémentation (résumé)

- **Scripts lus sur le montage `/bottleneck/scripts`**, pas en namespace
  files : un seul exemplaire des scripts (Git), utilisé à l'identique par
  `make check` et par Kestra. → [ADR 0002 §1](adr/0002-scripts-et-sorties-du-flow.md#1-les-tâches-lisent-les-scripts-sur-le-montage-bottleneckscripts)
- **SQL par le CLI DuckDB**, pas par le plugin JDBC : un seul moteur DuckDB
  (1.3.2) écrit la base. → [ADR 0002 §2](adr/0002-scripts-et-sorties-du-flow.md#2-sql-exécuté-par-le-cli-duckdb-pas-par-le-plugin-jdbc)
- **Sorties en `outputFiles` + publication dans `data/outputs/`** :
  historique par exécution dans Kestra. → [ADR 0002 §3](adr/0002-scripts-et-sorties-du-flow.md#3-sorties--outputfiles-kestra--publication-dans-dataoutputs)
- **T0 → T8 séquentielles, T9a ∥ T9b** : DuckDB n'accepte qu'un processus
  en écriture par fichier ; les exports ouvrent la base en `read_only`.
  → [architecture-flux.md §3](architecture-flux.md#3-dépendances-et-ordre-dexécution)
- **`cp` dans le YAML** : il publie un fichier déjà produit (rôle
  d'orchestration), il ne calcule rien.

## 5. Le `cp` et le dossier de travail

Avec `taskRunner: Process`, Kestra crée pour chaque tâche un **dossier de
travail temporaire**, vide. Le script d'export y écrit son fichier (`.`).
À la fin de la tâche, Kestra récupère tout ce qui correspond à `outputFiles`
(`*.xlsx` ou `*.csv`) puis supprime le dossier. Le `cp` copie entre-temps le
fichier vers `data/outputs/`, visible sur l'hôte. Le glob `*.csv` ne peut
pas attraper un autre fichier : le dossier ne contient que ce que la tâche
vient d'écrire.

## 6. Tests, erreurs et planification

- `test_<id>` juste après chaque tâche : `python.Commands` qui lance
  `scripts/tests/checks.py test_<id>`. Code retour 1 si un contrôle est KO.
- `retry` (`constant`, `PT1M`, `maxAttempts: 3`) sur les tâches nominales,
  pas sur les tests.
- Handler `errors` : tâche `io.kestra.plugin.core.log.Log`, niveau `ERROR`.
  La tâche en cause vient de `errorLogs()[0]['taskId']`.
- Trigger `io.kestra.plugin.core.trigger.Schedule`, cron `0 9 15 * *`,
  timezone `Europe/Paris`.

Détail et justification : [strategie-tests.md](strategie-tests.md).

## 7. Exécuter et vérifier

- Rejouer la chaîne et les tests hors Kestra : `make check`.
