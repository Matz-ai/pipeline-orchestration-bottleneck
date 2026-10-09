# Stratégie de tests et gestion d'erreurs

> **Étape OC 3.** Chaque tâche nominale du flow
> [`bottleneck_pipeline`](../flows/bottleneck_pipeline.yaml) est suivie de sa
> tâche de test `test_<id>`. Tous les tests sont dans un seul script,
> [`scripts/tests/checks.py`](../scripts/tests/checks.py), appelé par
> `python checks.py test_<id>`. Si un contrôle est KO, le script renvoie le
> code 1 : la tâche échoue et le flow s'arrête.

## 1. Tâche → test → contrôles

Chaque test combine des **invariants** (vrais tous les mois) et l'**oracle**
de Stéphane (`EXPECTED` dans `scripts/python/settings.py`, cf.
[architecture-flux.md §2](architecture-flux.md#deux-sortes-de-contrôles-dans-chaque-test)).

| Tâche | Test | Invariants | Oracle | Famille OC |
| --- | --- | --- | --- | --- |
| `ingest` | `test_ingest` | colonnes attendues présentes dans les 3 tables brutes | 825 / 825 / 1 513 lignes | nouvelles sources |
| `clean_erp` | `test_clean_erp` | `product_id` unique et jamais vide | 825 | 1 · doublons |
| `clean_liaison` | `test_clean_liaison` | `product_id` et `id_web` uniques | 825 | 1 · doublons |
| `clean_web` | `test_clean_web` | 0 `sku` manquant | 1 428 | 2 · valeurs manquantes |
| `dedup_web` | `test_dedup_web` | `sku` unique, 0 `total_sales` manquant | 714 | 1 · doublons |
| `merge` | `test_merge` | lignes = `web_dedup`, `product_id` et `sku` uniques, 0 prix manquant | 714 | 3 · jointures |
| `compute_ca` | `test_ca` | Σ CA par produit = CA total, aucun CA négatif, une ligne par produit | 70 568,60 € | 4 · CA |
| `zscore` | `test_zscore` | millésimes + ordinaires = fusion, z > 2 pour tous les millésimes, z ≤ 2 pour tous les ordinaires | 30 | 5 · z-score |
| `export_rapport_ca` | `test_export_rapport_ca` | relit le `.xlsx` : 2 onglets, lignes = base, CA total = base = Σ des lignes | 714 lignes, 70 568,60 € | 4 · CA |
| `export_millesimes` | `test_export_millesimes` | relit le `.csv` : lignes = vue, pas de doublon | 30 | 5 · z-score |
| `export_ordinaires` | `test_export_ordinaires` | relit le `.csv` : lignes = vue, pas de doublon | 684 (= 714 − 30) | 5 · z-score |

Les tests ouvrent la base **en lecture seule** : ils ne modifient rien.
`make check` rejoue les 8 premiers tests après la chaîne (même code).

## 2. Retry : sur les tâches, pas sur les tests

- **Tâches nominales** : `retry` constant, 3 tentatives au total, 1 min
  d'écart. Il couvre les pannes passagères, par exemple une base DuckDB
  verrouillée par un autre processus (point 6 du mail de Laurent). Relancer
  est sans risque : chaque script recrée ses tables (`CREATE OR REPLACE`).
- **Tests** : pas de retry. Un test KO signale une donnée fausse : le
  relancer donnerait le même résultat.

## 3. En cas d'échec

1. La tâche en échec (après ses retry) ou le test KO arrête le flow : les
   tâches suivantes ne tournent pas, l'exécution passe en **FAILED**.
2. Le handler `errors` (`alerte_echec`) écrit un log `ERROR` avec l'id de
   l'exécution et la tâche en cause.
3. L'humain corrige la cause, puis **Restart** l'exécution : Kestra reprend
   à la tâche en échec.

Limite connue : un test d'export relit le fichier déjà publié dans
`data/outputs/`. S'il est KO, le fichier reste là, mais l'exécution est
FAILED et l'alerte dit de ne pas le diffuser.

## 4. Démontrer une panne

Rien n'est ajouté au flow. On ouvre la base dans un terminal avec
`.\make.ps1 duckdb` et on lance le flow : DuckDB refuse l'écriture tant que
la session est ouverte (*Could not set lock on file*). On voit `ingest`
échouer 3 fois à 1 min d'écart, puis le handler. Résultat constaté :
FAILED en 2 min 05, 3 tentatives, alerte sur `ingest`.
