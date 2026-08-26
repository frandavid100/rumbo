from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE = "CARREFOUR_FIRST_PARTY"

# Category-listing observations must not promote fields that require a product-detail page.
# Keep only fields that can be directly observed on an official Carrefour listing plus audit metadata.
LISTING_SAFE_FIELDS = {
    "retailer",
    "source",
    "capture_method",
    "capture_probe_version",
    "direct_listing_observed",
    "direct_page_observed",
    "listing_only_observed",
    "http_status",
    "page_sha256",
    "fetch_error",
    "observed_at",
    "retrieval_freshness",
    "provenance_note",
    "discovery_source",
    "retailer_sku",
    "canonical_url",
    "name",
    "brand",
    "image_url",
    "category_path",
    "price_eur",
    "price_currency",
    "unit_price_text",
    "availability",
    "nutrition_status",
}


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            return []
        if not isinstance(row, dict):
            return []
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def official_url(value: object) -> bool:
    url = str(value or "")
    return url.startswith("https://www.carrefour.es/") or url.startswith("https://carrefour.es/")


def row_kind(row: dict) -> str | None:
    if row.get("retailer") != "CARREFOUR" or row.get("source") != SOURCE:
        return None
    if not row.get("retailer_sku") or not official_url(row.get("canonical_url")):
        return None
    if row.get("direct_page_observed") is True and row.get("listing_only_observed") is not True:
        return "direct"
    if (
        row.get("direct_page_observed") is False
        and str(row.get("capture_method") or "").startswith("OPENAI_WEB_OFFICIAL_CATEGORY")
    ):
        return "listing"
    return None


def sanitize_listing_row(row: dict) -> tuple[dict, list[str]]:
    sanitized = {key: value for key, value in row.items() if key in LISTING_SAFE_FIELDS}
    sanitized["retailer"] = "CARREFOUR"
    sanitized["source"] = SOURCE
    sanitized["direct_page_observed"] = False
    sanitized["listing_only_observed"] = True
    # A listing can establish that nutrition was not observed there, but never declaration values.
    if sanitized.get("nutrition_status") not in (None, "", "NOT_OBSERVED_ON_LISTING", "NOT_FETCHED"):
        sanitized["nutrition_status"] = "NOT_OBSERVED_ON_LISTING"
    removed = sorted(
        key for key, value in row.items()
        if key not in LISTING_SAFE_FIELDS and value not in (None, "", [], {})
    )
    return sanitized, removed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", default="fixtures")
    ap.add_argument("--fresh", default="carrefour-first-party-fresh-inventory")
    ap.add_argument("--frontier", default="carrefour-first-party-category-frontier")
    ap.add_argument("--sqlite", default="carrefour-first-party-cumulative/carrefour_first_party.sqlite")
    ap.add_argument("--work", default="carrefour-first-party-cumulative-merge-input")
    args = ap.parse_args()

    fixtures = Path(args.fixtures)
    work = Path(args.work)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    for name in (
        "carrefour_first_party_products_cumulative.jsonl",
        "carrefour_first_party_field_evidence_cumulative.jsonl",
        "carrefour_first_party_cumulative_summary.json",
    ):
        src = fixtures / name
        if src.exists():
            shutil.copy2(src, work / name)

    accepted: list[str] = []
    skipped: list[str] = []
    accepted_rows = 0
    direct_rows = 0
    listing_rows = 0
    sanitized_listing_rows = 0
    removed_listing_fields: dict[str, int] = {}

    for src in sorted(fixtures.glob("carrefour_first_party_agent_web_products_*.jsonl")):
        rows = read_jsonl(src)
        if not rows:
            skipped.append(src.name)
            continue

        normalized: list[dict] = []
        valid = True
        for row in rows:
            kind = row_kind(row)
            if kind is None:
                valid = False
                break
            if kind == "direct":
                normalized.append(dict(row))
                direct_rows += 1
                continue

            clean, removed = sanitize_listing_row(row)
            normalized.append(clean)
            listing_rows += 1
            if removed:
                sanitized_listing_rows += 1
                for field in removed:
                    removed_listing_fields[field] = removed_listing_fields.get(field, 0) + 1

        if not valid:
            skipped.append(src.name)
            continue

        # Always write the normalized copy into the temporary merge input. The archived fixture
        # remains untouched, while listing-only rows cannot leak PDP-only declarations.
        write_jsonl(work / src.name, normalized)
        accepted.append(src.name)
        accepted_rows += len(normalized)

    cmd = [
        sys.executable,
        str(Path(__file__).with_name("merge_carrefour_first_party_cumulative.py")),
        "--fixtures", str(work),
        "--fresh", args.fresh,
        "--frontier", args.frontier,
        "--sqlite", args.sqlite,
    ]
    subprocess.run(cmd, check=True)

    summary_path = work / "carrefour_first_party_cumulative_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["manual_fixture_selection"] = {
        "policy": "ONLY_EXPLICIT_DIRECT_PDP_OR_SANITIZED_OFFICIAL_CATEGORY_OBSERVATIONS",
        "accepted_files": accepted,
        "accepted_rows": accepted_rows,
        "direct_rows": direct_rows,
        "listing_rows": listing_rows,
        "sanitized_listing_rows": sanitized_listing_rows,
        "removed_listing_fields": dict(sorted(removed_listing_fields.items())),
        "skipped_unverified_legacy_files": skipped,
        "skipped_count": len(skipped),
        "note": (
            "Archived fixtures remain unchanged. Direct PDP observations retain their observed fields; "
            "official category-listing rows are reduced to listing-observable identity/commerce fields "
            "before cumulative merge so no PDP-only declaration can be promoted from a listing."
        ),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    for name in (
        "carrefour_first_party_products_cumulative.jsonl",
        "carrefour_first_party_field_evidence_cumulative.jsonl",
        "carrefour_first_party_cumulative_summary.json",
    ):
        shutil.copy2(work / name, fixtures / name)

    print(json.dumps(summary["manual_fixture_selection"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
