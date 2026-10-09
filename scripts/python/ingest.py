"""Charge les 3 fichiers Excel dans DuckDB (raw_erp, raw_liaison, raw_web)."""

import math
import warnings

import duckdb
import pandas as pd

import settings

warnings.filterwarnings("ignore", message="Unknown extension is not supported")

# Clés de jointure qui mélangent nombres et texte dans Excel : lues en texte
TEXT_KEYS = {"liaison": ["id_web"], "web": ["sku"]}


def _to_text(value):
    """16004.0 -> '16004', '13127-1' -> '13127-1', vide -> None."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def ingest(con):
    counts = {}
    for name, path in settings.SOURCES.items():
        df = pd.read_excel(path)
        for col in TEXT_KEYS.get(name, []):
            df[col] = df[col].map(_to_text).astype("string")
        con.register("df_source", df)
        con.execute(f"CREATE OR REPLACE TABLE raw_{name} AS SELECT * FROM df_source")
        con.unregister("df_source")
        counts[f"raw_{name}"] = len(df)
    return counts


if __name__ == "__main__":
    with duckdb.connect(str(settings.DUCKDB_PATH)) as con:
        for table, n in ingest(con).items():
            print(f"{table} : {n} lignes")
