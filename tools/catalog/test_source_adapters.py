import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from mercadona_label_evidence import collect_label_images, nutrition_image_candidates
from mercadona_weekly_catalog_adapter import WeeklyCatalogProduct, is_non_food_product, stratified_sample
from openfoodfacts_adapter import fetch_product, to_candidate, USER_AGENT
from nutrition_resolver import ProductIdentity, resolve


class SourceAdaptersTest(unittest.TestCase):
    def test_off_by_gtin_snapshots_and_resolves(self):
        payload={
            "status":1,
            "product":{
                "product_name_es":"Avena Crunchy Cacao",
                "brands":"Hacendado",
                "quantity":"400 g",
                "ingredients_text_es":"Copos de avena, cacao",
                "nutriments":{
                    "energy-kcal_100g":393,
                    "fat_100g":6.4,
                    "carbohydrates_100g":65,
                    "proteins_100g":13,
                    "fiber_100g":8,
                }
            }
        }
        seen={}
        def transport(url,headers,timeout):
            seen.update(url=url,headers=headers,timeout=timeout)
            return json.dumps(payload).encode()
        with tempfile.TemporaryDirectory() as td:
            fetched=fetch_product("8402001015205",snapshot_dir=td,transport=transport)
            self.assertTrue(fetched.found)
            self.assertTrue(Path(fetched.snapshot_path).exists())
            self.assertIn("User-Agent",seen["headers"])
            self.assertEqual(seen["headers"]["User-Agent"],USER_AGENT)
            candidate=to_candidate(fetched)
            self.assertTrue(candidate.redistribution_allowed)
            self.assertEqual(candidate.upstream_license,"ODbL")
            result=resolve(ProductIdentity("Cereales avena Crunchy Hacendado de cacao",brand="Hacendado",gtin="8402001015205",format="400 g"),[candidate])
            self.assertEqual(result.status,"RESOLVED")
            self.assertEqual(result.level,"MATCHED")

    def test_off_404_is_normal_not_found(self):
        def transport(url, headers, timeout):
            raise HTTPError(url, 404, "Not Found", hdrs=None, fp=None)
        fetched = fetch_product("8480000302007", transport=transport)
        self.assertFalse(fetched.found)
        self.assertIsNone(to_candidate(fetched))

    def test_off_rejects_invalid_gtin_before_network(self):
        with self.assertRaises(ValueError):
            fetch_product("abc",transport=lambda *_: b"{}")

    def test_mercadona_images_are_build_only_label_evidence(self):
        images=[
            {"zoom":"https://img.example/front.jpg"},
            {"large":"https://img.example/back-label.jpg"},
            "https://img.example/side.jpg",
            {"url":"not-a-url"},
        ]
        with tempfile.TemporaryDirectory() as td:
            evidence=collect_label_images(retailer_sku="5002",product_name="Arroz basmati aromático Hacendado",images=images,source_page="https://tienda.mercadona.es/product/5002/x",snapshot_dir=td,observed_at="2026-08-17T12:00:00Z")
            self.assertEqual(len(evidence),3)
            self.assertTrue(all(not x.redistribution_allowed for x in evidence))
            self.assertTrue(all(x.purpose=="PACK_LABEL_CANDIDATE" for x in evidence))
            self.assertEqual(len(nutrition_image_candidates(evidence)),3)
            self.assertTrue(all(Path(x.snapshot_path).exists() for x in evidence))

    def test_non_food_merchandise_is_excluded_from_food_sampling(self):
        def product(pid, name):
            return WeeklyCatalogProduct(
                product_id=pid, ean=None, name=name, brand="Hacendado", legal_name=None,
                ingredients=None, family="Panadería y pastelería", subcategory="Panadería y pastelería",
                category_key="Panadería y pastelería", payload={}, photos=(), observed_at="2026-08-17T00:00:00Z",
            )
        candle=product("1","Vela de cumpleaños 6 Hacendado")
        cake=product("2","Bizcocho de chocolate Hacendado")
        self.assertTrue(is_non_food_product(candle))
        self.assertFalse(is_non_food_product(cake))
        sampled=stratified_sample([candle,cake],size=2,per_category_cap=5)
        self.assertEqual([p.product_id for p in sampled],["2"])


if __name__=="__main__": unittest.main()
