import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "catalog" / "build_catalog_v1.py"
MERCADONA = ROOT / "tools" / "catalog" / "fixtures" / "mercadona_sample.json"
OFF = ROOT / "tools" / "catalog" / "fixtures" / "off_sample.json"
SECONDARY = ROOT / "tools" / "catalog" / "fixtures" / "secondary_nutrition_sample.json"


def build(tmp: Path) -> Path:
    db = tmp / "catalog.sqlite"
    subprocess.run([
        sys.executable, str(SCRIPT),
        "--mercadona-fixture", str(MERCADONA),
        "--off-fixture", str(OFF),
        "--secondary-fixture", str(SECONDARY),
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
        assert con.execute("select count(*) from eligibility where menu_eligible=1").fetchone()[0] == 3
        assert con.execute("select count(*) from evidence").fetchone()[0] == 6
        levels = dict(con.execute("select evidence_level,count(*) from nutrition group by evidence_level").fetchall())
        assert levels == {"CORROBORATED": 2, "MATCHED": 1}
        milk = con.execute("select calories,protein_g from nutrition n join products p on p.id=n.product_id where p.gtin='8480000105424'").fetchone()
        assert milk == (46.0, 3.1)
        oil = con.execute("select calories,fat_g,carbohydrate_g,protein_g from nutrition n join products p on p.id=n.product_id where p.gtin='8480000047403'").fetchone()
        assert oil == (822.0, 91.0, 0.0, 0.0)
        assert con.execute("select count(*) from eligibility where reason is not null").fetchone()[0] == 0
        con.close()


def test_ids_are_stable():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        first = build(tmp / "one")
        second = build(tmp / "two")
        a = sqlite3.connect(first).execute("select id,gtin,canonical_name from products order by id").fetchall()
        b = sqlite3.connect(second).execute("select id,gtin,canonical_name from products order by id").fetchall()
        assert a == b
