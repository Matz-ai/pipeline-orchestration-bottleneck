# Dictionnaire de données — sources BottleNeck

> Schéma **réel** des 3 fichiers du zip OC, établi à partir de
> `make explore` ([`scripts/explore.py`](../scripts/explore.py)). Le brief ne
> le documente pas : tout ce qui est marqué « déduit » est une interprétation,
> à confirmer avec Stéphane (Data Analyst) ou le métier.

## Vue d'ensemble

| Fichier        | Système                 | Lignes | Colonnes | Clé          | Rôle                                       |
| -------------- | ----------------------- | -----: | -------: | ------------ | ------------------------------------------ |
| `erp.xlsx`     | ERP interne             |    825 |        5 | `product_id` | Référentiel produits : **prix**, stock     |
| `liaison.xlsx` | Table de correspondance |    825 |        2 | `product_id` | Relie l'ERP (`product_id`) au CMS (`id_web`) |
| `web.xlsx`     | CMS WordPress/WooCommerce |  1 513 |       28 | `sku`        | Catalogue en ligne : **ventes**, libellés  |

## Clé de jointure

```text
erp.product_id ──1:1── liaison.product_id
                       liaison.id_web ──1:1── web.sku   (après dédoublonnage du web)
```

- Le **prix** vient de l'ERP, la **quantité vendue** du CMS : le CA exige donc
  la réconciliation des deux systèmes, et elle passe **obligatoirement** par
  la liaison.
- `id_web` et `sku` sont **le même identifiant** (celui du CMS), sous deux
  noms différents.
- Ces deux colonnes **mélangent entiers et texte** dans Excel :
  `13127-1`, `14680-1`, `bon-cadeau-25-euros`. Elles sont donc chargées en
  **texte** (`VARCHAR`) dans DuckDB. Lues en nombre, ces 3 clés seraient
  perdues ou provoqueraient une erreur de type à la jointure.

Couverture des 825 produits de l'ERP :

| Cas                                                 | Produits | `onsale_web` | Dans la fusion |
| --------------------------------------------------- | -------: | :----------: | :------------: |
| Avec `id_web`, présent sur le site                  |      714 | 1            | oui            |
| Avec `id_web`, absent du site                       |       20 | 0            | —              |
| Sans `id_web`, pas en vente en ligne                |       88 | 0            | —              |
| Sans `id_web`, **mais** `onsale_web = 1`            |        3 | 1            | — (anomalie)   |

Les 714 lignes fusionnées ont toutes `onsale_web = 1` : la fusion retrouve
exactement les produits vendus en ligne.

---

## `erp.xlsx` — ERP

825 lignes, aucun doublon (ni exact, ni sur la clé), aucune valeur manquante.

| Colonne          | Type    | Nulls | Distincts | Exemple      | Rôle métier (déduit)                                  |
| ---------------- | ------- | ----: | --------: | ------------ | ----------------------------------------------------- |
| `product_id`     | entier  |     0 |       825 | `3847`       | **Clé** produit interne                               |
| `onsale_web`     | 0 / 1   |     0 |         2 | `1`          | Produit mis en vente sur le site (717 oui, 108 non)   |
| `price`          | décimal |     0 |       382 | `24.2`       | **Prix de vente unitaire TTC (€)**, base du CA et du z-score |
| `stock_quantity` | entier  |     0 |       129 | `15`         | Quantité en stock                                     |
| `stock_status`   | texte   |     0 |         2 | `instock`    | `instock` (638) / `outofstock` (187)                  |

Anomalies relevées (aucun impact sur les 7 chiffres) :

- **2 prix négatifs** (`-1` et `-8`, produits 6594 et 5017). Ils ne sont pas en
  vente en ligne, donc absents de la fusion. À signaler au métier.
- **6 statuts de stock incohérents** avec la quantité (ex. `outofstock` avec
  48 bouteilles). Le statut n'est pas utilisé dans les calculs.

## `liaison.xlsx` — table de correspondance

825 lignes, une par produit ERP, aucun doublon.

| Colonne      | Type                | Nulls | Distincts | Exemple   | Rôle métier (déduit)                     |
| ------------ | ------------------- | ----: | --------: | --------- | ---------------------------------------- |
| `product_id` | entier              |     0 |       825 | `3847`    | **Clé** ERP                              |
| `id_web`     | **mixte** int/texte |    91 |       734 | `15298`   | Identifiant CMS (= `web.sku`), vide si le produit n'est pas référencé en ligne |

Les 91 `id_web` vides sont **conservés** : la référence attend 825 lignes
après dédoublonnage. Ils disparaissent naturellement à la fusion (jointure
interne).

## `web.xlsx` — CMS (WordPress / WooCommerce)

Export brut de la table `wp_posts` de WordPress, enrichie de quelques champs
WooCommerce. 1 513 lignes, 28 colonnes.

**Particularité clé** : chaque produit apparaît **deux fois**, avec le même `sku` :

| `post_type`  | Ce que c'est                         | Lignes | Signe distinctif              |
| ------------ | ------------------------------------ | -----: | ----------------------------- |
| `product`    | La **fiche produit**                 |    714 | `guid` = `?post_type=product&p=…` |
| `attachment` | L'**image** du produit (pièce jointe) |    714 | `post_mime_type = image/jpeg` |
| *(vide)*     | Lignes blanches de l'export          |     83 | toutes les colonnes vides     |
| *(sans sku)* | 2 fiches produit **sans sku**        |      2 | Pierre Jean Villa (Condrieu, Côte Rôtie) |

Ce ne sont **pas des doublons exacts** : `guid`, `post_type`,
`post_mime_type`… diffèrent. Les 82 doublons exacts relevés par le profil
sont les lignes blanches entre elles.

| Colonne                 | Type       | Nulls | Distincts | Rôle métier (déduit)                                          |
| ----------------------- | ---------- | ----: | --------: | ------------------------------------------------------------- |
| `sku`                   | **mixte**  |    85 |       714 | **Clé** CMS (= `liaison.id_web`)                              |
| `virtual`               | 0          |     0 |         1 | Produit virtuel (toujours 0)                                  |
| `downloadable`          | 0          |     0 |         1 | Produit téléchargeable (toujours 0)                           |
| `rating_count`          | 0          |     0 |         1 | Nombre d'avis (toujours 0)                                    |
| `average_rating`        | décimal    |    83 |         1 | Note moyenne (toujours 0)                                     |
| `total_sales`           | décimal    |    83 |        41 | **Quantité vendue** (cumul), base du CA                       |
| `tax_status`            | texte      |   797 |         1 | `taxable` sur les fiches produit                              |
| `tax_class`             | —          | 1 513 |         0 | Vide                                                          |
| `post_author`           | décimal    |    83 |         2 | Id de l'auteur WordPress                                      |
| `post_date` / `_gmt`    | date-heure |    83 |       716 | Date de création (heure locale / UTC)                         |
| `post_content`          | —          | 1 513 |         0 | Vide                                                          |
| `post_title`            | texte      |    83 |       713 | **Nom du vin** (contient des entités HTML : `&amp;`)          |
| `post_excerpt`          | texte      |   797 |       679 | Description courte (HTML possible)                            |
| `post_status`           | texte      |    83 |         1 | `publish`                                                     |
| `comment_status`        | texte      |    83 |         1 | `closed`                                                      |
| `ping_status`           | texte      |    83 |         1 | `closed`                                                      |
| `post_password`         | —          | 1 513 |         0 | Vide                                                          |
| `post_name`             | texte      |    83 |       716 | Slug d'URL                                                    |
| `post_modified` / `_gmt`| date-heure |    83 |       589 | Date de dernière modification                                 |
| `post_content_filtered` | —          | 1 513 |         0 | Vide                                                          |
| `post_parent`           | décimal    |    83 |         1 | Toujours 0                                                    |
| `guid`                  | texte      |    83 |     1 429 | URL de la fiche ou de l'image                                 |
| `menu_order`            | décimal    |    83 |         1 | Toujours 0                                                    |
| `post_type`             | texte      |    83 |         2 | `product` / `attachment` (cf. ci-dessus)                      |
| `post_mime_type`        | texte      |   799 |         1 | `image/jpeg` sur les images                                   |
| `comment_count`         | décimal    |    83 |         1 | Toujours 0                                                    |

**Piège** : pour 3 `sku`, la ligne `attachment` porte un `total_sales`
différent de la fiche `product` :

| `sku`  | Vin                                           | `product` | `attachment` |
| ------ | --------------------------------------------- | --------: | -----------: |
| 7818   | Champagne Gosset Grand Blanc de Blancs        |        96 |            6 |
| 1662   | Champagne Gosset Grand Rosé                   |        87 |            7 |
| 16416  | Gilles Robin Crozes-Hermitage Rouge Papillon 2019 |    62 |            2 |

Garder la ligne `attachment` ferait tomber le CA à **61 242,60 €** au lieu de
70 568,60 €. Le dédoublonnage garde donc **explicitement** la fiche
`product` (cf. [`04_dedup_web.sql`](../scripts/sql/04_dedup_web.sql)).

---

## Tables produites dans `data/warehouse.duckdb`

| Table / vue        | Script                  | Lignes | Contenu                                         |
| ------------------ | ----------------------- | -----: | ----------------------------------------------- |
| `raw_erp`          | `python/ingest.py`      |    825 | Copie fidèle de `erp.xlsx`                      |
| `raw_liaison`      | `python/ingest.py`      |    825 | Copie fidèle, `id_web` en texte                 |
| `raw_web`          | `python/ingest.py`      |  1 513 | Copie fidèle, `sku` en texte                    |
| `erp_dedup`        | `sql/01_clean_erp.sql`  |    825 | ERP sans clé nulle ni doublon exact             |
| `liaison_dedup`    | `sql/02_clean_liaison.sql` |  825 | Liaison sans clé nulle ni doublon exact         |
| `web_nettoye`      | `sql/03_clean_web.sql`  |  1 428 | Web sans ligne à `sku` manquant                 |
| `web_dedup`        | `sql/04_dedup_web.sql`  |    714 | Une ligne par `sku` (la fiche `product`)        |
| `fusion`           | `sql/05_merge.sql`      |    714 | ERP ⋈ liaison ⋈ web : prix + ventes + libellé   |
| `ca_par_produit`   | `sql/06_ca.sql`         |    714 | CA = prix × quantité vendue, en `DECIMAL`       |
| `ca_total`         | `sql/06_ca.sql`         |      1 | CA total (70 568,60 €), nb de produits          |
| `vins_zscore`      | `python/zscore.py`      |    714 | z-score du prix + catégorie                     |
| `vins_millesimes`  | `python/zscore.py` (vue) |    30 | z > 2, soit prix > 88,08 €                      |
| `vins_ordinaires`  | `python/zscore.py` (vue) |   684 | z ≤ 2                                           |

Colonnes de `fusion` : `product_id`, `sku`, `nom_produit`, `slug`, `prix`,
`quantite_vendue`, `stock`, `statut_stock`, `en_vente_web`.

### Paramètres du z-score

| Grandeur            | Valeur      |
| ------------------- | ----------- |
| Population          | 714 vins de la fusion (vendus en ligne) |
| Prix moyen          | 32,49 €     |
| Écart-type (population) | 27,79 € |
| Seuil `z > 2`       | prix > 88,08 € |
| Millésimes          | **30**      |

Sur les 825 produits de l'ERP, on obtiendrait 34 millésimes : la population
de Stéphane est bien celle de la fusion. Le résultat ne dépend pas de
l'écart-type choisi (population ou échantillon : 30 dans les deux cas).

Le « Bon cadeau de 25 € » (`sku` `bon-cadeau-25-euros`) n'est pas un vin mais
fait partie des 714 produits, et donc de la population du z-score. Il est
classé ordinaire et l'exclure ne change pas le compte de millésimes. Il est
conservé pour rester aligné sur les chiffres de Stéphane.
