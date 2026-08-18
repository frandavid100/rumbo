from pathlib import Path

# 1. Replace CertifiedDayWitnessEvaluator with level-aware evaluator + complete search.
p = Path('app/src/main/java/es/david/rumbo/logic/CertifiedDayWitnessEvaluator.kt')
s = p.read_text()
s = s.replace('import es.david.rumbo.model.Food\n', 'import es.david.rumbo.model.Food\nimport es.david.rumbo.model.FoodCategory\nimport es.david.rumbo.model.WeekDay\n')
s = s.replace('        if (witness.level != CertifiedDayLevel.VIABLE || !witness.isStructurallyValid()) return false', '        if (!witness.isStructurallyValid()) return false')
insert = r'''

    /** COMPLETE = viable + fruit in two distinct meals + vegetables in two distinct meals + >=25 g fibre. */
    fun isComplete(
        witness: CertifiedDayWitness,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): Boolean {
        if (witness.level != CertifiedDayLevel.COMPLETE || !isViable(
                witness, rules, foodsById, dishesById, recommendation, mealShares
            )) return false
        return completeCriteria(witness.day, witness.meals, foodsById, dishesById, recommendation)
    }

    fun findCompleteWitness(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): CertifiedDayWitness? {
        val constraints = MenuConstraintModel.fromLegacyData(rules, foodsById, mealShares)
        if (constraints.structuralViolations.isNotEmpty()) return null
        val seeds = listOf(11L, 37L, 89L, 131L, 197L, 251L, 313L, 401L, 509L, 607L, 701L, 809L)
        for (seed in seeds) {
            val generated = runCatching {
                WeeklyMenuGenerator.generate(
                    constraints = constraints,
                    currentMeals = emptyList(),
                    history = emptyList(),
                    foodsById = foodsById,
                    dishesById = dishesById,
                    recommendation = recommendation,
                    seed = seed,
                    days = setOf(WeekDay.MONDAY)
                )
            }.getOrNull() ?: continue
            if (!completeCriteria(WeekDay.MONDAY, generated.meals, foodsById, dishesById, recommendation)) continue
            val candidate = CertifiedDayWitness(
                level = CertifiedDayLevel.COMPLETE,
                seed = seed,
                day = WeekDay.MONDAY,
                meals = generated.meals,
                fingerprint = generated.meals.hashCode()
            )
            if (isComplete(candidate, rules, foodsById, dishesById, recommendation, mealShares)) return candidate
        }
        return null
    }

    private fun completeCriteria(
        day: WeekDay,
        meals: List<es.david.rumbo.model.PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation
    ): Boolean {
        val assessment = MealPlanEvaluator.assessDay(day, meals, foodsById, dishesById, recommendation)
        if (!WeeklyMenuAcceptancePolicy.isDayAcceptable(assessment, meals.mapTo(mutableSetOf()) { it.type })) return false
        if (assessment.actual.fiberGrams < 25.0) return false
        fun mealsContaining(category: FoodCategory): Int = meals.count { meal ->
            val direct = meal.items.any { foodsById[it.foodId]?.category == category }
            val inDish = meal.dishes.any { plannedDish ->
                dishesById[plannedDish.dishId]?.ingredients?.any {
                    foodsById[it.foodId]?.category == category
                } == true
            }
            direct || inDish
        }
        return mealsContaining(FoodCategory.VEGETABLE) >= 2 && mealsContaining(FoodCategory.FRUIT) >= 2
    }
'''
idx = s.rfind('\n}')
s = s[:idx] + insert + s[idx:]
p.write_text(s)

# 2. Wire COMPLETE state/search/persistence into HomeScreen and progress card.
p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()
s = s.replace(
'''    val freshViableWitness = remember(repertoireAssessment) {
        repertoireAssessment?.witness?.let(CertifiedDayWitnessEvaluator::fromMenuWitness)
    }
''',
'''    val freshViableWitness = remember(repertoireAssessment) {
        repertoireAssessment?.witness?.let(CertifiedDayWitnessEvaluator::fromMenuWitness)
    }
    val hasCertifiedViableDay = savedViableWitnessValid ||
        (freshViableWitness != null && repertoireAssessment?.searchStatus == ConstraintSearchStatus.FEASIBLE)
    val savedCompleteWitness = data.activeProfileData?.certifiedDayWitnesses
        ?.firstOrNull { it.level == CertifiedDayLevel.COMPLETE }
    val savedCompleteWitnessValid = remember(
        savedCompleteWitness,
        data.activeProfileData?.planningRules,
        foodsById,
        dishesById,
        recommendation,
        mealShares,
        data.activeProfileData?.culinaryPolicyOverrides,
        data.activeProfileData?.nutritionToleranceSettings
    ) {
        recommendation != null && savedCompleteWitness != null &&
            CertifiedDayWitnessEvaluator.isComplete(
                savedCompleteWitness,
                data.activeProfileData?.planningRules.orEmpty(),
                foodsById,
                dishesById,
                recommendation,
                mealShares
            )
    }
    val freshCompleteWitness by produceState<CertifiedDayWitness?>(
        initialValue = null,
        hasCertifiedViableDay,
        data.activeProfileData?.planningRules,
        foodsById,
        dishesById,
        recommendation,
        mealShares
    ) {
        value = if (hasCertifiedViableDay && recommendation != null && !savedCompleteWitnessValid) {
            withContext(Dispatchers.Default) {
                CertifiedDayWitnessEvaluator.findCompleteWitness(
                    data.activeProfileData?.planningRules.orEmpty(),
                    foodsById,
                    dishesById,
                    recommendation,
                    mealShares
                )
            }
        } else null
    }
''')
# Remove the old duplicate viable declaration and add complete persistence there.
s = s.replace(
'''    val hasCertifiedViableDay = savedViableWitnessValid ||
        (freshViableWitness != null && repertoireAssessment?.searchStatus == ConstraintSearchStatus.FEASIBLE)

    val menuReady''',
'''    LaunchedEffect(savedCompleteWitness, savedCompleteWitnessValid, freshCompleteWitness) {
        when {
            savedCompleteWitnessValid -> Unit
            freshCompleteWitness != null -> onSaveCertifiedDayWitness(freshCompleteWitness!!)
            savedCompleteWitness != null -> onClearCertifiedDayWitness(CertifiedDayLevel.COMPLETE)
        }
    }
    val hasCertifiedCompleteDay = savedCompleteWitnessValid || freshCompleteWitness != null

    val menuReady''', 1)
s = s.replace(
'''                    assessment = repertoireAssessment,
                    hasCertifiedViableDay = hasCertifiedViableDay,
''',
'''                    assessment = repertoireAssessment,
                    hasCertifiedViableDay = hasCertifiedViableDay,
                    hasCertifiedCompleteDay = hasCertifiedCompleteDay,
''', 1)
s = s.replace(
'''private fun RepertoireProgressCard(
    assessment: RepertoireAssessment?,
    hasCertifiedViableDay: Boolean,
''',
'''private fun RepertoireProgressCard(
    assessment: RepertoireAssessment?,
    hasCertifiedViableDay: Boolean,
    hasCertifiedCompleteDay: Boolean,
''', 1)
s = s.replace(
'''        assessment, hasCertifiedViableDay, foods, repertoireFoodIds, planningRules
    ) {
        repertoireProgressTarget(
            assessment, hasCertifiedViableDay, foods, repertoireFoodIds, planningRules
''',
'''        assessment, hasCertifiedViableDay, hasCertifiedCompleteDay, foods, repertoireFoodIds, planningRules
    ) {
        repertoireProgressTarget(
            assessment, hasCertifiedViableDay, hasCertifiedCompleteDay, foods, repertoireFoodIds, planningRules
''', 1)
s = s.replace(
'''private fun repertoireProgressTarget(
    assessment: RepertoireAssessment?,
    hasCertifiedViableDay: Boolean,
''',
'''private fun repertoireProgressTarget(
    assessment: RepertoireAssessment?,
    hasCertifiedViableDay: Boolean,
    hasCertifiedCompleteDay: Boolean,
''', 1)
needle = '''    if (hasCertifiedViableDay || assessment.searchStatus == ConstraintSearchStatus.FEASIBLE) {
'''
replacement = '''    if (hasCertifiedCompleteDay) {
        return 2 to RepertoireProgressTarget(
            "Nivel 2 conseguido: Rumbo ha encontrado y guardado un día completo que, además de ser viable, incluye fruta en al menos dos comidas, verdura en al menos dos comidas y 25 g o más de fibra."
        )
    }

    if (hasCertifiedViableDay || assessment.searchStatus == ConstraintSearchStatus.FEASIBLE) {
'''
assert needle in s
s = s.replace(needle, replacement, 1)
old = '''        return 1 to RepertoireProgressTarget(
            "Nivel 1 conseguido: tu repertorio permite crear un menú viable. Ya tienes cubierta la variedad básica de fruta y verdura; los demás criterios del nivel 2 se evaluarán al completar el motor de menú completo."
        )
'''
new = '''        return 1 to RepertoireProgressTarget(
            "Sigues en el nivel 1: Rumbo todavía no ha encontrado un único día que reúna a la vez fruta en dos comidas, verdura en dos comidas, al menos 25 g de fibra y todos los requisitos de un menú viable. Añadir más opciones de fruta, verdura y alimentos ricos en fibra aumenta las combinaciones posibles."
        )
'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

# 3. Tests for COMPLETE acceptance and fibre rejection.
p = Path('app/src/test/java/es/david/rumbo/logic/CertifiedDayWitnessCompleteTest.kt')
p.write_text(r'''package es.david.rumbo.logic

import es.david.rumbo.model.*
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CertifiedDayWitnessCompleteTest {
    private val target = Recommendation(2000, 100, 250, 67, "test")
    private val mealTypes = MealType.entries

    private fun food(id: Long, category: FoodCategory, fiber: Double) = Food(
        id = id,
        name = "F$id",
        category = category,
        calories = 500.0,
        fatGrams = 16.75,
        carbohydrateGrams = 62.5,
        proteinGrams = 25.0,
        fiberGrams = fiber,
        culinaryRoles = setOf("STANDALONE")
    )

    private fun fixture(fiber: Double): Triple<CertifiedDayWitness, List<PlanningRule>, Map<Long, Food>> {
        val foods = listOf(
            food(1, FoodCategory.FRUIT, fiber),
            food(2, FoodCategory.FRUIT, fiber),
            food(3, FoodCategory.VEGETABLE, fiber),
            food(4, FoodCategory.VEGETABLE, fiber),
            food(5, FoodCategory.PROTEIN, fiber)
        )
        val meals = mealTypes.mapIndexed { index, type ->
            PlannedMeal(
                id = (index + 1).toLong(),
                type = type,
                days = setOf(WeekDay.MONDAY),
                items = listOf(PlannedFood(foods[index].id, 80.0, false))
            )
        }
        val rules = foods.mapIndexed { index, f ->
            PlanningRule(
                itemKind = PlannedItemKind.FOOD,
                itemId = f.id,
                allowedMealTypes = setOf(mealTypes[index]),
                frequency = PlanningFrequency.NORMAL,
                preferredGrams = 80.0,
                minimumFactor = 0.5,
                maximumFactor = 1.5
            )
        }
        return Triple(
            CertifiedDayWitness(CertifiedDayLevel.COMPLETE, 11L, WeekDay.MONDAY, meals),
            rules,
            foods.associateBy { it.id }
        )
    }

    @Test
    fun completeRequiresTwoFruitMealsTwoVegetableMealsAndEnoughFiber() {
        val (witness, rules, foods) = fixture(8.0)
        assertTrue(CertifiedDayWitnessEvaluator.isComplete(
            witness, rules, foods, emptyMap(), target, MealDistributionPolicy.defaults
        ))
    }

    @Test
    fun completeRejectsDayBelowFiberThreshold() {
        val (witness, rules, foods) = fixture(4.0)
        assertFalse(CertifiedDayWitnessEvaluator.isComplete(
            witness, rules, foods, emptyMap(), target, MealDistributionPolicy.defaults
        ))
    }
}
''')
print('Applied COMPLETE day level 2 certification and tests')
