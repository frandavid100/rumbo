import json
import unittest
from pathlib import Path
from nutrition_resolver import ProductIdentity, NutritionCandidate, resolve, score

FIX = Path(__file__).parent / 'fixtures' / 'nutrition_resolver_probe.json'


def identity(data):
    return ProductIdentity(name=data['name'], brand=data.get('brand'), gtin=data.get('gtin'), format=data.get('format'), ingredients=data.get('ingredients'))


def candidate(data):
    return NutritionCandidate(
        identity=identity(data), nutrition=data['nutrition'], source=data['source'], source_url=data['source_url'],
        source_record_id=data.get('source_record_id'), observed_at=data.get('observed_at'), upstream_license=data.get('upstream_license'),
        redistribution_allowed=data.get('redistribution_allowed', False), source_family=data.get('source_family'), claim=data.get('claim')
    )


class ResolverTest(unittest.TestCase):
    def test_probe(self):
        rows=json.loads(FIX.read_text())
        for row in rows:
            with self.subTest(row['target']['name']):
                result=resolve(identity(row['target']), [candidate(x) for x in row['candidates']], require_publishable=True)
                self.assertEqual(result.status,row['expected_status'],(row['target']['name'],result))

    def test_gtin_conflict_is_fatal(self):
        a=ProductIdentity('Producto Hacendado','Hacendado','11111111')
        b=ProductIdentity('Producto Hacendado','Hacendado','22222222')
        value,reasons=score(a,b)
        self.assertEqual(value,0)
        self.assertIn('GTIN_CONFLICT',reasons)

    def test_two_independent_disagreeing_sources_go_to_review(self):
        target=ProductIdentity('Atún claro al natural Hacendado','Hacendado')
        a=NutritionCandidate(ProductIdentity('Atún claro al natural','Hacendado'),{'calories':79,'fat_g':.6,'carbohydrate_g':.5,'protein_g':18},'A','https://a.example',source_family='A')
        b=NutritionCandidate(ProductIdentity('Atún claro al natural','Hacendado'),{'calories':98,'fat_g':1.2,'carbohydrate_g':.9,'protein_g':21},'B','https://b.example',source_family='B')
        result=resolve(target,[a,b],require_publishable=False)
        self.assertEqual(result.status,'REVIEW')
        self.assertEqual(result.reason,'NUTRITION_CONFLICT')

    def test_publishable_candidate_wins_rights_gate(self):
        target=ProductIdentity('Cereales avena Crunchy Hacendado de cacao','Hacendado','8402001015205')
        c=NutritionCandidate(ProductIdentity('Avena Crunchy Cacao','Hacendado','8402001015205'),{'calories':393,'fat_g':6.4,'carbohydrate_g':65,'protein_g':13},'Open Food Facts','https://world.openfoodfacts.org',upstream_license='ODbL',redistribution_allowed=True,source_family='Open Food Facts')
        result=resolve(target,[c])
        self.assertEqual(result.status,'RESOLVED')
        self.assertTrue(result.publishable)
        self.assertEqual(result.level,'MATCHED')

if __name__=='__main__': unittest.main()
