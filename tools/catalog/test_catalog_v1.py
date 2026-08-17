import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"tools"/"catalog"/"build_catalog_v1.py"
FIX=ROOT/"tools"/"catalog"/"fixtures"

def build(tmp:Path)->Path:
    db=tmp/"catalog.sqlite"
    subprocess.run([sys.executable,str(SCRIPT),"--mercadona-fixture",str(FIX/"mercadona_sample.json"),"--off-fixture",str(FIX/"off_sample.json"),"--secondary-fixture",str(FIX/"secondary_nutrition_sample.json"),"--generic-fixture",str(FIX/"generic_nutrition_sample.json"),"--output",str(db),"--report",str(tmp/"report.json"),"--evidence-dir",str(tmp/"evidence")],check=True)
    return db

def test_vertical_sample():
    with tempfile.TemporaryDirectory() as td:
        db=build(Path(td)); con=sqlite3.connect(db)
        assert con.execute("select count(*) from products").fetchone()[0]==12
        assert con.execute("select count(*) from eligibility where menu_eligible=1").fetchone()[0]==12
        assert con.execute("select count(*) from eligibility where classified=1").fetchone()[0]==12
        levels=dict(con.execute("select evidence_level,count(*) from nutrition group by evidence_level").fetchall())
        assert levels=={"CORROBORATED":6,"GENERIC":5,"MATCHED":1}
        assert con.execute("select count(*) from evidence").fetchone()[0]==24
        assert con.execute("select count(*) from eligibility where reason is not null").fetchone()[0]==0
        con.close()

def test_ids_are_stable():
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td); a=sqlite3.connect(build(tmp/"a")).execute("select id,gtin,canonical_name from products order by id").fetchall(); b=sqlite3.connect(build(tmp/"b")).execute("select id,gtin,canonical_name from products order by id").fetchall(); assert a==b
