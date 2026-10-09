"""Télécharge le zip OpenClassrooms et extrait erp.xlsx, liaison.xlsx, web.xlsx dans data/raw/."""

import io
import urllib.request
import zipfile
from pathlib import Path

URL = "https://s3.eu-west-1.amazonaws.com/course.oc-static.com/projects/922_Data+Engineer/922_P10/bottleneck.zip"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

if __name__ == "__main__":
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL, timeout=60) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    for member in archive.namelist():
        stem = Path(member).stem.lower()
        for name in ("erp", "liaison", "web"):
            if member.endswith(".xlsx") and stem.endswith(name):
                (RAW_DIR / f"{name}.xlsx").write_bytes(archive.read(member))
                print(f"{member} -> data/raw/{name}.xlsx")
