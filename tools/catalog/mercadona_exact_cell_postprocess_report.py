from __future__ import annotations

from label_table_exact_diagnostic import parse_associated_exact_cells


def postprocess_report(report: dict[str, object]) -> dict[str, object]:
    attempts = []
    exact_total = 0
    for attempt in report.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        association = attempt.get("association")
        if isinstance(association, dict):
            exact = parse_associated_exact_cells(association)
        else:
            exact = {"diagnostic_only": True, "status": "BLOCKED_BY_ASSOCIATION", "exact_cells": {}, "exact_value_count": 0}
        exact_total += int(exact.get("exact_value_count") or 0)
        attempts.append({"variant": attempt.get("variant"), "psm": attempt.get("psm"), "exact_cell_postprocess": exact})
    return {
        "diagnostic_only": True,
        "canonical_reconciliation_allowed": False,
        "nutrition_usable": False,
        "missing_values_inferred": False,
        "product_id": report.get("product_id"),
        "ean": report.get("ean"),
        "exact_value_observations": exact_total,
        "attempts": attempts,
        "CLASSIFIED": 0,
        "MENU_ELIGIBLE": 0,
    }
