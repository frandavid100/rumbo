import tempfile
import unittest
from pathlib import Path

from label_text_extractor import TextExtraction
from mercadona_label_evidence import LabelImageEvidence
from mercadona_label_pipeline import process_label_image
from mercadona_nutrition_reader import OCR_EVIDENCE_LEVEL


class MercadonaLabelPipelineTest(unittest.TestCase):
    def evidence(self):
        return LabelImageEvidence(
            retailer='Mercadona', retailer_sku='23049', product_name='Batido de chocolate Hacendado',
            image_url='https://example.test/label.jpg', image_index=2,
            observed_at='2026-08-17T00:00:00Z', source_page='https://tienda.mercadona.es/product/23049',
            redistribution_allowed=False, purpose='PACK_LABEL_CANDIDATE'
        )

    def test_declared_end_to_end_with_injected_io(self):
        def downloader(url,path,timeout): path.write_bytes(b'image')
        def extractor(path):
            return TextExtraction(
                text='INFORMACION NUTRICIONAL por 100 ml\nValor energetico 256 kJ 61 kcal\nGrasas 0,9 g\nHidratos de carbono 10 g\nProteinas 3,1 g\nSal 0,14 g',
                confidence=.96, engine='fixture', engine_version='1', language='spa')
        result=process_label_image(self.evidence(),gtin='8400000000000',brand='Hacendado',downloader=downloader,extractor=extractor)
        self.assertEqual(result.status,'DECLARED')
        self.assertIsNotNone(result.candidate)
        self.assertEqual(result.candidate.evidence_level, OCR_EVIDENCE_LEVEL)
        self.assertIn(OCR_EVIDENCE_LEVEL, result.candidate.claim)
        self.assertNotIn('DECLARED;', result.candidate.claim)
        self.assertFalse(result.candidate.redistribution_allowed)

    def test_bad_image_never_produces_candidate(self):
        def downloader(url,path,timeout): path.write_bytes(b'image')
        def extractor(path): return TextExtraction('ingredientes leche cacao azucar',.99,'fixture','1','spa')
        result=process_label_image(self.evidence(),downloader=downloader,extractor=extractor)
        self.assertEqual(result.status,'NOT_NUTRITION_LABEL')
        self.assertIsNone(result.candidate)

if __name__=='__main__': unittest.main()
