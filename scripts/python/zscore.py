"""Classe les vins de la fusion en millésimes (z-score > 2) et ordinaires.

z = (prix - moyenne des prix) / écart-type des prix
"""

import duckdb

import settings


def classify(con, threshold):
    df = con.execute("SELECT product_id, sku, nom_produit, prix, quantite_vendue FROM fusion").df()
    mean, std = df["prix"].mean(), df["prix"].std(ddof=0)
    df["z_score"] = (df["prix"] - mean) / std
    df["categorie"] = df["z_score"].gt(threshold).map({True: "millesime", False: "ordinaire"})

    con.register("df_zscore", df)
    con.execute("CREATE OR REPLACE TABLE vins_zscore AS SELECT * FROM df_zscore")
    con.unregister("df_zscore")
    con.execute("CREATE OR REPLACE VIEW vins_millesimes AS SELECT * FROM vins_zscore WHERE categorie = 'millesime'")
    con.execute("CREATE OR REPLACE VIEW vins_ordinaires AS SELECT * FROM vins_zscore WHERE categorie = 'ordinaire'")
    return int((df["categorie"] == "millesime").sum())


if __name__ == "__main__":
    with duckdb.connect(str(settings.DUCKDB_PATH)) as con:
        print(f"{classify(con, settings.ZSCORE_THRESHOLD)} vins millésimes")
