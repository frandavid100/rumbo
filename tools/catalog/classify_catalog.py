#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path
from classifier import CLASSIFIER_VERSION, ProductFeatures, classify

SCHEMA = """
CREATE TABLE IF NOT EXISTS culinary_types(product_id INTEGER PRIMARY KEY,culinary_type TEXT NOT NULL,confidence REAL NOT NULL,rule_id TEXT NOT NULL,evidence_json TEXT NOT NULL,classifier_version TEXT NOT NULL,origin TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS nutritional_role_assignments(product_id INTEGER NOT NULL,role TEXT NOT NULL,confidence REAL NOT NULL,rule_id TEXT NOT NULL,evidence_json TEXT NOT NULL,classifier_version TEXT NOT NULL,origin TEXT NOT NULL,PRIMARY KEY(product_id,role));
CREATE TABLE IF NOT EXISTS culinary_role_assignments(product_id INTEGER NOT NULL,role TEXT NOT NULL,confidence REAL NOT NULL,rule_id TEXT NOT NULL,evidence_json TEXT NOT NULL,classifier_version TEXT NOT NULL,origin TEXT NOT NULL,PRIMARY KEY(product_id,role));
CREATE TABLE IF NOT EXISTS culinary_policies(product_id INTEGER PRIMARY KEY,preferred_grams REAL,minimum_grams REAL,maximum_grams REAL,standalone_allowed INTEGER NOT NULL,requires_cooking INTEGER NOT NULL,divisible INTEGER NOT NULL,classifier_version TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS culinary_relations(product_id INTEGER NOT NULL,source_role TEXT NOT NULL,intensity TEXT NOT NULL,target_role TEXT NOT NULL,hard INTEGER NOT NULL,classifier_version TEXT NOT NULL,PRIMARY KEY(product_id,source_role,intensity,target_role));
CREATE TABLE IF NOT EXISTS review_queue(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'OPEN',classifier_version TEXT NOT NULL,UNIQUE(product_id,reason,status));
CREATE INDEX IF NOT EXISTS idx_nutritional_role ON nutritional_role_assignments(role);
CREATE INDEX IF NOT EXISTS idx_culinary_role ON culinary_role_assignments(role);
CREATE INDEX IF NOT EXISTS idx_review_status ON review_queue(status);
"""

def store(con, pid, result):
    if result.culinary_type:
        a=result.culinary_type
        con.execute("INSERT INTO culinary_types VALUES(?,?,?,?,?,?,?)",(pid,a.value,a.confidence,a.rule_id,json.dumps(a.evidence,ensure_ascii=False),CLASSIFIER_VERSION,"AUTOMATIC"))
    for a in result.nutritional_roles:
        con.execute("INSERT INTO nutritional_role_assignments VALUES(?,?,?,?,?,?,?)",(pid,a.value,a.confidence,a.rule_id,json.dumps(a.evidence,ensure_ascii=False),CLASSIFIER_VERSION,"AUTOMATIC"))
    for a in result.culinary_roles:
        con.execute("INSERT INTO culinary_role_assignments VALUES(?,?,?,?,?,?,?)",(pid,a.value,a.confidence,a.rule_id,json.dumps(a.evidence,ensure_ascii=False),CLASSIFIER_VERSION,"AUTOMATIC"))
    con.execute("INSERT INTO culinary_policies VALUES(?,?,?,?,?,?,?,?)",(pid,result.preferred_grams,result.minimum_grams,result.maximum_grams,int(result.properties.get('standalone_allowed',False)),int(result.properties.get('requires_cooking',False)),int(result.properties.get('divisible',True)),CLASSIFIER_VERSION))
    for rel in result.relations:
        con.execute("INSERT INTO culinary_relations VALUES(?,?,?,?,?,?)",(pid,rel['source_role'],rel['intensity'],rel['target_role'],int(rel['hard']),CLASSIFIER_VERSION))
    for reason in result.review_reasons:
        con.execute("INSERT INTO review_queue(product_id,reason,status,classifier_version) VALUES(?,?,?,?)",(pid,reason,"OPEN",CLASSIFIER_VERSION))

def run(database: Path):
    con=sqlite3.connect(database); con.executescript(SCHEMA)
    for table in ('culinary_types','nutritional_role_assignments','culinary_role_assignments','culinary_policies','culinary_relations','review_queue'):
        con.execute(f'DELETE FROM {table}')
    rows=con.execute("""
        SELECT p.id,p.canonical_name,p.legal_name,p.ingredients,
               n.calories,n.protein_g,n.carbohydrate_g,n.fat_g,n.fiber_g
        FROM products p LEFT JOIN nutrition n ON n.product_id=p.id
    """).fetchall()
    for pid,name,legal,ingredients,kcal,protein,carbs,fat,fiber in rows:
        result=classify(ProductFeatures(name=name,legal_name=legal,ingredients=ingredients,calories=kcal,protein_g=protein,carbohydrate_g=carbs,fat_g=fat,fiber_g=fiber))
        store(con,pid,result)
        nutrition_ok=all(x is not None for x in (kcal,protein,carbs,fat))
        reason=None if nutrition_ok and result.classified else ('Falta nutrición comparable' if not nutrition_ok else 'Clasificación pendiente de revisión')
        con.execute("UPDATE eligibility SET classified=?,menu_eligible=?,reason=? WHERE product_id=?",(int(result.classified),int(nutrition_ok and result.classified),reason,pid))
    con.execute("INSERT OR REPLACE INTO catalog_metadata(key,value) VALUES('classifier_version',?)",(CLASSIFIER_VERSION,))
    con.commit()
    report={
        'products':len(rows),
        'classified':con.execute('SELECT count(*) FROM eligibility WHERE classified=1').fetchone()[0],
        'menu_eligible':con.execute('SELECT count(*) FROM eligibility WHERE menu_eligible=1').fetchone()[0],
        'nutritional_assignments':con.execute('SELECT count(*) FROM nutritional_role_assignments').fetchone()[0],
        'culinary_assignments':con.execute('SELECT count(*) FROM culinary_role_assignments').fetchone()[0],
        'review_open':con.execute("SELECT count(*) FROM review_queue WHERE status='OPEN'").fetchone()[0],
    }
    print(json.dumps(report,ensure_ascii=False,indent=2)); con.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('database',type=Path); run(p.parse_args().database)
