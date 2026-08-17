import unittest

from classifier import ProductFeatures
from classifier_quality import classify, classify_type


class ClassifierQualityTests(unittest.TestCase):
    def t(self, name, family="", calories=200, protein=10, carb=10, fat=10):
        return ProductFeatures(name=name, family=family, calories=calories, protein_g=protein, carbohydrate_g=carb, fat_g=fat)

    def test_tuna_in_oil_is_fish(self):
        f = self.t("Atún en aceite de oliva Ribeira 650 g", "Conservas, caldos y cremas")
        self.assertEqual(classify_type(f).value, "MAIN_FISH")

    def test_rice_vinegar_is_sauce(self):
        f = self.t("Vinagre de arroz Carrefour Sensation 25 cl", "Aceite, especias y salsas")
        self.assertEqual(classify_type(f).value, "SAUCE")

    def test_jam_is_spread_not_fruit(self):
        f = self.t("Mermelada de fresa Carrefour 410 g", "Azúcar, caramelos y chocolate")
        self.assertEqual(classify_type(f).value, "SPREAD")

    def test_fish_al_huevo_is_fish(self):
        f = self.t("Filetes de merluza al huevo Pescanova 400 g", "Marisco y pescado")
        self.assertEqual(classify_type(f).value, "MAIN_FISH")

    def test_bolognese_pasta_is_prepared_and_reviewed(self):
        f = self.t("Macarrones boloñesa Carrefour El Mercado 280 g", "Arroz, legumbres y pasta")
        result = classify(f)
        self.assertEqual(result.culinary_type.value, "PREPARED_DISH")
        self.assertFalse(result.classified)
        self.assertIn("PREPARED_DISH_NEEDS_PORTION_REVIEW", result.review_reasons)

    def test_arroz_a_banda_is_prepared(self):
        f = self.t("Arroz a banda con gambas Carretilla 250 g", "Marisco y pescado")
        self.assertEqual(classify_type(f).value, "PREPARED_DISH")

    def test_arroz_para_paella_stays_dry_rice(self):
        f = self.t("Arroz bomba para paella categoría extra Carrefour 1 kg", "Arroz, legumbres y pasta")
        self.assertEqual(classify_type(f).value, "DRY_RICE")

    def test_broth_is_not_main_meat(self):
        f = self.t("Caldo casero de carne Gallina Blanca 1 l", "Conservas, caldos y cremas")
        self.assertEqual(classify_type(f).value, "PREPARED_DISH")

    def test_impossible_nutrition_blocks_classification(self):
        f = self.t("Pasta seca 500 g", "Arroz, legumbres y pasta", calories=350, protein=500, carb=70, fat=2)
        result = classify(f)
        self.assertFalse(result.classified)
        self.assertIn("PROTEIN_OUT_OF_RANGE", result.review_reasons)


if __name__ == "__main__":
    unittest.main()
