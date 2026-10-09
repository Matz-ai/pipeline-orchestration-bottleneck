# ADR 0002 — Accès aux scripts, tâches SQL et publication des sorties du flow

- **Statut** : accepté
- **Date** : 2026-10-09
- **Complète** : [ADR 0001](0001-stack-locale.md) §4 (laissait ouvert le mode
  d'injection des scripts)

## Contexte

Le flow `flows/bottleneck_pipeline.yaml` appelle des scripts versionnés dans
`scripts/` (Kestra orchestre, les scripts traitent). Il reste trois choix à
faire, avec le flow sous les yeux :

1. comment les tâches accèdent aux scripts ;
2. comment exécuter les scripts SQL DuckDB ;
3. comment les 3 fichiers produits (rapport `.xlsx`, 2 `.csv`) sortent du
   conteneur.

## Décisions

### 1. Les tâches lisent les scripts sur le montage `/bottleneck/scripts`

`./scripts` est déjà monté en lecture seule dans le conteneur (ADR 0001 §5).
Les tâches appellent directement `python {{ envs.scripts_dir }}/python/…` ou
`duckdb … -f {{ envs.scripts_dir }}/sql/…`.

| | Montage direct | Namespace files Kestra |
| - | - | - |
| Source de vérité | le repo Git, un seul exemplaire | une **copie** dans le stockage Kestra |
| Mise à jour d'un script | immédiate (modifier le fichier suffit) | il faut ré-uploader (UI, API ou flow de synchro) |
| Risque | flow lié à ce poste (le montage doit exister) | Git et Kestra qui divergent sans que personne ne le voie |
| `make check` et Kestra | exécutent **les mêmes fichiers**, octet pour octet | deux exemplaires à garder alignés |

On garde donc un seul exemplaire des scripts. Le montage direct est plus simple que
`namespaceFiles` et supprime un risque de dérive.

**Piste d'industrialisation** (à citer en soutenance) : sur un Kestra
distant ou à plusieurs workers, le montage n'existe plus. On passerait alors
aux namespace files, synchronisés depuis Git par un flow
(`io.kestra.plugin.git.SyncNamespaceFiles`), et les tâches liraient les
scripts avec `namespaceFiles: enabled: true`. Le contenu des scripts ne
change pas.

### 2. SQL exécuté par le CLI DuckDB, pas par le plugin JDBC

Les tâches T1 → T6 sont des `shell.Commands` qui lancent
`duckdb <base> -bail -f <script.sql>`. Le CLI DuckDB 1.3.2 est déjà dans
l'image ; `-bail` arrête au premier ordre en erreur et renvoie le
code 1, ce qui met la tâche Kestra en échec.

Pourquoi pas le plugin Kestra `io.kestra.plugin.jdbc.duckdb.Queries`
(présent dans l'image, en version 2.1.0) :

- il embarque **son propre moteur DuckDB** (pilote JDBC), dont la version ne
  dépend pas de `requirements.txt`. Deux moteurs de versions différentes
  écriraient alors dans le même fichier `warehouse.duckdb` : c'est un risque
  sur le format de stockage ;
- sa propriété `sql` attend le texte de la requête, pas un chemin. Pour
  rester hors du YAML, il faudrait passer par les namespace files (cf. §1).

Avec le CLI, un seul moteur (1.3.2) écrit la base : le même que celui de
pandas/duckdb en Python et de `make duckdb`.

### 3. Sorties : `outputFiles` Kestra + publication dans `data/outputs/`

Chaque tâche d'export :

1. écrit son fichier dans **son dossier de travail** (`.`), isolé par Kestra ;
2. le **publie** dans `data/outputs/` (`ENV_DATA_OUTPUT_DIR`, monté sur
   l'hôte) par un `cp` ;
3. le déclare en `outputFiles` : Kestra en garde une copie dans son stockage
   interne, **rattachée à l'exécution**. Le fichier est téléchargeable dans
   l'onglet *Outputs*, et chaque exécution mensuelle garde le sien
   (historique).

On sépare ainsi :

| Dossier | Contenu | Qui écrit |
| - | - | - |
| `data/outputs/` | sortie **opérationnelle**, réécrite à chaque run (le 15 du mois) | le flow |
| stockage Kestra | une copie **par exécution** (historique, téléchargement UI) | le flow |

Avantage : chaque mois a son fichier dans l'historique Kestra, même si
`data/outputs/` est réécrit au run suivant.

### 4. `taskRunner: Process` répété sur chaque tâche

Kestra 2.0.5 refuse `pluginDefaults` dans un flow (vérifié contre l'API de
validation de l'instance : *Unrecognized field "pluginDefaults"*). Le
`taskRunner` est donc écrit sur chacune des 11 tâches de script. C'est
verbeux, mais explicite : chaque tâche dit où elle tourne.

## Conséquences

- Modifier un script SQL/Python suffit : le run suivant l'utilise, sans
  redéployer le flow.
- Le flow suppose le montage `./scripts` → `/bottleneck/scripts` (déjà dans
  `docker-compose.yml`).
