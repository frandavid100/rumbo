from __future__ import annotations

import json
from pathlib import Path
import tempfile

from label_text_extractor import extract_with_tesseract
from mercadona_label_evidence import nutrition_image_candidates
from mercadona_label_pipeline import download_label_image, process_label_file_ensemble
from mercadona_product_adapter import fetch_product
from nutrition_visual_table_detector import detect_visual_table_regions

PRODUCTS = [
    ("23049", "Batido de chocolate Hacendado"),
    ("3363", "Zumo de naranja recién exprimido Hacendado"),
    ("60127", "Media tortilla de patata con cebolla Listo para Comer"),
    ("14325", "Galletas tostadas Hacendado"),
    ("18018", "Atún claro al natural Hacendado"),
]


def extractor(psm):
    return lambda path: extract_with_tesseract(path, language="spa", psm=psm)


def main():
    strategies=(("psm6",extractor(6)),("psm11",extractor(11)))
    report={"products":len(PRODUCTS),"api_fetched":0,"baseline_declared":0,
            "visual_declared":0,"visual_candidates":0,"items":[]}
    with tempfile.TemporaryDirectory(prefix="rumbo-visual-probe-") as td:
        root=Path(td)
        for sku,expected in PRODUCTS:
            item={"sku":sku,"expected":expected,"status":"UNRESOLVED","visual_regions":[]}
            try:
                product=fetch_product(sku,timeout=8.0)
                report["api_fetched"]+=1
                item["name"]=product.name; item["ean"]=product.ean
                backs=[x for x in nutrition_image_candidates(product.label_images) if x.perspective==9]
                if not backs:
                    item["reason"]="NO_BACK_IMAGE"; report["items"].append(item); continue
                evidence=backs[0]
                source=root/f"{sku}.jpg"
                download_label_image(evidence.image_url,source,timeout=8.0)
                baseline=process_label_file_ensemble(evidence,source,gtin=product.ean,brand=product.brand,strategies=strategies)
                item["baseline"]={"status":baseline.status,"nutrition":baseline.candidate.nutrition if baseline.candidate else
                    (baseline.ensemble.nutrition if baseline.ensemble else None)}
                if baseline.status=="DECLARED":
                    item["status"]="BASELINE_DECLARED"; report["baseline_declared"]+=1
                    report["items"].append(item); continue
                regions=detect_visual_table_regions(source,root/f"regions-{sku}")
                report["visual_candidates"]+=len(regions)
                for region in regions:
                    result=process_label_file_ensemble(evidence,region.path,gtin=product.ean,brand=product.brand,strategies=strategies)
                    meta={"box":list(region.box),"score":region.score,"horizontal_lines":region.horizontal_lines,
                          "vertical_lines":region.vertical_lines,"status":result.status,
                          "nutrition":result.candidate.nutrition if result.candidate else
                            (result.ensemble.nutrition if result.ensemble else None)}
                    item["visual_regions"].append(meta)
                    if result.status=="DECLARED" and result.candidate is not None:
                        item["status"]="VISUAL_DECLARED"; item["nutrition"]=result.candidate.nutrition
                        report["visual_declared"]+=1; break
                if item["status"]=="UNRESOLVED" and item["visual_regions"]:
                    item["status"]="VISUAL_REVIEW"
            except Exception as exc:
                item["error"]=f"{type(exc).__name__}:{exc}"
            report["items"].append(item)
    Path("live-visual-detector-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2)); return 0


if __name__=="__main__": raise SystemExit(main())
