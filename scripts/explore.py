"""Profil des 3 fichiers sources (lecture seule).

Usage : make explore
"""

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "python"))

import pandas as pd  # noqa: E402

import settings  # noqa: E402
from ingest import _to_text  # noqa: E402

warnings.filterwarnings("ignore", message="Unknown extension is not supported")
pd.set_option("display.width", 200)

# Clé métier supposée de chaque fichier
KEYS = {"erp": "product_id", "liaison": "product_id", "web": "sku"}


def title(text: str) -> None:
    print(f"\n{'═' * 100}\n  {text}\n{'═' * 100}")


def empty_rows(df: pd.DataFrame) -> int:
    """Lignes vides, en ignorant les colonnes constantes (ex. web : virtual = 0 partout)."""
    varying = [c for c in df.columns if df[c].nunique(dropna=False) > 1]
    return int(df[varying].isna().all(axis=1).sum())


def examples(series: pd.Series, n: int = 3) -> str:
    values = series.dropna().unique()[:n]
    return " | ".join(str(v)[:28] for v in values) or "—"


def profile(name: str, df: pd.DataFrame) -> None:
    key = KEYS[name]
    title(f"{name}.xlsx — {len(df)} lignes × {df.shape[1]} colonnes")
    dup_exact = df.duplicated().sum()
    dup_key = df[key].dropna().duplicated().sum()
    print(f"  Doublons exacts (ligne entière)   : {dup_exact}")
    print(f"  Doublons sur la clé `{key}`{' ' * (11 - len(key))}: {dup_key}")
    print(f"  Lignes vides                      : {empty_rows(df)}\n")

    print(f"  {'colonne':<22} {'type':<15} {'nulls':>6} {'distincts':>10}  {'clé ?':<6} exemples")
    print("  " + "─" * 98)
    for col in df.columns:
        s = df[col]
        types = sorted({type(v).__name__ for v in s.dropna()})
        dtype = str(s.dtype) if len(types) <= 1 else "mixte:" + "/".join(types)
        candidate = "oui" if s.notna().all() and s.is_unique else ""
        print(
            f"  {col:<22} {dtype:<15} {s.isna().sum():>6} {s.nunique():>10}  "
            f"{candidate:<6} {examples(s)}"
        )


def findings(erp: pd.DataFrame, liaison: pd.DataFrame, web: pd.DataFrame) -> None:
    title("Constats pour la chaîne de traitement")
    # Clés en texte, comme dans l'ingestion DuckDB
    liaison = liaison.assign(id_web=liaison["id_web"].map(_to_text))
    web = web.assign(sku=web["sku"].map(_to_text))
    web_ok = web.dropna(subset=["sku"])

    print("  1. Clés de jointure : erp.product_id = liaison.product_id ; liaison.id_web = web.sku")
    for name, col, s in (("liaison", "id_web", liaison["id_web"]), ("web", "sku", web["sku"])):
        texts = sorted({v for v in s.dropna() if not v.isdigit()})
        print(f"     - {name}.{col} non numériques : {texts}  → clés lues en TEXTE")

    print(f"\n  2. web : {web['sku'].isna().sum()} lignes sans sku "
          f"(dont {empty_rows(web)} vides) → "
          f"{len(web_ok)} lignes après nettoyage")
    print(f"     post_type après nettoyage : {web_ok['post_type'].value_counts().to_dict()}")
    print(f"     occurrences par sku       : {web_ok['sku'].value_counts().value_counts().to_dict()} "
          "(nb d'occurrences : nb de sku)")
    diff = web_ok.groupby("sku")["total_sales"].nunique()
    print(f"     sku dont product/attachment ont un total_sales différent : {sorted(diff[diff > 1].index)}")

    print(f"\n  3. liaison : {liaison['id_web'].isna().sum()} produits ERP sans id_web "
          f"({liaison['id_web'].notna().sum()} avec)")
    linked = liaison.dropna(subset=["id_web"])
    in_web = linked["id_web"].isin(web_ok["sku"])
    print(f"     id_web retrouvés dans web : {in_web.sum()} ; absents : {(~in_web).sum()}")

    m = erp.merge(liaison, on="product_id").merge(
        web_ok[web_ok["post_type"] == "product"], left_on="id_web", right_on="sku"
    )
    print(f"\n  4. Fusion erp ⋈ liaison ⋈ web(product) : {len(m)} lignes ; "
          f"onsale_web dans la fusion : {m['onsale_web'].value_counts().to_dict()}")

    print(f"\n  5. ERP : prix min {erp['price'].min()} / max {erp['price'].max()} ; "
          f"prix ≤ 0 : {(erp['price'] <= 0).sum()} produit(s) ; "
          f"onsale_web : {erp['onsale_web'].value_counts().to_dict()}")
    incoherent = ((erp["stock_status"] == "outofstock") & (erp["stock_quantity"] > 0)) | (
        (erp["stock_status"] == "instock") & (erp["stock_quantity"] <= 0)
    )
    print(f"     stock_status incohérent avec stock_quantity : {incoherent.sum()} produit(s)")


if __name__ == "__main__":
    frames = {}
    for name, path in settings.SOURCES.items():
        frames[name] = pd.read_excel(path)
        profile(name, frames[name])
    findings(frames["erp"], frames["liaison"], frames["web"])
