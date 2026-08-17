from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import re
import unicodedata
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from mercadona_weekly_catalog_adapter import deterministic_candidate_ids, fetch_product_ids, stratified_sample
from pilot_large_catalog import _fetch_candidate_products, _is_food_category

PROBE_VERSION = "1.0.0"
AESAN_PAGE = "https://www.aesan.gob.es/AECOSAN/web/seguridad_alimentaria/subseccion/alimentosBebidas.htm"
SEED = "rumbo-mercadona-pilot-2026-08"
SAMPLE_SIZE = 300
CANDIDATE_POOL = 900
BASE = Path(__file__).resolve().parent
FIX = BASE / "fixtures"


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text)))
            self._href = None
            self._text = []


def _fetch(url: str, timeout: int = 30) -> bytes:
    req = Request(url, headers={"User-Agent": "RumboCatalogProbe/1.0 (+https://github.com/frandavid100/rumbo)"})
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def discover_excel_url(page_url: str = AESAN_PAGE) -> str:
    html = _fetch(page_url).decode("utf-8", errors="replace")
    parser = _LinkParser()
    parser.feed(html)
    ranked: list[tuple[int, str]] = []
    for href, text in parser.links:
        blob = f"{href} {text}".lower()
        score = 0
        if "excel" in blob:
            score += 4
        if "compos" in blob and ("alimento" in blob or "bebida" in blob):
            score += 3
        if "2022" in blob:
            score += 2
        if re.search(r"\.(xlsx?|csv)(?:$|[?#])", href.lower()):
            score += 3
        if score:
            ranked.append((score, urljoin(page_url, href)))
    if not ranked:
        raise RuntimeError("AESAN Excel link not found on official page")
    ranked.sort(reverse=True)
    return ranked[0][1]


def norm(value) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def digits(value) -> str:
    return re.sub(r"\D", "", "" if value is None else str(value))


def _find_column(columns, aliases: tuple[str, ...]) -> str | None:
    normalized = {c: norm(c) for c in columns}
    for alias in aliases:
        a = norm(alias)
        for col, n in normalized.items():
            if n == a:
                return col
    for alias in aliases:
        a = norm(alias)
        for col, n in normalized.items():
            if a and a in n:
                return col
    return None


def _read_excel(data: bytes):
    import pandas as pd

    book = pd.ExcelFile(io.BytesIO(data))
    frames = []
    diagnostics = []
    for sheet in book.sheet_names:
        # Most public workbooks have a normal header. If that is not true, search
        # the first 15 rows for the row containing both product/name and energy/macros.
        raw = pd.read_excel(book, sheet_name=sheet, header=None, nrows=18)
        header_row = 0
        best = -1
        for i, row in raw.iterrows():
            cells = [norm(x) for x in row.tolist() if str(x) != "nan"]
            joined = " | ".join(cells)
            score = sum(token in joined for token in ("producto", "denomin", "marca", "energia", "prote", "hidr", "grasa"))
            if score > best:
                best, header_row = score, int(i)
        frame = pd.read_excel(book, sheet_name=sheet, header=header_row)
        frame.columns = [str(x).strip() for x in frame.columns]
        frames.append(frame)
        diagnostics.append({"sheet": sheet, "header_row": header_row, "columns": list(frame.columns), "rows": len(frame)})
    if not frames:
        raise RuntimeError("AESAN workbook contained no sheets")
    return pd.concat(frames, ignore_index=True, sort=False), diagnostics


def _load_persisted_resolved_ids() -> set[str]:
    resolved: set[str] = set()
    structured = json.loads((FIX / "pilot_300_structured_resolved.json").read_text(encoding="utf-8"))
    resolved |= {str(x["product_id"]) for x in structured}
    for path in FIX.glob("pilot_300_declared_label_evidence*.json"):
        rows = json.loads(path.read_text(encoding="utf-8"))
        resolved |= {str(x["product_id"]) for x in rows}
    generic = json.loads((FIX / "generic_fdc_accepted_mappings.json").read_text(encoding="utf-8"))
    resolved |= {str(x["product_id"]) for x in generic}
    return resolved


def _same_brand(current_brand: str | None, historic_brand: str | None) -> bool:
    a, b = norm(current_brand), norm(historic_brand)
    if not a or not b:
        return False
    return a == b or a in b or b in a


def _name_similarity(a: str, b: str) -> float:
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jac = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    return round(0.65 * seq + 0.35 * jac, 4)


def _float(value):
    if value is None:
        return None
    s = str(value).strip().replace(",", ".")
    if not s or s.lower() == "nan":
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


@dataclass
class Match:
    product_id: str
    current_name: str
    current_brand: str | None
    current_ean: str | None
    aesan_name: str
    aesan_brand: str | None
    aesan_gtin: str | None
    score: float
    match_class: str
    nutrition: dict


def main() -> int:
    out = Path(os.environ.get("AESAN_PROBE_OUTPUT_DIR", "aesan-2022-probe-output"))
    out.mkdir(parents=True, exist_ok=True)

    excel_url = os.environ.get("AESAN_2022_EXCEL_URL") or discover_excel_url()
    excel = _fetch(excel_url, timeout=60)
    frame, workbook_diag = _read_excel(excel)
    cols = list(frame.columns)

    name_col = _find_column(cols, ("nombre producto", "producto", "denominacion", "nombre comercial", "alimento"))
    brand_col = _find_column(cols, ("marca", "brand"))
    gtin_col = _find_column(cols, ("ean", "gtin", "codigo de barras", "codigo barras"))
    kcal_col = _find_column(cols, ("energia kcal", "valor energetico kcal", "kcal", "energia"))
    fat_col = _find_column(cols, ("grasas", "grasa total", "lipidos"))
    carb_col = _find_column(cols, ("hidratos de carbono", "carbohidratos", "hidratos"))
    protein_col = _find_column(cols, ("proteinas", "proteina"))

    required = {"name": name_col, "kcal": kcal_col, "fat": fat_col, "carb": carb_col, "protein": protein_col}
    missing = [k for k, v in required.items() if not v]
    if missing:
        report = {"probe_version": PROBE_VERSION, "excel_url": excel_url, "workbook": workbook_diag,
                  "detected_columns": {"name": name_col, "brand": brand_col, "gtin": gtin_col,
                                       "kcal": kcal_col, "fat": fat_col, "carb": carb_col, "protein": protein_col},
                  "error": f"Required AESAN columns not detected: {missing}"}
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    ids = fetch_product_ids()
    candidates = deterministic_candidate_ids(ids, seed=SEED, limit=CANDIDATE_POOL)
    products, acquisition_errors = _fetch_candidate_products(candidates, 16)
    food = [p for p in products if _is_food_category(p.category_key)]
    sample = stratified_sample(food, size=SAMPLE_SIZE, per_category_cap=24)
    resolved = _load_persisted_resolved_ids()
    pending = [p for p in sample if str(p.product_id) not in resolved]

    historic = []
    for idx, row in frame.iterrows():
        name = row.get(name_col)
        if not norm(name):
            continue
        nutrition = {"kcal_100": _float(row.get(kcal_col)), "fat_100": _float(row.get(fat_col)),
                     "carb_100": _float(row.get(carb_col)), "protein_100": _float(row.get(protein_col))}
        if any(v is None for v in nutrition.values()):
            continue
        historic.append({"index": int(idx), "name": str(name),
                         "brand": None if not brand_col else str(row.get(brand_col)),
                         "gtin": None if not gtin_col else digits(row.get(gtin_col)),
                         "nutrition": nutrition})

    matches: list[Match] = []
    review: list[dict] = []
    for p in pending:
        pgtin = digits(p.ean)
        scored = []
        for h in historic:
            exact_gtin = bool(pgtin and len(pgtin) >= 8 and pgtin == h["gtin"])
            brand_ok = _same_brand(p.brand, h["brand"])
            sim = _name_similarity(p.name, h["name"])
            if exact_gtin:
                score, cls = 1.0, "EXACT_GTIN"
            elif brand_ok and sim >= 0.92:
                score, cls = sim, "HIGH_BRAND_NAME"
            elif brand_ok and sim >= 0.78:
                score, cls = sim, "REVIEW_BRAND_NAME"
            elif sim >= 0.94:
                score, cls = sim * 0.92, "REVIEW_NAME_ONLY"
            else:
                continue
            scored.append((score, cls, h))
        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            continue
        score, cls, h = scored[0]
        margin = score - scored[1][0] if len(scored) > 1 else score
        payload = Match(str(p.product_id), p.name, p.brand, p.ean, h["name"], h["brand"], h["gtin"],
                        round(score, 4), cls, h["nutrition"])
        if cls == "EXACT_GTIN" or (cls == "HIGH_BRAND_NAME" and margin >= 0.04):
            matches.append(payload)
        else:
            review.append({**asdict(payload), "runner_up_margin": round(margin, 4)})

    class_counts: dict[str, int] = {}
    for m in matches:
        class_counts[m.match_class] = class_counts.get(m.match_class, 0) + 1
    report = {
        "probe_version": PROBE_VERSION,
        "source": "AESAN products marketed in Spain, observations collected in 2022",
        "source_freshness_warning": "Historical only: AESAN states products may have changed after 2022",
        "excel_url": excel_url,
        "aesan_rows_total": len(frame),
        "aesan_rows_with_core_nutrition": len(historic),
        "detected_columns": {"name": name_col, "brand": brand_col, "gtin": gtin_col,
                             "kcal": kcal_col, "fat": fat_col, "carb": carb_col, "protein": protein_col},
        "sample_size": len(sample),
        "already_resolved": len(resolved & {str(p.product_id) for p in sample}),
        "pending_checked": len(pending),
        "high_confidence_historical_matches": len(matches),
        "high_confidence_rate_of_pending": round(len(matches) / len(pending), 4) if pending else 0,
        "high_confidence_classes": class_counts,
        "review_candidates": len(review),
        "matches": [asdict(m) for m in matches],
        "review": review[:200],
        "workbook": workbook_diag,
        "acquisition_error_count": len(acquisition_errors),
        "policy": "Probe only. No AESAN values are promoted to current DECLARED/MATCHED evidence automatically.",
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "high-confidence-matches.json").write_text(json.dumps([asdict(m) for m in matches], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("matches", "review", "workbook")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
