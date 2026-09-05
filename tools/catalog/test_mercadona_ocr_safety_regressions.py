import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mercadona_neural_ocr_wave import (
    _fuse_declared_only_readings,
    _ocr_targets,
    _should_run_easyocr_rescue,
)
from nutrition_label_reader import read_nutrition_label
from nutrition_ocr_ensemble import ParsedOCRReading, fuse_ocr_readings


def _observed_reading(parsed, confidence):
    return SimpleNamespace(parsed=parsed, extraction=SimpleNamespace(confidence=confidence))


class MercadonaOCRSafetyRegressionsTest(unittest.TestCase):
    def test_no_visual_region_falls_back_to_full_back_image(self):
        # Real 256-product validation showed a material class of packaged foods
        # whose rear label contains nutrition text but no sufficiently ruled table
        # for the morphology detector. A detector miss must not become a hard OCR
        # miss: retry the same official rear-label image, while keeping the normal
        # independent-engine/parser/coherence acceptance gates unchanged.
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "back-label.jpg"
            image_path.write_bytes(b"fixture")
            targets = _ocr_targets(image_path, [])
        self.assertEqual(len(targets), 1)
        kind, target_path, region = targets[0]
        self.assertEqual(kind, "full_back_image")
        self.assertEqual(target_path, image_path)
        self.assertIsNone(region)

    def test_declared_only_fallback_can_ignore_noncredible_review_noise(self):
        # A third independent family is useful only if it can corroborate a clean
        # Paddle reading without being vetoed by a Tesseract layout that already
        # failed Rumbo's own deterministic energy/macro validation. REVIEW is not
        # positive evidence and must not be allowed to poison two independently
        # DECLARED, matching observations.
        clean = read_nutrition_label("""Información nutricional por 100 g
Valor energético 711 kJ / 170 kcal
Grasas 10 g
Hidratos de carbono 0.8 g
Proteínas 19 g
Sal 0.3 g
""", extraction_confidence=.98)
        noisy = read_nutrition_label("""Información nutricional por 100 g
Valor energético 711 kJ / 170 kcal
Grasas 90 g
Hidratos de carbono 0.8 g
Proteínas 19 g
Sal 0.3 g
""", extraction_confidence=.92)
        self.assertEqual(clean.status, "DECLARED")
        self.assertEqual(noisy.status, "REVIEW")
        readings = (
            ("paddleocr", "paddleocr", clean, .98),
            ("easyocr", "easyocr", clean, .96),
            ("tesseract-psm6", "tesseract", noisy, .92),
        )
        raw = fuse_ocr_readings(
            ParsedOCRReading(strategy, result, confidence, family)
            for strategy, family, result, confidence in readings
        )
        self.assertEqual(raw.status, "REVIEW")
        strict = _fuse_declared_only_readings(readings, "visual_region")
        self.assertEqual(strict.status, "DECLARED", strict)
        self.assertEqual(strict.independent_engine_families, 2)
        self.assertEqual(strict.corroborated_fields, 4)

    def test_declared_only_fallback_keeps_credible_engine_conflict(self):
        clean = read_nutrition_label("""Información nutricional por 100 g
Valor energético 711 kJ / 170 kcal
Grasas 10 g
Hidratos de carbono 0.8 g
Proteínas 19 g
Sal 0.3 g
""", extraction_confidence=.98)
        conflicting = read_nutrition_label("""Información nutricional por 100 g
Valor energético 690 kJ / 165 kcal
Grasas 5 g
Hidratos de carbono 10 g
Proteínas 20 g
Sal 0.3 g
""", extraction_confidence=.94)
        self.assertEqual(clean.status, "DECLARED")
        self.assertEqual(conflicting.status, "DECLARED")
        readings = (
            ("paddleocr", "paddleocr", clean, .98),
            ("easyocr", "easyocr", clean, .96),
            ("tesseract-psm6", "tesseract", conflicting, .94),
        )
        strict = _fuse_declared_only_readings(readings, "visual_region")
        self.assertEqual(strict.status, "REVIEW")
        self.assertTrue(any(reason.startswith("OCR_FIELD_CONFLICT") for reason in strict.reasons))

    def test_impossible_partial_calories_do_not_enter_ensemble_evidence(self):
        # Observed Tesseract failure on a real Mercadona back label: the printed
        # `442 kJ / 106 kcal` was linearised as `442/4106`, while other rows
        # remained incomplete. Partial parses must reject the impossible 4106
        # before the value can contaminate an otherwise valid ensemble.
        observed = """Información nutricional por 100 g
Valor energético 442 kJ / 4106 kcal
Grasas 1.8 g
Hidratos de carbono
Proteínas 22 g
Sal 0.16 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.97)
        self.assertEqual(result.status, "REVIEW")
        self.assertNotIn("calories", result.nutrition or {})
        self.assertIn("IMPOSSIBLE_CALORIES", result.reasons)

    def test_impossible_partial_macro_does_not_enter_ensemble_evidence(self):
        observed = """Información nutricional por 100 g
Valor energético 442 kJ / 106 kcal
Grasas 1.8 g
Hidratos de carbono
Proteínas 222 g
Sal 0.16 g
"""
        result = read_nutrition_label(observed, extraction_confidence=.97)
        self.assertEqual(result.status, "REVIEW")
        self.assertNotIn("protein_g", result.nutrition or {})
        self.assertIn("IMPOSSIBLE_PROTEIN_G", result.reasons)

    def test_ingredient_fat_percentage_cannot_shadow_explicit_nutrition_row(self):
        # Observed PP-OCR output for Mercadona product 15101. The image OCR is
        # very high confidence, but the package has no explicit nutrition-section
        # heading. The old generic `grasa` search matched `materia grasa láctea`
        # in the ingredients and borrowed `Cacao: 31%`, silently replacing the
        # actual later `Grasas/Lípidos\n35 g` row. Macro labels must be row-like.
        observed = """CHOCOLATE EXTRAFINO CON LECHE
INGREDIENTES
Azúcar. leche entera en polvo. manteca de cacao. pasta de cacao.
leche descremada en polvo. materia grasa láctea anhidra. emulgente:
lecitinas. aroma. Cacao: 31% mínimo.
100g
Valor
2320 kJ
Energético/Energia 556 kcal
Grasas/Lípidos
35 g
1.6 g
de las cuales/dos quais:
22g
- Saturadas/Saturados
1.0 g
Hidratos de Carbono
50g
2.2g
de los cuales/dos quais:
49 g
2.2g
- Azúcares/Açúcares
Proteínas
9.3 g
Sal
0.2g
"""
        result = read_nutrition_label(observed, extraction_confidence=.98)
        self.assertEqual(result.status, "DECLARED", result)
        self.assertEqual(result.nutrition, {
            "calories": 556.0,
            "fat_g": 35.0,
            "carbohydrate_g": 50.0,
            "protein_g": 9.3,
        })

    def test_one_explicit_basis_is_enough_when_all_core_fields_are_independently_corroborated(self):
        # Observed on Mercadona product 2689: Paddle reads the explicit `100 g`
        # basis and all four macros, while Tesseract independently reads the same
        # four values but loses only the basis glyph. There is no competing basis.
        with_basis = read_nutrition_label("""Información nutricional por 100 g
Valor energético 711 kJ / 170 kcal
Grasas 10 g
Hidratos de carbono 0.8 g
Proteínas 19 g
Sal 0.3 g
""", extraction_confidence=.98)
        without_basis = read_nutrition_label("""Información nutricional
Valor energético 711 kJ / 170 kcal
Grasas 10 g
Hidratos de carbono 0.8 g
Proteínas 19 g
Sal 0.3 g
""", extraction_confidence=.96)
        self.assertEqual(with_basis.status, "DECLARED")
        self.assertEqual(without_basis.status, "REVIEW")

        fused = fuse_ocr_readings((
            ParsedOCRReading("paddleocr:visual-region", with_basis, .98, "paddleocr"),
            ParsedOCRReading("tesseract-psm11:visual-region", without_basis, .96, "tesseract"),
        ))
        self.assertEqual(fused.status, "DECLARED", fused)
        self.assertEqual(fused.basis, "100_g")
        self.assertEqual(fused.corroborated_fields, 4)
        self.assertEqual(fused.independent_engine_families, 2)

    def test_conflicting_explicit_bases_still_force_review(self):
        per_100g = read_nutrition_label("""Información nutricional por 100 g
Valor energético 711 kJ / 170 kcal
Grasas 10 g
Hidratos de carbono 0.8 g
Proteínas 19 g
Sal 0.3 g
""", extraction_confidence=.98)
        per_100ml = read_nutrition_label("""Información nutricional por 100 ml
Valor energético 711 kJ / 170 kcal
Grasas 10 g
Hidratos de carbono 0.8 g
Proteínas 19 g
Sal 0.3 g
""", extraction_confidence=.98)
        fused = fuse_ocr_readings((
            ParsedOCRReading("paddleocr", per_100g, .98, "paddleocr"),
            ParsedOCRReading("tesseract", per_100ml, .98, "tesseract"),
        ))
        self.assertEqual(fused.status, "REVIEW")
        self.assertIn("OCR_BASIS_CONFLICT", fused.reasons)

    def test_easyocr_rescue_routes_clean_complementary_partial_tuple(self):
        # Product 13240 exposed a systematic routing hole: Paddle and Tesseract
        # together recover a coherent complete 100 g tuple, with two fields already
        # corroborated, but neither individual reading is parser-DECLARED. EasyOCR
        # may be used as a third independent observation without relaxing acceptance.
        paddle = read_nutrition_label("""Información nutricional por 100 g
Valor energético 699 kJ / 167 kcal
Grasas 12 g
Proteínas 7.9 g
Sal 0.7 g
""", extraction_confidence=.98)
        tesseract = read_nutrition_label("""Información nutricional por 100 g
Valor energético 699 kJ / 167 kcal
Hidratos de carbono 6.39 g
Proteínas 7.9 g
Sal 0.7 g
""", extraction_confidence=.94)
        readings = (
            ("paddleocr", "paddleocr", _observed_reading(paddle, .98)),
            ("tesseract-psm6", "tesseract", _observed_reading(tesseract, .94)),
        )
        self.assertTrue(_should_run_easyocr_rescue(readings, "visual_region"))

    def test_easyocr_rescue_rejects_cross_engine_field_conflict(self):
        paddle = read_nutrition_label("""Información nutricional por 100 g
Valor energético 954 kJ / 228 kcal
Grasas 13 g
Hidratos de carbono 14 g
Proteínas 12 g
""", extraction_confidence=.98)
        tesseract = read_nutrition_label("""Información nutricional por 100 g
Valor energético 954 kJ / 228 kcal
Grasas 13 g
Hidratos de carbono 89 g
Proteínas 12 g
""", extraction_confidence=.94)
        readings = (
            ("paddleocr", "paddleocr", _observed_reading(paddle, .98)),
            ("tesseract-psm6", "tesseract", _observed_reading(tesseract, .94)),
        )
        self.assertFalse(_should_run_easyocr_rescue(readings, "visual_region"))

    def test_easyocr_rescue_requires_complete_union_and_explicit_basis(self):
        incomplete_a = read_nutrition_label("""Información nutricional por 100 g
Valor energético 753 kJ / 180 kcal
Grasas 12 g
Proteínas 1.7 g
""", extraction_confidence=.98)
        incomplete_b = read_nutrition_label("""Información nutricional por 100 g
Valor energético 753 kJ / 180 kcal
Proteínas 1.7 g
Sal 0.7 g
""", extraction_confidence=.94)
        incomplete = (
            ("paddleocr", "paddleocr", _observed_reading(incomplete_a, .98)),
            ("tesseract-psm6", "tesseract", _observed_reading(incomplete_b, .94)),
        )
        self.assertFalse(_should_run_easyocr_rescue(incomplete, "visual_region"))

        no_basis_a = read_nutrition_label("""Información nutricional
Valor energético 753 kJ / 180 kcal
Grasas 12 g
Hidratos de carbono 6.3 g
Proteínas 1.7 g
""", extraction_confidence=.98)
        no_basis_b = read_nutrition_label("""Información nutricional
Valor energético 753 kJ / 180 kcal
Grasas 12 g
Hidratos de carbono 6.3 g
Proteínas 1.7 g
""", extraction_confidence=.94)
        no_basis = (
            ("paddleocr", "paddleocr", _observed_reading(no_basis_a, .98)),
            ("tesseract-psm6", "tesseract", _observed_reading(no_basis_b, .94)),
        )
        self.assertFalse(_should_run_easyocr_rescue(no_basis, "visual_region"))


if __name__ == "__main__":
    unittest.main()
