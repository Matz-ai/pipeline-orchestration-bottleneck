"""Chemins et paramètres du pipeline (variables d'environnement du conteneur Kestra)."""

import os
from pathlib import Path

DUCKDB_PATH = Path(os.getenv("ENV_DUCKDB_PATH", "/bottleneck/data/warehouse.duckdb"))
DATA_RAW_DIR = Path(os.getenv("ENV_DATA_RAW_DIR", "/bottleneck/data/raw"))
DATA_OUTPUT_DIR = Path(os.getenv("ENV_DATA_OUTPUT_DIR", "/bottleneck/data/outputs"))
SQL_DIR = Path(os.getenv("ENV_SCRIPTS_DIR", "/bottleneck/scripts")) / "sql"
ZSCORE_THRESHOLD = float(os.getenv("ENV_ZSCORE_THRESHOLD", "2"))

SOURCES = {
    "erp": DATA_RAW_DIR / "erp.xlsx",
    "liaison": DATA_RAW_DIR / "liaison.xlsx",
    "web": DATA_RAW_DIR / "web.xlsx",
}

# Valeurs de référence de Stéphane (+ volumes bruts des exports)
EXPECTED = {
    "raw_erp_rows": 825,
    "raw_liaison_rows": 825,
    "raw_web_rows": 1513,
    "erp_rows": 825,
    "liaison_rows": 825,
    "web_rows_cleaned": 1428,
    "web_rows_deduped": 714,
    "merged_rows": 714,
    "ca_total": 70568.60,
    "millesimes": 30,
}


def livrable_filename(numero, nom, extension):
    """Nom_Prenom_<n°>_<nom>_<mmaaaa>.<ext>, avec les valeurs du .env."""
    parts = [os.getenv(f"ENV_LIVRABLE_{k}", "") for k in ("NOM", "PRENOM", "DATE")]
    if not all(parts):
        raise RuntimeError("Remplir LIVRABLE_NOM, LIVRABLE_PRENOM et LIVRABLE_DATE dans .env")
    return f"{parts[0]}_{parts[1]}_{numero}_{nom}_{parts[2]}.{extension}"
