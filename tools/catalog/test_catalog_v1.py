import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "catalog" / "build_catalog_v1.py"
MERCADONA = ROOT / "tools" / "catalog" / "fixtures" / "mercadona_sample.json"
OFF = ROOT / "tools" / "catalog" / "fixtures" / "off_sample.json"


def build(tmp: Path) -> Path:
    db = tmp / "catalog.sqlite"
    subprocess.run([
        sys.executable, str(SCRIPT),
        "--mercadona-fixture", str(MERCADONA),
        "--off-fixture", str(OFF),
        "--output", str(db),
        "--report", str(tmp / "report.json"),
        "--evidence-dir", str(tmp / "evidence"),
    ], check=True)
    return db


def test_vertical_sample():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        db = build(tmp)
        con = sqlite3.connect(db)
        assert con.execute("select count(*) from products").fetchone()[0] == 3
        assert con.execute("select count(*) from eligibility where menu_eligible=1").fetchone()[0] == 1
        assert con.execute("select count(*) from evidence").fetchone()[0] == 4
        rice = con.execute("select calories,protein_g from nutrition").fetchone()
        assert rice == (353.0, 9.0)
        missing = con.execute("select count(*) from eligibility where reason='Falta nutrición comparable'").fetchone()[0]
        assert missing == 2
        con.close()


def test_ids_are_stable():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        first = build(tmp / "one")
        second = build(tmp / "two")
        a = sqlite3.connect(first).execute("select id,gtin,canonical_name from products order by id").fetchall()
        b = sqlite3.connect(second).execute("select id,gtin,canonical_name from products order by id").fetchall()
        assert a == b
