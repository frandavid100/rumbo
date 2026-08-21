#!/usr/bin/env python3
"""Probe official Carrefour historical documents that expose EAN/GTIN values.

This dataset is intentionally separate from the current Carrefour product staging.
Historical EAN evidence must never be promoted to a current product merely because
its name looks similar: an exact/current identity check is required first.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

SOURCE = "CARREFOUR_FIRST_PARTY"
EAN_RE = re.compile(r"(?<!\d)(\d{13})(?!\d)")

DOCUMENTS = [
    {
        "label": "Carrefour No Gluten product list (2017 static archive)",
        "url": "https://static.carrefour.es/crs/cdn_static/c4corp-front/documentos/crf-no-gluten/20170704/images/nogluten/listados_no-gluten.pdf",
        "source_date": "2017-07-04",
    },
    {
        "label": "Carrefour FACE gluten-free product list (legacy)",
        "url": "https://www.carrefour.es/_includes/pdfs/productos-singluten-listaface.pdf",
        "source_date": None,
    },
    {
        "label": "Carrefour FACE gluten-free product list (2014-02-06)",
        "url": "https://www.carrefour.es/_includes/pdfs/productos-singluten-listaface_20140206.pdf",
        "source_date": "2014-02-06",
    },
]


def fetch(url: str, timeout: int) -> tuple[int | None, bytes | None, str | None]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; RumboCatalogResearch/1.0; +https://github.com/frandavid100/rumbo)",
            "Accept": "application/pdf,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read(), None
    except urllib.error.HTTPError as exc:
        return int(exc.code), None, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # network/TLS/timeouts are evidence too
        return None, None, f"{type(exc).__name__}: {exc}"


def extract_pdf_text(payload: bytes) -> str:
    reader = PdfReader(io.BytesIO(payload))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def contexts_for_gtins(text: str) -> list[tuple[str, str]]:
    # Keep original extracted lines so each GTIN remains auditable in context.
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    out: list[tuple[str, str]] = []
    for idx, line in enumerate(lines):
        for match in EAN_RE.finditer(line.replace(" ", "")):
            gtin = match.group(1)
            start = max(0, idx - 2)
            end = min(len(lines), idx + 3)
            context = " | ".join(lines[start:end])
            out.append((gtin, context))
    # PDF extractors sometimes put product and EAN in one large line; scan whole text too.
    if not out:
        compact = " ".join(text.split())
        for match in EAN_RE.finditer(compact):
            s = max(0, match.start() - 180)
            e = min(len(compact), match.end() + 180)
            out.append((match.group(1), compact[s:e]))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    observed_at = datetime.now(timezone.utc).isoformat()
    evidence: dict[tuple[str, str], dict] = {}
    docs_summary: list[dict] = []

    for document in DOCUMENTS:
        status, payload, error = fetch(document["url"], args.timeout)
        doc_summary = {
            "label": document["label"],
            "url": document["url"],
            "source_date": document["source_date"],
            "http_status": status,
            "fetch_error": error,
            "bytes": len(payload) if payload else 0,
            "extracted_gtin_occurrences": 0,
            "unique_gtins": 0,
        }
        if payload:
            try:
                text = extract_pdf_text(payload)
                pairs = contexts_for_gtins(text)
                unique_doc = set()
                for gtin, context in pairs:
                    unique_doc.add(gtin)
                    key = (document["url"], gtin)
                    evidence[key] = {
                        "retailer": "CARREFOUR",
                        "source": SOURCE,
                        "evidence_type": "HISTORICAL_DECLARED_GTIN",
                        "evidence_scope": "HISTORICAL_FIRST_PARTY_DOCUMENT",
                        "gtin": gtin,
                        "document_url": document["url"],
                        "document_label": document["label"],
                        "source_date": document["source_date"],
                        "observed_at": observed_at,
                        "retrieval_freshness": "HISTORICAL_DOCUMENT_DO_NOT_ASSUME_CURRENT",
                        "context": context,
                        "current_product_match_status": "NOT_ATTEMPTED",
                        "safe_for_current_product_merge": False,
                    }
                doc_summary["extracted_gtin_occurrences"] = len(pairs)
                doc_summary["unique_gtins"] = len(unique_doc)
            except Exception as exc:
                doc_summary["parse_error"] = f"{type(exc).__name__}: {exc}"
        docs_summary.append(doc_summary)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(evidence.values(), key=lambda row: (row["document_url"], row["gtin"]))
    args.out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    unique_gtins = {row["gtin"] for row in rows}
    statuses = Counter(str(doc.get("http_status")) for doc in docs_summary)
    summary = {
        "retailer": "CARREFOUR",
        "source": SOURCE,
        "built_at": observed_at,
        "purpose": "Historical first-party EAN/GTIN discovery only; never a current-product assertion without a separate exact identity check.",
        "documents": docs_summary,
        "counts": {
            "documents_attempted": len(DOCUMENTS),
            "documents_fetched": sum(1 for doc in docs_summary if doc.get("http_status") == 200),
            "evidence_rows": len(rows),
            "unique_gtins": len(unique_gtins),
        },
        "http_status_counts": dict(statuses),
        "safe_for_current_product_merge": False,
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
