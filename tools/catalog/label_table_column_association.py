from __future__ import annotations

"""Geometry-only association of nutrition rows with an explicit per-100 column.

This module is diagnostic-only. It never parses or selects nutritional values and
must not be used as canonical nutrition evidence by itself. It exists to test
whether a clearly labelled ``100 g``/``100 ml`` column can be isolated from OCR
word geometry without using nutritional plausibility or post-hoc value selection.
"""

import re
import unicodedata

from label_table_geometry import BasisHeader, TsvToken, unique_basis_header

ASSOCIATION_VERSION = "1.0.0"
CORE_FIELDS = ("calories", "fat_g", "carbohydrate_g", "protein_g")
_DIGIT_RE = re.compile(r"\d")


def _ascii_compact(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^0-9a-z]+", "", without_marks)


def _visual_rows(tokens: list[TsvToken]) -> list[list[TsvToken]]:
    """Group words by observed y geometry, independent of OCR block IDs."""
    if not tokens:
        return []
    heights = sorted(max(1, token.height) for token in tokens)
    median_height = heights[len(heights) // 2]
    tolerance = max(4.0, median_height * 0.45)
    rows: list[list[TsvToken]] = []
    for token in sorted(tokens, key=lambda item: (item.center_y, item.left)):
        best_index = None
        best_distance = None
        for index, row in enumerate(rows):
            row_center = sum(item.center_y for item in row) / len(row)
            distance = abs(token.center_y - row_center)
            # Very tall OCR boxes can overlap several real rows. Center-only
            # clustering prevents one bad box from bridging a whole table.
            if distance <= tolerance:
                if best_distance is None or distance < best_distance:
                    best_index = index
                    best_distance = distance
        if best_index is None:
            rows.append([token])
        else:
            rows[best_index].append(token)
    normalized = [sorted(row, key=lambda item: (item.left, item.word_num)) for row in rows]
    return sorted(normalized, key=lambda row: (min(item.top for item in row), min(item.left for item in row)))


def _classify_label_text(label_text: str) -> str | None:
    compact = _ascii_compact(label_text)
    if compact in {
        "energia", "energetico", "energeticoenergia",
        "valorenergetico", "valorenergeticoenergia",
    }:
        return "calories"
    if compact in {"grasa", "grasas", "lipidos", "grasaslipidos", "grasalipidos"}:
        return "fat_g"
    if compact in {"hidratosdecarbono", "carbohidrato", "carbohidratos"}:
        return "carbohydrate_g"
    if compact in {"proteina", "proteinas", "protein", "proteins"}:
        return "protein_g"
    return None


def _field_before_cell(row: list[TsvToken], cell_left: int) -> tuple[str | None, str]:
    """Find the nearest explicit core-row label immediately left of a cell.

    Looking backwards from the candidate cell avoids unrelated ingredient text
    and numbers that may share the same visual y coordinate elsewhere on a label.
    Only short exact label phrases are accepted.
    """
    preceding = [token for token in row if token.right <= cell_left and not _DIGIT_RE.search(token.text)]
    if not preceding:
        return None, ""
    preceding = sorted(preceding, key=lambda token: (token.left, token.word_num))
    for length in range(1, min(5, len(preceding)) + 1):
        phrase_tokens = preceding[-length:]
        phrase = " ".join(token.text for token in phrase_tokens).strip()
        field = _classify_label_text(phrase)
        if field:
            return field, phrase
    return None, ""


def _numeric_cell_spans(row: list[TsvToken]) -> list[list[TsvToken]]:
    """Split numeric-bearing parts of a visual row into geometry-only cells."""
    try:
        start = next(index for index, token in enumerate(row) if _DIGIT_RE.search(token.text))
    except StopIteration:
        return []
    value_tokens = row[start:]
    if not value_tokens:
        return []
    heights = sorted(max(1, token.height) for token in value_tokens)
    median_height = heights[len(heights) // 2]
    max_gap = max(12, round(median_height * 1.5))
    groups: list[list[TsvToken]] = [[value_tokens[0]]]
    for token in value_tokens[1:]:
        previous = groups[-1][-1]
        if token.left - previous.right > max_gap:
            groups.append([token])
        else:
            groups[-1].append(token)

    cells: list[list[TsvToken]] = []
    for group in groups:
        try:
            first_numeric = next(index for index, token in enumerate(group) if _DIGIT_RE.search(token.text))
        except StopIteration:
            continue
        # A wide OCR line can contain ingredient text and a table cell at the
        # same y coordinate. Trim leading nonnumeric text from each candidate.
        cells.append(group[first_numeric:])
    return cells


def _cell_dict(group: list[TsvToken]) -> dict[str, object]:
    left = min(token.left for token in group)
    right = max(token.right for token in group)
    return {
        "text": " ".join(token.text for token in group),
        "left": left,
        "right": right,
        "top": min(token.top for token in group),
        "bottom": max(token.bottom for token in group),
        "center_x": (left + right) / 2.0,
        "numeric_token_count": sum(1 for token in group if _DIGIT_RE.search(token.text)),
    }


def _header_dict(header: BasisHeader) -> dict[str, object]:
    return {
        "basis": header.basis,
        "text": header.text,
        "left": header.left,
        "right": header.right,
        "top": header.top,
        "bottom": header.bottom,
        "center_x": header.center_x,
        "line_key": list(header.line_key),
    }


def associate_explicit_basis_column(tokens: list[TsvToken]) -> dict[str, object]:
    """Associate core row labels with observed text cells in one explicit column.

    Fail closed when the basis header is absent/ambiguous, a core row label is
    duplicated, more than one cell is geometrically plausible for the explicit
    column, or associated row centers drift enough to imply inconsistent columns.
    The returned cell text is raw OCR evidence, not a parsed nutrition value.
    """
    header_status, header = unique_basis_header(tokens)
    result: dict[str, object] = {
        "diagnostic_only": True,
        "nutrition_values_selected": False,
        "numeric_values_parsed": False,
        "selection_policy": "explicit_basis_header_and_geometry_only",
        "basis_header_status": header_status,
        "basis_header": _header_dict(header) if header else None,
        "status": header_status,
        "rows": {},
    }
    if header is None:
        return result

    header_width = max(1, header.right - header.left)
    token_heights = sorted(max(1, token.height) for token in tokens)
    median_height = token_heights[len(token_heights) // 2] if token_heights else 12
    column_half_width = max(24.0, header_width * 0.9, median_height * 2.5)
    result["column_half_width_px"] = column_half_width

    matches: dict[str, list[dict[str, object]]] = {field: [] for field in CORE_FIELDS}
    ambiguous_labeled_rows: list[dict[str, object]] = []
    ambiguous_fields: set[str] = set()
    for row in _visual_rows(tokens):
        if min(token.top for token in row) < header.bottom:
            continue
        all_cells = [_cell_dict(group) for group in _numeric_cell_spans(row)]
        plausible = [
            cell for cell in all_cells
            if abs(float(cell["center_x"]) - header.center_x) <= column_half_width
        ]
        labeled = []
        for cell in plausible:
            field, label_text = _field_before_cell(row, int(cell["left"]))
            if field:
                labeled.append((field, label_text, cell))
        if len(plausible) > 1 and labeled:
            ambiguous_fields.update(field for field, _, _ in labeled)
            ambiguous_labeled_rows.append({
                "fields": sorted({field for field, _, _ in labeled}),
                "labels": [label for _, label, _ in labeled],
                "candidate_cells": all_cells,
                "plausible_cells": plausible,
            })
            continue
        if len(plausible) == 1 and len(labeled) == 1:
            field, label_text, cell = labeled[0]
            matches[field].append({
                "label_text": label_text,
                "candidate_cells": all_cells,
                "associated_cell": cell,
            })

    rows: dict[str, object] = {}
    associated_centers: list[float] = []
    global_status: str | None = "AMBIGUOUS_NUMERIC_COLUMN" if ambiguous_labeled_rows else None
    for field in CORE_FIELDS:
        field_matches = matches[field]
        if field in ambiguous_fields:
            related = [row for row in ambiguous_labeled_rows if field in row.get("fields", [])]
            rows[field] = {
                "status": "AMBIGUOUS_EXPLICIT_COLUMN_CELL",
                "label_text": [label for row in related for label in row.get("labels", [])],
                "candidate_cells": [cell for row in related for cell in row.get("candidate_cells", [])],
                "plausible_cells": [cell for row in related for cell in row.get("plausible_cells", [])],
                "associated_cell": None,
            }
            continue
        if not field_matches:
            rows[field] = {
                "status": "MISSING_ROW_LABEL_OR_EXPLICIT_COLUMN_CELL",
                "label_text": None,
                "candidate_cells": [],
                "associated_cell": None,
            }
            continue
        if len(field_matches) != 1:
            rows[field] = {
                "status": "AMBIGUOUS_ROW_LABEL",
                "label_text": [match["label_text"] for match in field_matches],
                "candidate_cells": [],
                "associated_cell": None,
            }
            global_status = "AMBIGUOUS_ROW_LABEL"
            continue
        match = field_matches[0]
        rows[field] = {
            "status": "ASSOCIATED_CELL_DIAGNOSTIC",
            "label_text": match["label_text"],
            "candidate_cells": match["candidate_cells"],
            "associated_cell": match["associated_cell"],
        }
        associated_centers.append(float(match["associated_cell"]["center_x"]))

    if ambiguous_labeled_rows:
        result["ambiguous_labeled_rows"] = ambiguous_labeled_rows
    result["rows"] = rows
    if global_status:
        result["status"] = global_status
        return result

    if associated_centers:
        max_drift = max(30.0, header_width * 1.25, median_height * 3.0)
        drift = max(associated_centers) - min(associated_centers)
        result["max_associated_center_drift_px"] = drift
        result["allowed_center_drift_px"] = max_drift
        if drift > max_drift:
            result["status"] = "AMBIGUOUS_NUMERIC_COLUMN"
            return result

    associated_count = sum(
        1 for row in rows.values()
        if isinstance(row, dict) and row.get("status") == "ASSOCIATED_CELL_DIAGNOSTIC"
    )
    result["associated_core_field_count"] = associated_count
    if associated_count == len(CORE_FIELDS):
        result["status"] = "ASSOCIATED_CORE_ROWS_DIAGNOSTIC"
    else:
        result["status"] = "PARTIAL_CORE_ROWS_DIAGNOSTIC"
    return result
