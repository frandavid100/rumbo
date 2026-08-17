import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PIPELINE=ROOT/"tools"/"catalog"/"run_pipeline_v1.py"
FIX=ROOT/"tools"/"catalog"/"fixtures"

def build(tmp:Path)->Path:
    db=tmp/"catalog.sqlite"
    subprocess.run([
        sys.executable,str(PIPELINE),
        "--mercadona-fixture",str(FIX/"mercadona_sample.json"),
        "--off-fixture",str(FIX/"off_sample.json"),
        "--secondary-fixture",str(FIX/"secondary_nutrition_sample.json"),
        "--generic-fixture",str(FIX/"generic_nutrition_sample.json"),
        "--output",str(db),
        "--report",str(tmp/"report.json"),
        "--evidence-dir",str(tmp/"evidence")
    ],check=True)
    return db

def test_vertical_sample():
    with tempfile.TemporaryDirectory() as td:
        db=build(Path(td)); con=sqlite3.connect(db)
        assert con.execute("select count(*) from products").fetchone()[0]==12
        assert con.execute("select count(*) from eligibility where menu_eligible=1").fetchone()[0]==12
        assert con.execute("select count(*) from eligibility where classified=1").fetchone()[0]==12
        assert con.execute("select count(*) from review_queue where status='OPEN'").fetchone()[0]==0
        assert con.execute("select count(*) from culinary_types").fetchone()[0]==12
        assert con.execute("select count(*) from nutritional_role_assignments").fetchone()[0]==12
        assert con.execute("select count(*) from culinary_role_assignments").fetchone()[0]==30
        levels=dict(con.execute("select evidence_level,count(*) from nutrition group by evidence_level").fetchall())
        assert levels=={"CORROBORATED":6,"GENERIC":5,"MATCHED":1}
        assert con.execute("select count(*) from evidence").fetchone()[0]==24
        assert con.execute("select count(*) from eligibility where reason is not null").fetchone()[0]==0

        # El tomate frito está correctamente clasificado culinariamente sin
        # inventar un rol nutricional incidental.
        sauce_id=con.execute("select id from products where canonical_name='Tomate frito Hacendado'").fetchone()[0]
        assert con.execute("select count(*) from nutritional_role_assignments where product_id=?",(sauce_id,)).fetchone()[0]==0
        assert {x[0] for x in con.execute("select role from culinary_role_assignments where product_id=?",(sauce_id,))}=={"SAUCE_DRESSING","TOPPING"}

        # La leche demuestra la clasificación nutricional múltiple.
        milk_id=con.execute("select id from products where gtin='8480000105424'").fetchone()[0]
        assert {x[0] for x in con.execute("select role from nutritional_role_assignments where product_id=?",(milk_id,))}=={"COMPLEMENTARY_PROTEIN","COMPLEMENTARY_CARBOHYDRATE"}

        image=con.execute("select kind,source,license,attribution,redistributable,is_primary from product_images").fetchone()
        assert image==("front","Open Food Facts","CC BY-SA","Open Food Facts contributors",1,1)
        con.close()

def test_ids_are_stable():
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td)
        a=sqlite3.connect(build(tmp/"a")).execute("select id,gtin,canonical_name from products order by id").fetchall()
        b=sqlite3.connect(build(tmp/"b")).execute("select id,gtin,canonical_name from products order by id").fetchall()
        assert a==b
