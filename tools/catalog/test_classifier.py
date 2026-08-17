import unittest
from classifier import ProductFeatures, classify

class ClassifierGoldenTest(unittest.TestCase):
    def assertRoles(self, f, nroles=(), croles=(), ctype=None, classified=True):
        r=classify(f)
        if ctype is not None:
            self.assertEqual(r.culinary_type.value if r.culinary_type else None, ctype)
        self.assertTrue(set(nroles) <= {x.value for x in r.nutritional_roles})
        self.assertTrue(set(croles) <= {x.value for x in r.culinary_roles})
        self.assertEqual(r.classified, classified, (f.name, r.review_reasons))
        return r

    def test_authorised_examples(self):
        self.assertRoles(ProductFeatures('Lentejas cocidas', calories=116,protein_g=9,carbohydrate_g=20,fat_g=.4), ['PRIMARY_CARBOHYDRATE','COMPLEMENTARY_PROTEIN'], ['PLATE_CENTER','PLATE_BASE'], 'LEGUME')
        self.assertRoles(ProductFeatures('Queso curado', calories=400,protein_g=25,carbohydrate_g=1,fat_g=33), ['COMPLEMENTARY_PROTEIN','COMPLEMENTARY_FAT'], ['TOPPING','SANDWICH_FILLING','STANDALONE'], 'CHEESE')
        self.assertRoles(ProductFeatures('Plátano', calories=89,protein_g=1.1,carbohydrate_g=23,fat_g=.3), ['FRUIT','COMPLEMENTARY_CARBOHYDRATE'], ['STANDALONE','DESSERT'], 'FRUIT')

    def test_hard_relations(self):
        cereal=self.assertRoles(ProductFeatures('Corn flakes',calories=360,protein_g=7,carbohydrate_g=80,fat_g=1.5), ['PRIMARY_CARBOHYDRATE'], ['CEREAL_MIX_IN'], 'BREAKFAST_CEREAL')
        self.assertIn({'source_role':'CEREAL_MIX_IN','intensity':'REQUIRE','target_role':'CEREAL_BASE','hard':True}, cereal.relations)
        oil=self.assertRoles(ProductFeatures('Aceite de oliva virgen extra',calories=822,protein_g=0,carbohydrate_g=0,fat_g=91), ['CONCENTRATED_FAT'], ['COOKING_MEDIUM'], 'CULINARY_OIL')
        self.assertIn({'source_role':'COOKING_MEDIUM','intensity':'FORBID','target_role':'ALONE','hard':True}, oil.relations)

    def test_current_sample_semantics(self):
        cases=[
            (ProductFeatures('Arroz basmati',calories=353,protein_g=9,carbohydrate_g=78,fat_g=.6),'DRY_RICE',['PRIMARY_CARBOHYDRATE']),
            (ProductFeatures('Leche semidesnatada',calories=46,protein_g=3.1,carbohydrate_g=4.8,fat_g=1.6),'MILK_BASE',['COMPLEMENTARY_PROTEIN','COMPLEMENTARY_CARBOHYDRATE']),
            (ProductFeatures('Huevos',calories=143,protein_g=12.6,carbohydrate_g=.7,fat_g=9.5),'MAIN_EGG',['PRIMARY_PROTEIN']),
            (ProductFeatures('Filete de salmón',calories=182,protein_g=18.4,carbohydrate_g=0,fat_g=12),'MAIN_FISH',['PRIMARY_PROTEIN']),
            (ProductFeatures('Tomates',calories=21,protein_g=.9,carbohydrate_g=3.5,fat_g=.2),'VEGETABLE',['VEGETABLE']),
        ]
        for f,t,n in cases:
            with self.subTest(f.name): self.assertRoles(f,n,ctype=t)

    def test_ambiguous_and_incomplete_go_to_review(self):
        a=classify(ProductFeatures('Preparado alimenticio sabor mediterráneo',calories=200,protein_g=6,carbohydrate_g=20,fat_g=10))
        self.assertFalse(a.classified); self.assertIn('UNKNOWN_CULINARY_TYPE',a.review_reasons)
        b=classify(ProductFeatures('Arroz basmati'))
        self.assertFalse(b.classified); self.assertIn('INCOMPLETE_CORE_NUTRITION',b.review_reasons)

if __name__=='__main__': unittest.main()
