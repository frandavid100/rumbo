#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.catalog.bedca import BedcaClient, write_manifest
from tools.catalog.classify import classify
from tools.catalog.sqlite_catalog import create


def identity_key(record: dict) -> str:
    """Stable generic-food identity: the visible BEDCA denomination, normalized."""
    name = unicodedata.normalize("NFKC", record["index"].name_es)
    return " ".join(name.casefold().split())


def record_score(record: dict) -> tuple[int, int, int, int]:
    nutrition = record["nutrition"]
    core = sum(nutrition.get(field) is not None for field in
               ("calories", "protein_g", "carbohydrate_g", "fat_g", "fiber_g", "sodium_g"))
    concrete_components = sum(
        component.get("best_location") not in (None, "")
        for component in record["detail"]["components"]
    )
    # Prefer measured energy over a value derived from macronutrients. The final
    # tie-breaker is deliberately stable and independent of download order.
    return (int(not nutrition.get("calories_derived", False)), core,
            concrete_components, -int(record["index"].id))


def deduplicate(records: list[dict]) -> tuple[list[dict], list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(identity_key(record), []).append(record)
    selected: list[dict] = []
    merged: list[dict] = []
    for key, candidates in grouped.items():
        winner = max(candidates, key=record_score)
        stable_source_id = min((item["index"].id for item in candidates), key=int)
        winner["stable_source_id"] = stable_source_id
        winner["source_records"] = [
            {
                "source_food_id": item["index"].id,
                "source_origin": item["index"].origin,
                "raw_sha256": item["detail"]["raw_sha256"],
                "selected": item is winner,
            }
            for item in sorted(candidates, key=lambda item: int(item["index"].id))
        ]
        selected.append(winner)
        if len(candidates) > 1:
            merged.append({
                "identity": key,
                "name": winner["index"].name_es,
                "canonical_source_food_id": winner["index"].id,
                "stable_product_id": f"bedca:{stable_source_id}",
                "merged_source_food_ids": [item["index"].id for item in candidates],
            })
    selected.sort(key=lambda record: int(record["stable_source_id"]))
    merged.sort(key=lambda item: item["identity"])
    return selected, merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Rumbo's development BEDCA catalogue")
    parser.add_argument("--cache", type=Path, default=Path("build/catalog/bedca/raw"))
    parser.add_argument("--output", type=Path,
                        default=Path("build/catalog/bedca/rumbo-bedca-development.rumbocatalog"))
    parser.add_argument("--report", type=Path, default=Path("build/catalog/bedca/report.json"))
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, help="development-only record limit")
    return parser.parse_args()


def component_map(detail: dict) -> dict[str, list[dict]]:
    mapped: dict[str, list[dict]] = {}
    for component in detail["components"]:
        key = (component.get("eur_name") or "").upper()
        if key:
            mapped.setdefault(key, []).append(component)
    return mapped


def value(components: dict[str, list[dict]], *codes: str, unit: str | None = None) -> float | None:
    candidates: list[dict] = []
    for code in codes:
        candidates += components.get(code, [])
    if unit:
        candidates = [item for item in candidates if (item.get("v_unit") or "").lower() == unit.lower()]
    concrete = [item for item in candidates if item.get("best_location") not in (None, "")]
    if not concrete:
        return None
    values = {float(item["best_location"]) for item in concrete}
    if len(values) != 1:
        raise ValueError(f"conflicting BEDCA component values for {codes}: {values}")
    return values.pop()


def normalize(detail: dict) -> dict[str, float | None]:
    components = component_map(detail)
    energy_kj = value(components, "ENERC", unit="kJ")
    energy_kcal = value(components, "ENERC", unit="kcal")
    calories = energy_kcal if energy_kcal is not None else (energy_kj / 4.184 if energy_kj is not None else None)
    sodium_mg = value(components, "NA", unit="mg")
    sodium_g = sodium_mg / 1000.0 if sodium_mg is not None else value(components, "NA", unit="g")
    result = {
        "calories": calories,
        "protein_g": value(components, "PROT", unit="g"),
        "carbohydrate_g": value(components, "CHO", "CHOCDF", "CHOAVL", unit="g"),
        "fat_g": value(components, "FAT", unit="g"),
        "fiber_g": value(components, "FIBT", "FIBTG", unit="g"),
        "sodium_g": sodium_g,
        "salt_g": sodium_g * 2.5 if sodium_g is not None else None,
    }
    if result["calories"] is None and all(result[field] is not None for field in
                                            ("protein_g", "carbohydrate_g", "fat_g")):
        result["calories"] = (4 * result["protein_g"] + 4 * result["carbohydrate_g"] +
                              9 * result["fat_g"] + 2 * (result["fiber_g"] or 0.0))
        result["calories_derived"] = True
    else:
        result["calories_derived"] = False
    validate_nutrition(result)
    return result


def validate_nutrition(nutrition: dict[str, float | None]) -> None:
    limits = {"calories": 1000.0, "protein_g": 100.0, "carbohydrate_g": 100.0,
              "fat_g": 100.0, "fiber_g": 100.0, "sodium_g": 50.0, "salt_g": 125.0}
    for field, maximum in limits.items():
        value_ = nutrition[field]
        if value_ is not None and not (0 <= value_ <= maximum):
            raise ValueError(f"implausible {field}: {value_}")


def main() -> int:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    client = BedcaClient(args.cache, delay_seconds=args.delay)
    groups = client.groups()
    group_names = {group.id: group.name_es for group in groups}
    foods = client.index(groups)
    if args.limit:
        foods = foods[:args.limit]
    write_manifest(args.output.parent / "manifest.json", groups, foods)

    records: list[dict] = []
    failures: list[dict] = []

    def process(item):
        detail = client.detail(item.id)
        nutrition = normalize(detail)
        classification = classify(item.name_es, item.group_id, nutrition)
        return {"index": item, "detail": detail, "nutrition": nutrition,
                "classification": classification, "group_name": group_names[item.group_id]}

    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(process, item): item for item in foods}
        for future in as_completed(futures):
            item = futures[future]
            completed += 1
            try:
                records.append(future.result())
            except Exception as error:
                failures.append({"food_id": item.id, "name": item.name_es,
                                 "error": f"{type(error).__name__}: {error}"})
            if completed % 50 == 0:
                print(f"BEDCA {completed}/{len(foods)}", flush=True)

    records.sort(key=lambda record: int(record["index"].id))
    extracted_count = len(records)
    records, merged = deduplicate(records)

    create(args.output, records)
    statuses = Counter(record["classification"].status for record in records)
    groups_count = Counter(record["index"].group_id for record in records)
    roles = Counter(role for record in records for role in
                    record["classification"].nutritional_roles + record["classification"].culinary_roles)
    report = {
        "source": "BEDCA", "purpose": "Rumbo internal development",
        "redistribution_status": "unresolved; do not publish",
        "indexed": len(foods), "normalized": extracted_count, "written": len(records),
        "duplicates_merged": extracted_count - len(records),
        "duplicate_groups": len(merged), "merged_records": merged,
        "failures": failures,
        "statuses": dict(sorted(statuses.items())), "groups": dict(sorted(groups_count.items())),
        "roles": dict(sorted(roles.items())), "output_bytes": args.output.stat().st_size,
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
