"""Exporte le rapport CA en Excel : onglets « CA par produit » et « CA total ».

Usage : python export_rapport_ca.py [out_dir]
"""

import sys
from pathlib import Path

import duckdb
import pandas as pd
from openpyxl.styles import Font

import settings

EURO = '#,##0.00 "€"'

COLONNES_PRODUIT = {
    "product_id": "ID produit (ERP)",
    "sku": "SKU (web)",
    "nom_produit": "Produit",
    "prix": "Prix unitaire (€)",
    "quantite_vendue": "Quantité vendue",
    "ca": "Chiffre d'affaires (€)",
}
COLONNES_TOTAL = {
    "ca_total": "CA total (€)",
    "nb_produits": "Produits au catalogue en ligne",
    "nb_produits_vendus": "Produits vendus (CA > 0)",
}


def _mettre_en_forme(ws, colonnes_euro, largeurs):
    ws.freeze_panes = "A2"
    for cell in ws[1]:
        cell.font = Font(bold=True)
        ws.column_dimensions[cell.column_letter].width = largeurs.get(cell.value, 25)
        if cell.value in colonnes_euro:
            for c in ws[cell.column_letter][1:]:
                c.number_format = EURO


def export(con, out_dir):
    par_produit = con.execute(
        f"SELECT {', '.join(COLONNES_PRODUIT)} FROM ca_par_produit ORDER BY ca DESC, product_id"
    ).df()
    total = con.execute(f"SELECT {', '.join(COLONNES_TOTAL)} FROM ca_total").df()
    par_produit[["prix", "ca"]] = par_produit[["prix", "ca"]].astype(float)
    total["ca_total"] = total["ca_total"].astype(float)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / settings.livrable_filename(3, "rapport_ca", "xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        par_produit.rename(columns=COLONNES_PRODUIT).to_excel(writer, sheet_name="CA par produit", index=False)
        total.rename(columns=COLONNES_TOTAL).to_excel(writer, sheet_name="CA total", index=False)
        _mettre_en_forme(
            writer.sheets["CA par produit"],
            {COLONNES_PRODUIT["prix"], COLONNES_PRODUIT["ca"]},
            {COLONNES_PRODUIT["nom_produit"]: 60},
        )
        _mettre_en_forme(writer.sheets["CA total"], {COLONNES_TOTAL["ca_total"]}, {})
    return path


if __name__ == "__main__":
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else settings.DATA_OUTPUT_DIR
    with duckdb.connect(str(settings.DUCKDB_PATH), read_only=True) as con:
        path = export(con, out_dir)
    print(path.name)
