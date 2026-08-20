from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

import carrefour_first_party_inventory as base
from carrefour_first_party_browser_probe import DEFAULT_URLS

SOURCE = base.SOURCE
VERSION = "carrefour-first-party-browser-inventory-1.0"
BLOCK_RE = re.compile(
    r"sorry,? you have been blocked|attention required|cloudflare|access denied|forbidden|captcha|robot|incapsula|akamai",
    re.I,
)


def sku_from_url(url: str) -> str:
    m = re.search(r"/R-([^/]+)/p/?$", url.split("?", 1)[0], re.I)
    return m.group(1) if m else hashlib.sha256(url.encode()).hexdigest()[:20]


def extract_from_html(url: str, final_url: str, status: int | None, raw: str, text: str):
    observed_at = base.now_iso()
    sku = sku_from_url(final_url or url)
    product = base.first_product_ld(raw)
    breadcrumbs = base.breadcrumb_path(raw)

    name = base.clean(product.get("name"))
    if not name:
        hm = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.I | re.S)
        name = base.clean(base.html_to_text(hm.group(1))) if hm else None

    brand_obj = product.get("brand")
    brand = base.clean(brand_obj.get("name")) if isinstance(brand_obj, dict) else base.clean(brand_obj)

    gtin = None
    for key in ("gtin14", "gtin13", "gtin12", "gtin8", "gtin", "ean"):
        value = product.get(key)
        if value and re.fullmatch(r"\d{8,14}", str(value)):
            gtin = str(value)
            break
    if not gtin:
        gm = re.search(r'"(?:gtin(?:13|14|12|8)?|ean)"\s*:\s*"(\d{8,14})"', raw, re.I)
        gtin = gm.group(1) if gm else None

    image = product.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url") or image.get("contentUrl")

    offers = product.get("offers")
    offers = offers[0] if isinstance(offers, list) and offers else offers
    offers = offers if isinstance(offers, dict) else {}
    price = base.norm_number(offers.get("price"))
    currency = base.clean(offers.get("priceCurrency"))
    availability = base.clean(offers.get("availability"))
    if availability and "/" in availability:
        availability = availability.rsplit("/", 1)[-1]
    if price is None:
        pm = re.search(r"\b(\d{1,4}[.,]\d{2})\s*€", text)
        price = base.norm_number(pm.group(1)) if pm else None
    um = re.search(r"\b(\d{1,4}[.,]\d{1,3})\s*€\s*/\s*(kg|l|ud|100\s*ml|100\s*g)\b", text, re.I)
    unit_price = None
    if um:
        unit = re.sub(r"\s+", "", um.group(2))
        unit_price = f"{um.group(1)} €/{unit}"
    if not availability:
        if re.search(r"Agotado temporalmente", text, re.I):
            availability = "OutOfStock"
        elif re.search(r"\bAñadir\b", text, re.I):
            availability = "InStock"

    nutrition_text = base.section(
        text,
        ["Información nutricional", "Informacion nutricional"],
        ["Ingredientes", "Alérgenos", "Más información", "Datos del producto", "Características producto", "Otra información obligatoria"],
    )
    ingredients = base.section(
        text,
        ["Ingredientes"],
        ["Alérgenos", "Más información", "Datos del producto", "Características producto", "Otra información obligatoria", "Información nutricional"],
    )
    allergens = base.section(
        text,
        ["Alérgenos", "Alergenos"],
        ["Más información", "Datos del producto", "Características producto", "Otra información obligatoria", "Información nutricional", "Ingredientes"],
    )
    legal_name = base.labelled_value(text, ["Denominación legal", "Denominacion legal"])
    net_content = base.labelled_value(text, ["Contenido neto"])
    storage = base.labelled_value(text, ["Condiciones de conservación", "Condiciones de conservacion", "Modo conservación", "Modo conservacion"])
    preparation = base.labelled_value(text, ["Modo de empleo", "Instrucciones"])
    operator = base.labelled_value(text, ["Dirección del operador de la empresa alimentaria", "Direccion del operador de la empresa alimentaria"])
    manufacturer = base.labelled_value(text, ["Razón social fabricante/envasador/importador", "Razon social fabricante/envasador/importador"])
    mandatory_mentions = base.labelled_value(text, ["Menciones obligatorias"])
    nutriscore = base.labelled_value(text, ["Nutriscore"])
    attributes = {}
    for label, key in (
        ("Tipo de bollería", "bakery_type"),
        ("Tipo de bolleria", "bakery_type"),
        ("Momento de consumo", "consumption_moment"),
        ("Producto", "product_type"),
    ):
        value = base.labelled_value(text, [label])
        if value and key not in attributes:
            attributes[key] = value

    ntext = nutrition_text or ""
    bm = re.search(r"(?:por|cada|Valores medios por)\s+100\s*(g|ml)", ntext or text, re.I)
    basis = "100 " + bm.group(1).lower() if bm else None
    km = re.search(r"(\d+(?:[.,]\d+)?)\s*Kcal", ntext, re.I)
    kcal = base.norm_number(km.group(1)) if km else None
    jm = re.search(r"(\d+(?:[.,]\d+)?)\s*KJ", ntext, re.I)
    kj = base.norm_number(jm.group(1)) if jm else None

    def grams(label: str):
        mm = re.search(label + r"[^0-9]{0,35}(\d+(?:[.,]\d+)?)\s*g", ntext, re.I)
        return base.norm_number(mm.group(1)) if mm else None

    vals = {
        "energy_kj": kj,
        "calories_kcal": kcal,
        "fat_g": grams(r"Grasas?(?:\s*\(g\))?"),
        "saturates_g": grams(r"(?:de las cuales\s+)?Saturadas?(?:\s*\(g\))?"),
        "carbohydrate_g": grams(r"Hidratos?\s+de\s+carbono(?:\s*\(g\))?"),
        "sugars_g": grams(r"(?:de los cuales\s+|de las cuales\s+)?Az[uú]cares?(?:\s*\(g\))?"),
        "fiber_g": grams(r"Fibra(?:\s+alimentaria)?(?:\s*\(g\))?"),
        "protein_g": grams(r"Prote[ií]nas?(?:\s*\(g\))?"),
        "salt_g": grams(r"Sal(?:\s*\(g\))?"),
    }
    core = sum(vals[x] is not None for x in ("calories_kcal", "fat_g", "carbohydrate_g", "protein_g"))
    nstatus = "DECLARED_COMPLETE" if core == 4 else ("DECLARED_PARTIAL" if any(v is not None for v in vals.values()) else "NOT_FOUND")

    row = {
        "retailer": "CARREFOUR",
        "retailer_sku": sku,
        "canonical_url": (final_url or url).split("?", 1)[0],
        "observed_at": observed_at,
        "source": SOURCE,
        "http_status": status,
        "page_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "fetch_error": None,
        "name": name,
        "brand": brand,
        "gtin": gtin,
        "image_url": base.clean(image),
        "category_path": breadcrumbs,
        "price_eur": price,
        "price_currency": currency or ("EUR" if price is not None else None),
        "unit_price_text": unit_price,
        "availability": availability,
        "legal_name": legal_name,
        "ingredients": ingredients,
        "allergens": allergens,
        "net_content": net_content,
        "storage_conditions": storage,
        "preparation_instructions": preparation,
        "operator_address": operator,
        "manufacturer_packer_importer": manufacturer,
        "mandatory_mentions": mandatory_mentions,
        "nutriscore": nutriscore,
        "attributes": attributes,
        "nutrition_basis": basis,
        "nutrition_status": nstatus,
        **vals,
    }

    declared = [
        "name", "brand", "gtin", "image_url", "category_path", "legal_name", "ingredients", "allergens",
        "net_content", "storage_conditions", "preparation_instructions", "operator_address",
        "manufacturer_packer_importer", "mandatory_mentions", "nutriscore", "attributes", "nutrition_basis",
        "energy_kj", "calories_kcal", "fat_g", "saturates_g", "carbohydrate_g", "sugars_g", "fiber_g",
        "protein_g", "salt_g",
    ]
    observed = ["price_eur", "price_currency", "unit_price_text", "availability", "canonical_url"]
    evidence = []
    for field in declared + observed:
        value = row.get(field)
        if value in (None, "", [], {}):
            continue
        evidence.append({
            "retailer_sku": sku,
            "field": field,
            "value": value,
            "source": SOURCE,
            "evidence_type": "DECLARED" if field in declared else "OBSERVED_LISTING",
            "source_url": row["canonical_url"],
            "observed_at": observed_at,
        })
    return row, evidence


async def inspect_url(context, url: str, timeout_ms: int, network_body_limit: int):
    page = await context.new_page()
    sku = sku_from_url(url)
    network = []
    tasks: list[asyncio.Task] = []

    async def capture(response):
        req = response.request
        resource_type = req.resource_type
        response_url = response.url
        if "carrefour" not in response_url.lower():
            return
        headers = await response.all_headers()
        content_type = headers.get("content-type", "")
        item = {
            "retailer_sku": sku,
            "url": response_url,
            "status": response.status,
            "resource_type": resource_type,
            "content_type": content_type,
        }
        if "json" in content_type.lower() and resource_type in {"xhr", "fetch"}:
            try:
                body = await response.text()
                item["body_bytes"] = len(body.encode())
                if len(body) <= network_body_limit:
                    try:
                        payload = json.loads(body)
                        if isinstance(payload, dict):
                            item["json_keys"] = sorted(payload.keys())[:80]
                        elif isinstance(payload, list):
                            item["json_type"] = "list"
                            item["json_length"] = len(payload)
                        item["body_sample"] = body[: min(len(body), 12000)]
                    except Exception:
                        item["body_sample"] = body[:4000]
            except Exception as exc:
                item["body_error"] = f"{type(exc).__name__}:{exc}"
        network.append(item)

    page.on("response", lambda response: tasks.append(asyncio.create_task(capture(response))))
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        status = response.status if response else None
        await page.wait_for_timeout(2200)
        final_url = page.url
        title = await page.title()
        raw = await page.content()
        text = await page.locator("body").inner_text(timeout=5000)
        blocked = bool((status == 403) or BLOCK_RE.search(title + "\n" + text))
        if blocked:
            row = {
                "retailer": "CARREFOUR",
                "retailer_sku": sku,
                "canonical_url": url.split("?", 1)[0],
                "observed_at": base.now_iso(),
                "source": SOURCE,
                "http_status": status,
                "fetch_error": "BLOCKED:CLOUDFLARE_OR_WAF",
                "nutrition_status": "FETCH_ERROR",
            }
            evidence = []
        elif status and status < 400 and len(text) > 1000:
            row, evidence = extract_from_html(url, final_url, status, raw, text)
        else:
            row = {
                "retailer": "CARREFOUR",
                "retailer_sku": sku,
                "canonical_url": url.split("?", 1)[0],
                "observed_at": base.now_iso(),
                "source": SOURCE,
                "http_status": status,
                "fetch_error": f"UNUSABLE_PAGE:{title}",
                "nutrition_status": "FETCH_ERROR",
            }
            evidence = []
        row["browser_title"] = title
        row["html_bytes"] = len(raw.encode())
        row["text_chars"] = len(text)
        row["blocked"] = blocked
    except Exception as exc:
        row = {
            "retailer": "CARREFOUR",
            "retailer_sku": sku,
            "canonical_url": url.split("?", 1)[0],
            "observed_at": base.now_iso(),
            "source": SOURCE,
            "fetch_error": f"{type(exc).__name__}:{exc}",
            "nutrition_status": "FETCH_ERROR",
            "blocked": False,
        }
        evidence = []
    finally:
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await page.close()
    return row, evidence, network


def write_sqlite(path: Path, rows: list[dict], evidence: list[dict]):
    db = base.init_db(path)
    for r in rows:
        db.execute(
            "INSERT OR REPLACE INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                r.get("retailer_sku"), r.get("gtin"), r.get("name"), r.get("brand"), r.get("canonical_url"),
                r.get("image_url"), json.dumps(r.get("category_path") or [], ensure_ascii=False), r.get("price_eur"),
                r.get("price_currency"), r.get("unit_price_text"), r.get("availability"), r.get("legal_name"),
                r.get("ingredients"), r.get("allergens"), r.get("net_content"), r.get("storage_conditions"),
                r.get("preparation_instructions"), r.get("operator_address"), r.get("manufacturer_packer_importer"),
                r.get("observed_at"), r.get("page_sha256"), r.get("http_status"), r.get("fetch_error"), SOURCE,
            ),
        )
        db.execute(
            "INSERT OR REPLACE INTO nutrition VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                r.get("retailer_sku"), r.get("nutrition_basis"), r.get("energy_kj"), r.get("calories_kcal"),
                r.get("fat_g"), r.get("saturates_g"), r.get("carbohydrate_g"), r.get("sugars_g"), r.get("fiber_g"),
                r.get("protein_g"), r.get("salt_g"), r.get("nutrition_status"), SOURCE, "DECLARED",
            ),
        )
    for e in evidence:
        db.execute(
            "INSERT OR REPLACE INTO field_evidence VALUES(?,?,?,?,?,?,?)",
            (
                e["retailer_sku"], e["field"], e["source"], e["evidence_type"],
                json.dumps(e["value"], ensure_ascii=False), e["source_url"], e["observed_at"],
            ),
        )
    metadata = {
        "retailer": "CARREFOUR",
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "source": base.BASE,
        "extractor_version": VERSION,
        "built_at": base.now_iso(),
        "classification_performed": "false",
    }
    for k, v in metadata.items():
        db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)", (k, str(v)))
    db.commit()
    db.close()


async def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    urls = set(args.url or DEFAULT_URLS)
    for path in args.seed_jsonl:
        urls.update(base.read_seed_jsonl(path))
    urls = sorted(urls)
    if args.rotate and urls:
        offset = int(datetime.now(timezone.utc).timestamp() // 3600) % len(urls)
        urls = urls[offset:] + urls[:offset]
    if args.max_products > 0:
        urls = urls[: args.max_products]

    rows, evidence, network = [], [], []
    consecutive_blocks = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="es-ES", viewport={"width": 1365, "height": 900})
        for index, url in enumerate(urls, 1):
            row, ev, net = await inspect_url(context, url, args.timeout * 1000, args.network_body_limit)
            rows.append(row)
            evidence.extend(ev)
            network.extend(net)
            print(json.dumps({
                "index": index,
                "sku": row.get("retailer_sku"),
                "status": row.get("http_status"),
                "name": row.get("name"),
                "nutrition_status": row.get("nutrition_status"),
                "blocked": row.get("blocked"),
            }, ensure_ascii=False))
            consecutive_blocks = consecutive_blocks + 1 if row.get("blocked") else 0
            if args.stop_after_blocks > 0 and consecutive_blocks >= args.stop_after_blocks:
                break
            if index < len(urls) and args.delay > 0:
                await page_sleep(args.delay)
        await context.close()
        await browser.close()

    rows.sort(key=lambda r: r["retailer_sku"])
    with (out / "products.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out / "field_evidence.jsonl").open("w", encoding="utf-8") as f:
        for item in evidence:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    with (out / "network_responses.jsonl").open("w", encoding="utf-8") as f:
        for item in network:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    write_sqlite(out / "carrefour_first_party.sqlite", rows, evidence)

    fields = [
        "gtin", "name", "brand", "image_url", "category_path", "price_eur", "unit_price_text", "availability",
        "legal_name", "ingredients", "allergens", "net_content", "storage_conditions", "preparation_instructions",
        "operator_address", "manufacturer_packer_importer", "mandatory_mentions", "nutriscore", "attributes",
    ]
    nutrition_fields = ["energy_kj", "calories_kcal", "fat_g", "saturates_g", "carbohydrate_g", "sugars_g", "fiber_g", "protein_g", "salt_g"]
    network_json = [n for n in network if "json" in (n.get("content_type") or "").lower() and n.get("resource_type") in {"xhr", "fetch"}]
    summary = {
        "retailer": "CARREFOUR",
        "source_policy": "FIRST_PARTY_CARREFOUR_ONLY",
        "source": base.BASE,
        "extractor_version": VERSION,
        "built_at": base.now_iso(),
        "classification_performed": "false",
        "counts": {
            "candidate_urls": len(urls),
            "attempted": len(rows),
            "fetched": sum(not r.get("fetch_error") for r in rows),
            "blocked": sum(bool(r.get("blocked")) for r in rows),
            "fetch_errors": sum(bool(r.get("fetch_error")) for r in rows),
            "nutrition_complete": sum(r.get("nutrition_status") == "DECLARED_COMPLETE" for r in rows),
            "nutrition_partial": sum(r.get("nutrition_status") == "DECLARED_PARTIAL" for r in rows),
            "nutrition_not_found": sum(r.get("nutrition_status") == "NOT_FOUND" for r in rows),
            "evidence_rows": len(evidence),
            "network_responses": len(network),
            "json_xhr_fetch_responses": len(network_json),
        },
        "coverage": {field: base.coverage(rows, field) for field in fields},
        "nutrition_field_coverage": {field: base.coverage(rows, field) for field in nutrition_fields},
        "network_json_candidates": network_json[:50],
        "sample": [r for r in rows if not r.get("fetch_error")][:10],
        "provenance_note": "Every populated product field in this dataset was observed directly on carrefour.es in a real browser session. Third-party data may seed candidate URLs only and is never copied as Carrefour evidence.",
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    return 0


async def page_sleep(seconds: float):
    await asyncio.sleep(seconds)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="carrefour-first-party-browser-inventory")
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--seed-jsonl", action="append", default=[])
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--delay", type=float, default=8.0)
    ap.add_argument("--max-products", type=int, default=0)
    ap.add_argument("--rotate", action="store_true")
    ap.add_argument("--stop-after-blocks", type=int, default=1)
    ap.add_argument("--network-body-limit", type=int, default=200000)
    args = ap.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
