from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

VALID = {"DECLARED", "REVIEW", "NO_VISUAL_REGION", "ERROR"}
EVIDENCE = "OCR_DERIVED_FROM_MERCADONA_IMAGE"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    strict: set[str] = set()
    any_status: set[str] = set()
    ocr_shaped: set[str] = set()
    evidence_rows: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    non_strict_paths: dict[str, set[str]] = defaultdict(set)
    samples: dict[str, dict] = {}

    for path in sorted(Path(args.root).rglob("*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            product_id = str(row.get("product_id") or "")
            status = str(row.get("status") or "")
            if not product_id or status not in VALID:
                continue
            any_status.add(product_id)
            evidence = row.get("evidence_level")
            evidence_key = "<MISSING>" if evidence is None else str(evidence)
            evidence_rows[evidence_key] += 1
            kinds[str(row.get("source_record_kind") or "<MISSING>")] += 1
            if isinstance(row.get("attempts"), list) or row.get("image_url") or row.get("perspective") is not None:
                ocr_shaped.add(product_id)
            if evidence == EVIDENCE:
                strict.add(product_id)
            else:
                non_strict_paths[product_id].add(str(path))
                samples.setdefault(product_id, {
                    "product_id": product_id,
                    "status": status,
                    "evidence_level": evidence,
                    "source": row.get("source"),
                    "source_record_kind": row.get("source_record_kind"),
                    "perspective": row.get("perspective"),
                    "image_url_present": bool(row.get("image_url")),
                    "attempts_present": isinstance(row.get("attempts"), list),
                    "path": str(path),
                })

    non_strict = sorted(any_status - strict)
    result = {
        "strict_ids": len(strict),
        "valid_status_ids_any_evidence": len(any_status),
        "ocr_shaped_valid_status_ids_any_evidence": len(ocr_shaped),
        "non_strict_valid_status_ids": len(non_strict),
        "non_strict_ocr_shaped_ids": len((any_status - strict) & ocr_shaped),
        "evidence_values_by_row": dict(sorted(evidence_rows.items())),
        "source_record_kinds_by_row": dict(sorted(kinds.items())),
        "non_strict_product_ids": non_strict,
        "non_strict_samples": [samples[x] for x in non_strict[:100] if x in samples],
        "non_strict_paths": {x: sorted(non_strict_paths[x]) for x in non_strict[:200]},
        "policy": "Diagnostic only; no row lacking the exact OCR evidence marker is promoted into the strict union.",
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
