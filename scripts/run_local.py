"""Rejoue la chaîne hors Kestra (ingestion, SQL, z-score) puis les tests du flow.

Usage : make check
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "python"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

import checks  # noqa: E402
import duckdb  # noqa: E402
import settings  # noqa: E402
from ingest import ingest  # noqa: E402
from zscore import classify  # noqa: E402

if __name__ == "__main__":
    with duckdb.connect(str(settings.DUCKDB_PATH)) as con:
        ingest(con)
        for sql_file in sorted(settings.SQL_DIR.glob("[0-9][0-9]_*.sql")):
            con.execute(sql_file.read_text(encoding="utf-8"))
        classify(con, settings.ZSCORE_THRESHOLD)
        ok = True
        for test in checks.TESTS:
            if not test.startswith("test_export"):
                ok &= checks.run(con, test)
    print("\nTous les contrôles sont OK." if ok else "\nAu moins un contrôle est KO.")
    sys.exit(0 if ok else 1)
