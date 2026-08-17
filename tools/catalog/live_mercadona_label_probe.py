from __future__ import annotations

import json
from pathlib import Path
import tempfile

from label_text_extractor import extract_with_tesseract
from mercadona_label_evidence import nutrition_image_candidates
from mercadona_label_pipeline import download_label_image, process_label_file_ensemble
from mercadona_product_adapter import fetch_product
from nutrition_table_region_detector import detect_nutrition_regions
from nutrition_visual_table_detector import detect_visual_table_regions

PRODUCTS = [
    ("14325", "Galletas tostadas Hacendado"),
    ("23773", "Chocolate negro 72% de cacao Hacendado"),
    ("23049", "Batido de chocolate Hacendado"),
    ("21713", "Refresco cola Hacendado"),
    ("3363", "Zumo de naranja recién exprimido Hacendado"),
    ("80862", "Hummus de garbanzos Hacendado con pimiento del piquillo asado"),
    ("13985", "Masa fresca pizza Hacendado"),
    ("22549", "Pizza Calzone con jamón cocido y queso Hacendado"),
    ("60127", "Media tortilla de patata con cebolla Listo para Comer"),
    ("18018", "Atún claro al natural Hacendado"),
    ("88407", "Lentejas Listo para Comer"),
    ("26108", "Fabada Hacendado"),
    ("23138", "Albóndigas en salsa Hacendado"),
]


def extractor_for(psm: int):
    return lambda path: extract_with_tesseract(path, language="spa", psm=psm)


def result_payload(result, *, image_index, perspective, variant, detector=None, region=None):
    return {
        "image_index": image_index, "perspective": perspective, "variant": variant,
        "detector": detector, "region": region, "status": result.status, "reason": result.reason,
        "readings": [{"strategy": strategy, "status": reading.parsed.status,
                      "confidence": reading.extraction.confidence, "basis": reading.parsed.basis,
                      "nutrition": reading.parsed.nutrition, "reasons": list(reading.parsed.reasons)}
                     for strategy, reading in result.readings],
        "ensemble": None if result.ensemble is None else {
            "status": result.ensemble.status, "confidence": result.ensemble.confidence,
            "basis": result.ensemble.basis, "nutrition": result.ensemble.nutrition,
            "corroborated_fields": result.ensemble.corroborated_fields,
            "reasons": list(result.ensemble.reasons),
        },
    }


def main() -> int:
    report = {"products_requested":len(PRODUCTS),"api_fetched":0,"with_photos":0,
              "declared":0,"declared_direct":0,"declared_ensemble":0,
              "declared_visual":0,"declared_ocr_region":0,"review_only":0,"unreadable":0,
              "visual_candidates":0,"ocr_region_candidates":0,"items":[]}
    snapshot_dir=Path("live-mercadona-snapshots"); snapshot_dir.mkdir(exist_ok=True)
    strategies=(("psm6",extractor_for(6)),("psm11",extractor_for(11)))

    for product_id, expected_name in PRODUCTS:
        item={"product_id":product_id,"expected_name":expected_name,"api_status":"ERROR",
              "ean":None,"name":None,"photo_count":0,"status":"UNREADABLE","declared":None,
              "attempts":[],"visual_regions":[],"ocr_regions":[]}
        try:
            product=fetch_product(product_id,snapshot_dir=snapshot_dir,timeout=8.0)
            report["api_fetched"]+=1
            item.update(api_status="OK",ean=product.ean,name=product.name,photo_count=len(product.label_images))
            if product.label_images: report["with_photos"]+=1
            best_review=None
            with tempfile.TemporaryDirectory(prefix="rumbo-live-label-") as td:
                for evidence in nutrition_image_candidates(product.label_images):
                    path=Path(td)/f"{product_id}-{evidence.image_index}.jpg"
                    try:
                        download_label_image(evidence.image_url,path,timeout=8.0)
                    except Exception as exc:
                        item["attempts"].append({"variant":"original","status":"DOWNLOAD_ERROR",
                            "reason":f"{type(exc).__name__}:{exc}"}); continue

                    direct=process_label_file_ensemble(evidence,path,gtin=product.ean,brand=product.brand,strategies=strategies)
                    attempt=result_payload(direct,image_index=evidence.image_index,perspective=evidence.perspective,variant="original")
                    item["attempts"].append(attempt)
                    if direct.status=="DECLARED" and direct.candidate is not None:
                        via="ensemble" if direct.ensemble is not None else "direct"
                        item["status"]="DECLARED"; item["declared"]={"via":via,"nutrition":direct.candidate.nutrition,
                            "image_index":evidence.image_index,"perspective":evidence.perspective}
                        report["declared"]+=1; report[f"declared_{via}"]+=1; break
                    if direct.ensemble is not None and direct.ensemble.nutrition:
                        best_review=(direct.ensemble.confidence,attempt,direct.ensemble.nutrition)
                    if evidence.perspective != 9:
                        continue

                    # First fallback: pure image structure. No OCR words are used to select regions.
                    vdir=Path(td)/f"visual-{product_id}-{evidence.image_index}"
                    try:
                        visual_regions=detect_visual_table_regions(path,vdir)
                    except Exception as exc:
                        visual_regions=[]; item["visual_regions"].append({"error":f"{type(exc).__name__}:{exc}"})
                    report["visual_candidates"]+=len(visual_regions)
                    for region in visual_regions:
                        meta={"name":region.name,"box":list(region.box),"score":region.score,
                              "horizontal_lines":region.horizontal_lines,"vertical_lines":region.vertical_lines,
                              "line_density":region.line_density}
                        item["visual_regions"].append(meta)
                        result=process_label_file_ensemble(evidence,region.path,gtin=product.ean,brand=product.brand,strategies=strategies)
                        attempt=result_payload(result,image_index=evidence.image_index,perspective=evidence.perspective,
                                               variant=region.name,detector="visual",region=meta)
                        item["attempts"].append(attempt)
                        if result.status=="DECLARED" and result.candidate is not None:
                            item["status"]="DECLARED"; item["declared"]={"via":"visual","nutrition":result.candidate.nutrition,
                                "image_index":evidence.image_index,"perspective":evidence.perspective,"region":meta}
                            report["declared"]+=1; report["declared_visual"]+=1; break
                        if result.ensemble is not None and result.ensemble.nutrition:
                            score=result.ensemble.confidence
                            if best_review is None or score>best_review[0]: best_review=(score,attempt,result.ensemble.nutrition)
                    if item["status"]=="DECLARED": break

                    # Second fallback kept for comparison/backward coverage: OCR-marker detector.
                    odir=Path(td)/f"ocr-regions-{product_id}-{evidence.image_index}"
                    try:
                        ocr_regions=detect_nutrition_regions(path,odir)
                    except Exception as exc:
                        ocr_regions=[]; item["ocr_regions"].append({"error":f"{type(exc).__name__}:{exc}"})
                    report["ocr_region_candidates"]+=len(ocr_regions)
                    for region in ocr_regions:
                        meta={"name":region.name,"box":list(region.box),"marker_kinds":list(region.marker_kinds),
                              "marker_count":region.marker_count,"confidence":region.confidence}
                        item["ocr_regions"].append(meta)
                        result=process_label_file_ensemble(evidence,region.path,gtin=product.ean,brand=product.brand,strategies=strategies)
                        attempt=result_payload(result,image_index=evidence.image_index,perspective=evidence.perspective,
                                               variant=region.name,detector="ocr_marker",region=meta)
                        item["attempts"].append(attempt)
                        if result.status=="DECLARED" and result.candidate is not None:
                            item["status"]="DECLARED"; item["declared"]={"via":"ocr_region","nutrition":result.candidate.nutrition,
                                "image_index":evidence.image_index,"perspective":evidence.perspective,"region":meta}
                            report["declared"]+=1; report["declared_ocr_region"]+=1; break
                        if result.ensemble is not None and result.ensemble.nutrition:
                            score=result.ensemble.confidence
                            if best_review is None or score>best_review[0]: best_review=(score,attempt,result.ensemble.nutrition)
                    if item["status"]=="DECLARED": break

            if item["status"]!="DECLARED":
                if best_review is not None:
                    item["status"]="REVIEW"; item["best_review"]={"confidence":best_review[0],
                        "attempt":best_review[1],"nutrition":best_review[2]}; report["review_only"]+=1
                else: report["unreadable"]+=1
        except Exception as exc:
            item["error"]=f"{type(exc).__name__}:{exc}"; report["unreadable"]+=1
        report["items"].append(item)

    report["declared_rate"]=round(report["declared"]/len(PRODUCTS),3)
    Path("live-mercadona-label-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2)); return 0


if __name__=="__main__": raise SystemExit(main())
