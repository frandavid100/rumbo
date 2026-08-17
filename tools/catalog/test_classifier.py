import unittest
from classifier import ProductFeatures, classify, COMPLEMENTARY_THRESHOLDS_PER_SERVING

class Golden(unittest.TestCase):
    def check(self,f,typ,nroles,croles,classified=True):
        r=classify(f)
        self.assertEqual(r.culinary_type.value if r.culinary_type else None,typ)
        self.assertEqual({x.value for x in r.nutritional_roles},set(nroles))
        self.assertEqual({x.value for x in r.culinary_roles},set(croles))
        self.assertEqual(r.classified,classified,(f.name,r.review_reasons))
        return r

    def test_golden_taxonomy(self):
        cases=[
            (ProductFeatures('Queso curado',calories=400,protein_g=25,carbohydrate_g=1,fat_g=33),'CHEESE',{'COMPLEMENTARY_PROTEIN','COMPLEMENTARY_FAT'},{'TOPPING','SANDWICH_FILLING','STANDALONE'}),
            (ProductFeatures('Nueces naturales',calories=654,protein_g=15.2,carbohydrate_g=13.7,fat_g=65.2),'FAT_COMPLEMENT',{'COMPLEMENTARY_FAT'},{'TOPPING','STANDALONE'}),
            (ProductFeatures('Lentejas cocidas',calories=116,protein_g=9,carbohydrate_g=20,fat_g=.4),'LEGUME',{'PRIMARY_CARBOHYDRATE','COMPLEMENTARY_PROTEIN'},{'PLATE_CENTER','PLATE_BASE','SIDE'}),
            (ProductFeatures('Yogur natural 0% pack 6',calories=36,protein_g=4.3,carbohydrate_g=4.5,fat_g=.1),'CREAMY_BASE',{'COMPLEMENTARY_PROTEIN'},{'CEREAL_BASE','POWDER_BASE','STANDALONE','DESSERT'}),
            (ProductFeatures('Pan de molde 100% integral familiar',calories=248,protein_g=8.7,carbohydrate_g=41,fat_g=3.8),'BREAD',{'PRIMARY_CARBOHYDRATE'},{'SANDWICH_BASE','PLATE_BASE','STANDALONE'}),
            (ProductFeatures('Corn flakes',calories=360,protein_g=7,carbohydrate_g=80,fat_g=1.5),'BREAKFAST_CEREAL',{'PRIMARY_CARBOHYDRATE'},{'CEREAL_MIX_IN'}),
            (ProductFeatures('Cacao puro en polvo',calories=350,protein_g=20,carbohydrate_g=15,fat_g=20),'COCOA_POWDER',set(),{'POWDER_MIX_IN','TOPPING'}),
            (ProductFeatures('Proteína en polvo whey',calories=390,protein_g=80,carbohydrate_g=8,fat_g=5),'PROTEIN_POWDER',{'COMPLEMENTARY_PROTEIN'},{'POWDER_MIX_IN'}),
            (ProductFeatures('Aceite de oliva virgen extra',calories=822,protein_g=0,carbohydrate_g=0,fat_g=91),'CULINARY_OIL',{'CONCENTRATED_FAT'},{'COOKING_MEDIUM','SAUCE_DRESSING'}),
            (ProductFeatures('Tomate frito',calories=79,protein_g=1.5,carbohydrate_g=10,fat_g=3.5),'SAUCE',set(),{'SAUCE_DRESSING','TOPPING'}),
            (ProductFeatures('Tomates',calories=21,protein_g=.9,carbohydrate_g=3.5,fat_g=.2),'VEGETABLE',{'VEGETABLE'},{'SIDE','TOPPING'}),
            (ProductFeatures('Filete de salmón',calories=182,protein_g=18.4,carbohydrate_g=0,fat_g=12),'MAIN_FISH',{'PRIMARY_PROTEIN'},{'PLATE_CENTER','SANDWICH_FILLING'}),
            (ProductFeatures('Leche semidesnatada',calories=46,protein_g=3.1,carbohydrate_g=4.8,fat_g=1.6),'MILK_BASE',{'COMPLEMENTARY_PROTEIN','COMPLEMENTARY_CARBOHYDRATE'},{'CEREAL_BASE','POWDER_BASE','BEVERAGE','STANDALONE'}),
            (ProductFeatures('Plátano',calories=89,protein_g=1.1,carbohydrate_g=23,fat_g=.3),'FRUIT',{'FRUIT','COMPLEMENTARY_CARBOHYDRATE'},{'STANDALONE','DESSERT'}),
        ]
        for case in cases:
            with self.subTest(case[0].name): self.check(*case)

    def test_hard_relations(self):
        cereal=classify(ProductFeatures('Corn flakes',calories=360,protein_g=7,carbohydrate_g=80,fat_g=1.5))
        self.assertIn({'source_role':'CEREAL_MIX_IN','intensity':'REQUIRE','target_role':'CEREAL_BASE','hard':True},cereal.relations)
        powder=classify(ProductFeatures('Proteína en polvo whey',calories=390,protein_g=80,carbohydrate_g=8,fat_g=5))
        self.assertIn({'source_role':'POWDER_MIX_IN','intensity':'REQUIRE','target_role':'POWDER_BASE','hard':True},powder.relations)
        oil=classify(ProductFeatures('Aceite de oliva virgen extra',calories=822,protein_g=0,carbohydrate_g=0,fat_g=91))
        self.assertIn({'source_role':'COOKING_MEDIUM','intensity':'FORBID','target_role':'ALONE','hard':True},oil.relations)

    def test_threshold_boundaries_are_serving_based(self):
        self.assertEqual(COMPLEMENTARY_THRESHOLDS_PER_SERVING,{'protein_g':5.0,'carbohydrate_g':10.0,'fat_g':5.0})
        low=classify(ProductFeatures('Yogur natural',calories=60,protein_g=3.3,carbohydrate_g=4,fat_g=3.3))
        self.assertNotIn('COMPLEMENTARY_PROTEIN',{x.value for x in low.nutritional_roles})
        self.assertNotIn('COMPLEMENTARY_FAT',{x.value for x in low.nutritional_roles})
        high=classify(ProductFeatures('Yogur proteico',calories=70,protein_g=3.34,carbohydrate_g=4,fat_g=3.34))
        self.assertIn('COMPLEMENTARY_PROTEIN',{x.value for x in high.nutritional_roles})
        self.assertIn('COMPLEMENTARY_FAT',{x.value for x in high.nutritional_roles})

    def test_multipack_does_not_change_classification(self):
        a=classify(ProductFeatures('Yogur natural 0%',calories=36,protein_g=4.3,carbohydrate_g=4.5,fat_g=.1))
        b=classify(ProductFeatures('Yogur natural 0% pack 6',calories=36,protein_g=4.3,carbohydrate_g=4.5,fat_g=.1))
        self.assertEqual(a.culinary_type.value,b.culinary_type.value)
        self.assertEqual({x.value for x in a.nutritional_roles},{x.value for x in b.nutritional_roles})

    def test_prepared_and_unknown_review(self):
        prepared=classify(ProductFeatures('Lasaña boloñesa preparada',calories=180,protein_g=8,carbohydrate_g=18,fat_g=8))
        self.assertFalse(prepared.classified)
        self.assertEqual(prepared.culinary_type.value,'PREPARED_DISH')
        self.assertIn('PREPARED_DISH_NEEDS_PORTION_REVIEW',prepared.review_reasons)

        unknown=classify(ProductFeatures('Preparado alimenticio sabor mediterráneo',calories=200,protein_g=6,carbohydrate_g=20,fat_g=10))
        self.assertFalse(unknown.classified)
        self.assertIn('UNKNOWN_CULINARY_TYPE',unknown.review_reasons)

    def test_incomplete_review(self):
        r=classify(ProductFeatures('Arroz basmati'))
        self.assertFalse(r.classified)
        self.assertIn('INCOMPLETE_CORE_NUTRITION',r.review_reasons)

if __name__=='__main__': unittest.main()
