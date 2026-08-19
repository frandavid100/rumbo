from pathlib import Path
p=Path('app/src/test/java/es/david/rumbo/logic/CertifiedDayWitnessAraRegressionTest.kt')
t=p.read_text()
old='''    private val foods = listOf(\n'''
portion='''    private val portionBasisById = mapOf(\n        5751811545638569543L to 150.0,\n        5304878835083443904L to 150.0,\n        5138918923368881607L to 170.0,\n        4713451237391941996L to 150.0,\n        5998252704584821415L to 100.0,\n        4912645548334196354L to 100.0,\n        5065604127361444435L to 80.0,\n        4374284991780745501L to 80.0,\n        4530255594904942386L to 250.0,\n        5427737837577403981L to 250.0,\n        4824921464295006360L to 30.0,\n        5863259172627146722L to 250.0,\n        4042487276430228545L to 10.0,\n        4927534216171556707L to 200.0,\n        4108023238282100017L to 200.0,\n        5409764689805397597L to 200.0,\n        4359402894918143880L to 150.0,\n        4373007081554746702L to 80.0,\n        5412212443169419885L to 200.0,\n        5803238462349753934L to 200.0,\n        4494907683069959481L to 200.0,\n        5466605370625528297L to 200.0,\n        4825073144419713243L to 200.0,\n        5273024687756059532L to 200.0\n    )\n\n    private val foods = listOf(\n'''
if t.count(old)!=1: raise SystemExit(f'foods start {t.count(old)}')
t=t.replace(old,portion,1)
old2=''') .associateBy { it.id }'''
# actual source has no space; use exact alternate
if old2 not in t:
    old2=''').associateBy { it.id }'''
new2=''').map { food ->\n        food.copy(portionBasisGrams = portionBasisById[food.id])\n    }.associateBy { it.id }'''
if t.count(old2)!=1: raise SystemExit(f'foods end {t.count(old2)}')
t=t.replace(old2,new2,1)
marker='''    @Test\n    fun araReachesCompleteFromHerExistingViableWitness() {'''
if t.count(marker)!=1: raise SystemExit('test marker')
# append second test before final class brace
insert='''\n    @Test\n    fun araCanAdvanceFromHerCertifiedCompleteDayTowardLevel3WithoutFalseInsufficiency() {\n        val complete = CertifiedDayWitnessEvaluator.findCompleteDay(\n            rules = rules,\n            foodsById = foods,\n            dishesById = emptyMap(),\n            recommendation = target,\n            mealShares = MealDistributionPolicy.defaults,\n            baselineWitness = baseline\n        ).witness\n        assertNotNull(complete)\n\n        val result = CulinarilySatisfactoryDaySearch.find(\n            rules = rules,\n            foodsById = foods,\n            dishesById = emptyMap(),\n            recommendation = target,\n            mealShares = MealDistributionPolicy.defaults,\n            baselineCompleteWitness = complete\n        )\n        val detail = result.diagnostic?.issues?.joinToString(" | ") { issue ->\n            "${issue.mealType}:${issue.kind}:${issue.foodName}:${issue.roles.joinToString()}"\n        }.orEmpty()\n        assertNotNull("Ara no alcanzó nivel 3. Diagnóstico: $detail", result.witness)\n        assertTrue(\n            CulinarySatisfactionEvaluator.isCulinarilySatisfactory(\n                result.witness!!, rules, foods, emptyMap(), target, MealDistributionPolicy.defaults\n            )\n        )\n    }\n'''
idx=t.rfind('\n}')
if idx<0: raise SystemExit('class end')
t=t[:idx]+insert+t[idx:]
p.write_text(t)
print('Regresión Ara nivel 3 añadida')
