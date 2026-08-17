#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from classifier import ProductFeatures, classify, classify_type, CLASSIFIER_VERSION

ROOT = Path(__file__).resolve().parent
PROBE = ROOT / "fixtures" / "mercadona_full_classification_probe.json"


def main() -> int:
    items = json.loads(PROBE.read_text(encoding="utf-8"))
    type_errors = []
    role_errors = []
    full_reviews = []
    missing_nutrition = []
    types = Counter()
    roles = Counter()
    resolved = 0
    fully_classified = 0

    for item in items:
        nutrition = item.get("nutrition")
        features = ProductFeatures(
            name=item["name"],
            calories=nutrition.get("calories") if nutrition else None,
            protein_g=nutrition.get("protein_g") if nutrition else None,
            carbohydrate_g=nutrition.get("carbohydrate_g") if nutrition else None,
            fat_g=nutrition.get("fat_g") if nutrition else None,
        )
        type_assignment = classify_type(features)
        actual_type = type_assignment.value if type_assignment else None
        if actual_type != item["expected_type"]:
            type_errors.append({"name": item["name"], "expected": item["expected_type"], "actual": actual_type})
        if actual_type:
            types[actual_type] += 1

        if item["nutrition_status"] != "RESOLVED":
            missing_nutrition.append(item["name"])
            continue

        resolved += 1
        result = classify(features)
        actual_roles = {a.value for a in result.nutritional_roles}
        expected_roles = set(item.get("expected_roles", []))
        if actual_roles != expected_roles:
            role_errors.append({
                "name": item["name"],
                "expected": sorted(expected_roles),
                "actual": sorted(actual_roles),
                "type": actual_type,
            })
        for role in actual_roles:
            roles[role] += 1
        if result.classified:
            fully_classified += 1
        else:
            full_reviews.append({"name": item["name"], "reasons": result.review_reasons})

    report = {
        "classifier_version": CLASSIFIER_VERSION,
        "products": len(items),
        "nutrition_resolved": resolved,
        "nutrition_missing": len(missing_nutrition),
        "type_correct": len(items) - len(type_errors),
        "fully_classified_resolved": fully_classified,
        "type_errors": type_errors,
        "role_errors": role_errors,
        "reviews_on_resolved": full_reviews,
        "missing_nutrition_products": missing_nutrition,
        "types": dict(sorted(types.items())),
        "nutritional_roles": dict(sorted(roles.items())),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if type_errors or role_errors or full_reviews else 0


if __name__ == "__main__":
    raise SystemExit(main())
