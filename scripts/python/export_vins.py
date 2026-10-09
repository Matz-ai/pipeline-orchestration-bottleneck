"""Exporte les vins millésimes ou ordinaires en CSV (séparateur ;, virgule décimale).

Usage : python export_vins.py {millesimes|ordinaires} [out_dir]
"""

import sys
from pathlib import Path

import duckdb

import settings

LIVRABLES = {"millesimes": 4, "ordinaires": 5}


def export(con, categorie, out_dir):
    df = con.execute(
        "SELECT product_id, sku, nom_produit, prix, CAST(quantite_vendue AS INTEGER) AS quantite_vendue, "
        f"ROUND(z_score, 4) AS z_score FROM vins_{categorie} ORDER BY z_score DESC, product_id"
    ).df()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / settings.livrable_filename(LIVRABLES[categorie], f"vins_{categorie}", "csv")
    df.to_csv(path, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    return path, len(df)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in LIVRABLES:
        sys.exit("Usage : export_vins.py {millesimes|ordinaires} [out_dir]")
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else settings.DATA_OUTPUT_DIR
    with duckdb.connect(str(settings.DUCKDB_PATH), read_only=True) as con:
        path, n = export(con, sys.argv[1], out_dir)
    print(f"{path.name} : {n} vins")
