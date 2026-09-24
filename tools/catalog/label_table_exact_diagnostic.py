from __future__ import annotations

from label_table_exact_cell_parser import CORE_FIELDS, EXACT_CELL_PARSER_VERSION, parse_exact_nutrition_cell

EXACT_DIAGNOSTIC_VERSION = "1.0.0"
_BLOCKED = {
    "AMBIGUOUS_EXPLICIT_100_BASIS_HEADER",
    "AMBIGUOUS_NUMERIC_COLUMN",
    "AMBIGUOUS_ROW_LABEL",
    "MISSING_EXPLICIT_100_BASIS_HEADER",
}


def parse_associated_exact_cells(association: dict[str, object]) -> dict[str, object]:
    status = str(association.get("status") or "")
    result = {
        "diagnostic_only": True,
        "canonical_reconciliation_allowed": False,
        "nutrition_usable": False,
        "missing_values_inferred": False,
        "exact_diagnostic_version": EXACT_DIAGNOSTIC_VERSION,
        "exact_cell_parser_version": EXACT_CELL_PARSER_VERSION,
        "association_status": status,
        "status": "NO_EXACT_CELLS",
        "exact_cells": {},
        "exact_value_count": 0,
    }
    if status in _BLOCKED or association.get("basis_header_status") != "UNIQUE_EXPLICIT_100_BASIS_HEADER":
        result["status"] = "BLOCKED_BY_ASSOCIATION"
        return result
    rows = association.get("rows")
    if not isinstance(rows, dict):
        result["status"] = "BLOCKED_BY_ASSOCIATION"
        return result
    exact_cells = {}
    exact_count = 0
    for field in CORE_FIELDS:
        row = rows.get(field)
        if not isinstance(row, dict) or row.get("status") != "ASSOCIATED_CELL_DIAGNOSTIC":
            continue
        cell = row.get("associated_cell")
        if not isinstance(cell, dict):
            continue
        raw = str(cell.get("text") or "")
        parsed = parse_exact_nutrition_cell(field, raw)
        exact_cells[field] = {
            "raw_cell_text": raw,
            "row_label_text": row.get("label_text"),
            "cell_center_x": cell.get("center_x"),
            "parse": parsed,
        }
        if parsed.get("status") == "EXACT_VALUE":
            exact_count += 1
    result["exact_cells"] = exact_cells
    result["exact_value_count"] = exact_count
    if exact_cells:
        result["status"] = "DIAGNOSTIC_EXACT_CELLS"
    return result
