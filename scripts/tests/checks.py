"""Tests du flow : un test par tâche nominale.

Usage : python checks.py test_<tâche>   (code retour 1 si un contrôle est KO)
"""

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

import duckdb  # noqa: E402
import pandas as pd  # noqa: E402
import settings  # noqa: E402

E = settings.EXPECTED

# Colonnes utilisées par la suite de la chaîne
COLONNES_SOURCES = {
    "raw_erp": ["product_id", "onsale_web", "price", "stock_quantity", "stock_status"],
    "raw_liaison": ["product_id", "id_web"],
    "raw_web": ["sku", "total_sales", "post_title", "post_name", "post_type", "post_modified"],
}


def euros(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"))


def q(con, sql: str):
    return con.execute(sql).fetchone()[0]


def doublons(con, table: str, cle: str) -> int:
    return q(con, f"SELECT COUNT({cle}) - COUNT(DISTINCT {cle}) FROM {table}")


def manquants(con, table: str, cle: str) -> int:
    return q(con, f"SELECT COUNT(*) FILTER (WHERE {cle} IS NULL) FROM {table}")


def lignes(con, table: str) -> int:
    return q(con, f"SELECT COUNT(*) FROM {table}")


# Chaque test renvoie une liste de (libellé, attendu, obtenu).


def test_ingest(con):
    checks = []
    for table, colonnes in COLONNES_SOURCES.items():
        presentes = {r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()}
        absentes = [c for c in colonnes if c not in presentes]
        checks.append((f"{table} : colonnes absentes", [], absentes))
    checks += [
        ("raw_erp : lignes", E["raw_erp_rows"], lignes(con, "raw_erp")),
        ("raw_liaison : lignes", E["raw_liaison_rows"], lignes(con, "raw_liaison")),
        ("raw_web : lignes", E["raw_web_rows"], lignes(con, "raw_web")),
    ]
    return checks


def test_clean_erp(con):
    return [
        ("product_id en double", 0, doublons(con, "erp_dedup", "product_id")),
        ("product_id manquant", 0, manquants(con, "erp_dedup", "product_id")),
        ("erp_dedup : lignes", E["erp_rows"], lignes(con, "erp_dedup")),
    ]


def test_clean_liaison(con):
    return [
        ("product_id en double", 0, doublons(con, "liaison_dedup", "product_id")),
        ("id_web en double", 0, doublons(con, "liaison_dedup", "id_web")),
        ("liaison_dedup : lignes", E["liaison_rows"], lignes(con, "liaison_dedup")),
    ]


def test_clean_web(con):
    return [
        ("sku manquant", 0, manquants(con, "web_nettoye", "sku")),
        ("web_nettoye : lignes", E["web_rows_cleaned"], lignes(con, "web_nettoye")),
    ]


def test_dedup_web(con):
    return [
        ("sku en double", 0, doublons(con, "web_dedup", "sku")),
        ("total_sales manquant", 0, manquants(con, "web_dedup", "total_sales")),
        ("web_dedup : lignes", E["web_rows_deduped"], lignes(con, "web_dedup")),
    ]


def test_merge(con):
    return [
        ("fusion = web_dedup (aucun produit web perdu)", lignes(con, "web_dedup"), lignes(con, "fusion")),
        ("product_id en double", 0, doublons(con, "fusion", "product_id")),
        ("sku en double", 0, doublons(con, "fusion", "sku")),
        ("prix manquant", 0, manquants(con, "fusion", "prix")),
        ("fusion : lignes", E["merged_rows"], lignes(con, "fusion")),
    ]


def test_ca(con):
    total = q(con, "SELECT ca_total FROM ca_total")
    return [
        ("Σ CA par produit = CA total", euros(total), euros(q(con, "SELECT SUM(ca) FROM ca_par_produit"))),
        ("CA négatif", 0, q(con, "SELECT COUNT(*) FILTER (WHERE ca < 0) FROM ca_par_produit")),
        ("ca_par_produit = fusion", lignes(con, "fusion"), lignes(con, "ca_par_produit")),
        ("CA total (€)", euros(E["ca_total"]), euros(total)),
    ]


def test_zscore(con):
    seuil = settings.ZSCORE_THRESHOLD
    mil, ordi = lignes(con, "vins_millesimes"), lignes(con, "vins_ordinaires")
    return [
        ("millésimes + ordinaires = fusion", lignes(con, "fusion"), mil + ordi),
        (f"millésime avec z ≤ {seuil:g}", 0, q(con, f"SELECT COUNT(*) FROM vins_millesimes WHERE z_score <= {seuil}")),
        (f"ordinaire avec z > {seuil:g}", 0, q(con, f"SELECT COUNT(*) FROM vins_ordinaires WHERE z_score > {seuil}")),
        ("vins millésimes", E["millesimes"], mil),
    ]


def test_export_rapport_ca(con):
    path = settings.DATA_OUTPUT_DIR / settings.livrable_filename(3, "rapport_ca", "xlsx")
    onglets = pd.read_excel(path, sheet_name=None)
    produits, total = onglets["CA par produit"], onglets["CA total"]
    ca_fichier = euros(total["CA total (€)"].iloc[0])
    return [
        ("onglets", ["CA par produit", "CA total"], list(onglets)),
        ("lignes = ca_par_produit", lignes(con, "ca_par_produit"), len(produits)),
        ("CA total = base", euros(q(con, "SELECT ca_total FROM ca_total")), ca_fichier),
        ("Σ CA des lignes = CA total", ca_fichier, euros(produits["Chiffre d'affaires (€)"].sum())),
        ("lignes", E["merged_rows"], len(produits)),
        ("CA total (€)", euros(E["ca_total"]), ca_fichier),
    ]


def _test_export_vins(con, numero: int, categorie: str, attendu: int):
    path = settings.DATA_OUTPUT_DIR / settings.livrable_filename(numero, f"vins_{categorie}", "csv")
    df = pd.read_csv(path, sep=";", decimal=",", encoding="utf-8-sig")
    return [
        (f"lignes = vins_{categorie}", lignes(con, f"vins_{categorie}"), len(df)),
        ("product_id en double", 0, int(df["product_id"].duplicated().sum())),
        ("lignes", attendu, len(df)),
    ]


def test_export_millesimes(con):
    return _test_export_vins(con, 4, "millesimes", E["millesimes"])


def test_export_ordinaires(con):
    return _test_export_vins(con, 5, "ordinaires", E["merged_rows"] - E["millesimes"])


TESTS = {name: f for name, f in globals().items() if name.startswith("test_")}


def run(con, test: str) -> bool:
    ok = True
    print(test)
    for libelle, attendu, obtenu in TESTS[test](con):
        bon = attendu == obtenu
        ok &= bon
        print(f"   {'OK' if bon else 'KO'}  {libelle} : attendu {attendu}, obtenu {obtenu}")
    return ok


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in TESTS:
        sys.exit(f"Usage : checks.py {{{'|'.join(TESTS)}}}")
    with duckdb.connect(str(settings.DUCKDB_PATH), read_only=True) as con:
        ok = run(con, sys.argv[1])
    if not ok:
        sys.exit(f"{sys.argv[1]} : contrôle KO")
