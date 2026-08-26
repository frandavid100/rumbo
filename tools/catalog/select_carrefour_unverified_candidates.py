#!/usr/bin/env python3
"""Build a discovery-only queue of Carrefour candidate URLs not yet directly verified.

The candidate input may come from external discovery sources such as RadarSuper. This
script NEVER promotes those hints to Carrefour first-party evidence. It only removes
product IDs already present in one or more verified first-party JSONL inputs, excludes
candidate IDs whose official Carrefour route has a persisted terminal outcome, and emits
a bounded, deterministic work queue plus counts for auditing.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


SKU_IN_URL_RE = re.compile(r"/R-([^/]+)/p(?:$|[?#])", re.IGNORECASE)

# This queue exists to drive Rumbo's food-catalog verification. Keep every external
# candidate in the audit counts, but put obvious human-food candidates ahead of alcohol,
# pet products and other non-food supermarket items. This is scheduling metadata only:
# it never creates or suppresses Carrefour evidence.
FOOD_URL_SIGNAL_RE = re.compile(
    r"/(?:"
    r"aceite|aceituna|agua-mineral|arroz|avena|azucar|barrita|bebida-vegetal|"
    r"bizcocho|bolleria|caldo|cafe|cacao|cereales?|chocolate|conserva|crema-de-|"
    r"embutido|fiambre|galleta|garbanzo|harina|helado|huevo|infusion|judia|"
    r"leche|lenteja|mantequilla|mermelada|pan-|pasta-|patata|pescado|pizza|"
    r"postre|queso|salsa|sopa|te-|tofu|tortilla|yogur|zumo"
    r")",
    re.IGNORECASE,
)
DEPRIORITIZED_URL_SIGNAL_RE = re.compile(
    r"/(?:"
    # Alcohol.
    r"whisky|ron-|vodka|ginebra|licor|vermut|cerveza|vino-|cava-|champagne|"
    # Personal care / cosmetics. Keep these before generic food signals such as leche.
    r"agua-de-colonia|perfume|desodorante|crema-hidratante|crema-corporal|"
    r"crema-facial|crema-de-manos|leche-corporal|champu|gel-de-ducha|"
    # Household / hygiene.
    r"ambientador|lavavajillas|detergente|limpiador|lejia|plumero|atrapapolvo|"
    r"papel-higienico|panal|compresa|tampon|dentifrico|cepillo-de-dientes|"
    # Pet food and animal-care products. These can contain strong human-food tokens
    # (galletas, barritas, leche, etc.) and therefore must be checked first.
    r"pienso|comida-para-perro|comida-para-gato|alimento-para-perro|"
    r"alimento-para-gato|galletas-para-perro|galletas-para-gato|"
    r"galletas-para-roedores|barritas?.*para-canarios|para-perros?(?:-|/)|"
    r"para-gatos?(?:-|/)|para-roedores?(?:-|/)|para-canarios?(?:-|/)|"
    r"arena-para-gato|mascotas?"
    r")",
    re.IGNORECASE,
)


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if isinstance(value, dict):
            rows.append(value)
    return rows


def norm_sku(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def candidate_sku(row: dict[str, Any]) -> tuple[str | None, str]:
    # The RadarSuper export's retailer_sku_candidate may be an external slug, while the
    # canonical Carrefour URL embeds Carrefour's real R- product identifier. Prefer the
    # official-looking URL identifier as a discovery hint; it still becomes evidence only
    # after direct observation on Carrefour.
    url = str(row.get("canonical_url") or row.get("url") or "").strip()
    match = SKU_IN_URL_RE.search(url)
    if match:
        return norm_sku(match.group(1)), "CARREFOUR_URL_CANDIDATE"
    for key in ("retailer_sku", "sku", "product_id", "retailer_sku_candidate"):
        sku = norm_sku(row.get(key))
        if sku:
            return sku, f"FIELD_{key.upper()}_CANDIDATE"
    return None, "MISSING"


def candidate_food_priority(row: dict[str, Any]) -> int:
    """Return queue priority without treating an external URL slug as product evidence.

    0 = URL looks like human food and is useful for Rumbo first.
    1 = uncertain/general supermarket candidate; keep it in the queue.
    2 = obvious alcohol, pet or non-food candidate; retain but verify last.
    """
    url = str(row.get("canonical_url_candidate") or row.get("canonical_url") or row.get("url") or "")
    if DEPRIORITIZED_URL_SIGNAL_RE.search(url):
        return 2
    if FOOD_URL_SIGNAL_RE.search(url):
        return 0
    return 1


def candidate_key(row: dict[str, Any]) -> tuple[int, int, int, str, str]:
    food_priority = candidate_food_priority(row)
    has_gtin_hint = 0 if norm_sku(row.get("gtin_hint_external")) else 1
    has_name_hint = 0 if str(row.get("name_hint_external") or "").strip() else 1
    name = str(row.get("name_hint_external") or "").casefold()
    sku = norm_sku(row.get("retailer_sku")) or ""
    return (food_priority, has_gtin_hint, has_name_hint, name, sku)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="fixtures/carrefour_candidate_urls_radarsuper.jsonl", type=Path)
    parser.add_argument(
        "--verified",
        default=[Path("fixtures/carrefour_first_party_products_cumulative.jsonl")],
        nargs="+",
        type=Path,
        help="One or more verified first-party product JSONL files. Missing paths are ignored.",
    )
    parser.add_argument(
        "--terminal-outcomes",
        default=Path("fixtures/carrefour_first_party_candidate_route_outcomes.jsonl"),
        type=Path,
        help=(
            "Persisted official-route observations for discovery candidates. Rows with "
            "terminal=true exclude that Carrefour product ID from future verification queues."
        ),
    )
    parser.add_argument("--output", default="fixtures/carrefour_unverified_candidates_head.jsonl", type=Path)
    parser.add_argument("--summary", default="fixtures/carrefour_unverified_candidates_summary.json", type=Path)
    parser.add_argument("--limit", type=int, default=250)
    args = parser.parse_args()

    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")

    verified_rows: list[dict[str, Any]] = []
    verified_inputs_used: list[str] = []
    for path in args.verified:
        if not path.exists():
            continue
        verified_inputs_used.append(str(path))
        verified_rows.extend(read_jsonl(path))
    verified_skus = {
        sku
        for row in verified_rows
        if str(row.get("source") or "") == "CARREFOUR_FIRST_PARTY"
        for sku in [norm_sku(row.get("retailer_sku"))]
        if sku
    }

    terminal_rows = list(read_jsonl(args.terminal_outcomes))
    terminal_skus = {
        sku
        for row in terminal_rows
        if bool(row.get("terminal"))
        for sku in [norm_sku(row.get("retailer_sku"))]
        if sku
    }
    terminal_outcome_counts: dict[str, int] = {}
    for row in terminal_rows:
        if not bool(row.get("terminal")):
            continue
        outcome = str(row.get("outcome") or "UNKNOWN_TERMINAL")
        terminal_outcome_counts[outcome] = terminal_outcome_counts.get(outcome, 0) + 1

    candidate_rows = list(read_jsonl(args.candidates))
    by_sku: dict[str, tuple[dict[str, Any], str]] = {}
    missing_sku = 0
    id_source_counts: dict[str, int] = {}
    for row in candidate_rows:
        sku, id_source = candidate_sku(row)
        id_source_counts[id_source] = id_source_counts.get(id_source, 0) + 1
        if not sku:
            missing_sku += 1
            continue
        by_sku.setdefault(sku, (row, id_source))

    unverified: list[dict[str, Any]] = []
    already_verified = 0
    terminal_excluded = 0
    for sku, (row, id_source) in by_sku.items():
        if sku in verified_skus:
            already_verified += 1
            continue
        if sku in terminal_skus:
            terminal_excluded += 1
            continue
        selected = {
            "retailer": "CARREFOUR",
            "candidate_source": str(row.get("candidate_source") or "EXTERNAL_DISCOVERY_ONLY"),
            "candidate_source_url": row.get("candidate_source_url"),
            "retailer_sku": sku,
            "retailer_sku_candidate_source": id_source,
            "external_retailer_sku_candidate": norm_sku(row.get("retailer_sku_candidate")),
            "gtin_hint_external": norm_sku(row.get("gtin") or row.get("ean") or row.get("barcode")),
            "name_hint_external": row.get("name_hint") or row.get("name"),
            "canonical_url_candidate": row.get("canonical_url") or row.get("url"),
            "canonical_url_verified": False,
            "selection_reason": "NOT_YET_DIRECTLY_VERIFIED",
            "evidence_status": "DISCOVERY_ONLY_NOT_CARREFOUR_EVIDENCE",
            "queue_food_priority": candidate_food_priority(
                {"canonical_url_candidate": row.get("canonical_url") or row.get("url")}
            ),
            "provenance_note": (
                "External discovery hint only. The Carrefour R- identifier parsed from the URL is "
                "used solely to prioritize verification. Do not attribute any field in this row to "
                "Carrefour until an official Carrefour surface is directly observed."
            ),
        }
        unverified.append(selected)

    unverified.sort(key=candidate_key)
    selected_rows = unverified[: args.limit]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in selected_rows),
        encoding="utf-8",
    )

    priority_counts = {
        "food_like": sum(1 for row in unverified if candidate_food_priority(row) == 0),
        "uncertain": sum(1 for row in unverified if candidate_food_priority(row) == 1),
        "deprioritized_obvious_alcohol_pet_or_nonfood": sum(
            1 for row in unverified if candidate_food_priority(row) == 2
        ),
    }
    selected_priority_counts = {
        "food_like": sum(1 for row in selected_rows if candidate_food_priority(row) == 0),
        "uncertain": sum(1 for row in selected_rows if candidate_food_priority(row) == 1),
        "deprioritized_obvious_alcohol_pet_or_nonfood": sum(
            1 for row in selected_rows if candidate_food_priority(row) == 2
        ),
    }

    summary = {
        "source_boundary": {
            "candidate_input": "EXTERNAL_DISCOVERY_ONLY",
            "verified_input": "CARREFOUR_FIRST_PARTY",
            "terminal_outcome_input": "CARREFOUR_FIRST_PARTY_ROUTE_OUTCOME_NOT_PRODUCT_EVIDENCE",
            "output_is_first_party_evidence": False,
        },
        "verified_inputs_used": verified_inputs_used,
        "terminal_outcomes_input": str(args.terminal_outcomes) if args.terminal_outcomes.exists() else None,
        "counts": {
            "candidate_rows": len(candidate_rows),
            "candidate_unique_carrefour_url_ids": len(by_sku),
            "candidate_rows_missing_product_id": missing_sku,
            "verified_first_party_unique_skus": len(verified_skus),
            "candidate_ids_already_verified": already_verified,
            "candidate_ids_terminal_route_excluded": terminal_excluded,
            "candidate_ids_not_yet_verified": len(unverified),
            "queue_rows_emitted": len(selected_rows),
            "queue_limit": args.limit,
            "unverified_with_external_gtin_hint": sum(1 for row in unverified if row.get("gtin_hint_external")),
            "unverified_with_external_name_hint": sum(1 for row in unverified if row.get("name_hint_external")),
        },
        "candidate_id_source_counts": id_source_counts,
        "terminal_outcome_counts": terminal_outcome_counts,
        "food_priority_counts": priority_counts,
        "emitted_food_priority_counts": selected_priority_counts,
        "queue_order": (
            "Rumbo human-food-like URL slugs first; uncertain/general candidates second; obvious alcohol, pet and non-food last. "
            "Within each tier: external GTIN hint, name hint, casefolded name, Carrefour URL product ID."
        ),
        "notes": [
            "This queue is only a prioritization aid for direct official Carrefour verification.",
            "No external candidate value is promoted to CARREFOUR_FIRST_PARTY evidence by this script.",
            "URL-slug food priority is scheduling metadata only. Candidates are retained regardless of tier and require direct Carrefour observation before any field becomes evidence.",
            "Pet/cosmetic exclusions are evaluated before generic food tokens so URLs such as galletas-para-perro or leche-corporal do not consume the human-food verification head.",
            "Persisted terminal outcomes are official-route observations only; they exclude stale candidate IDs but do not create product evidence.",
            "The RadarSuper export carries an external retailer_sku_candidate that can be a slug; the Carrefour R- ID is therefore parsed preferentially from the candidate URL.",
            "Pending direct first-party batch fixtures may be included as verified inputs so the queue remains current before the cumulative merge commit lands.",
        ],
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["counts"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
