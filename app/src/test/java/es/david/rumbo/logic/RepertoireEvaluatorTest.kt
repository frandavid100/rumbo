package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RepertoireEvaluatorTest {
    private val recommendation = Recommendation(2000, 140, 220, 65, "")
    private val lunchOnly = MealType.entries.associateWith { if (it == MealType.LUNCH) 1.0 else 0.0 }

    @Test
    fun inactiveAndUnprogrammedFoodsDoNotCount() {
        val foods = listOf(
            food(1, "Pollo", FoodCategory.PROTEIN, 165.0, 31.0, 0.0, 3.6),
            food(2, "Arroz", FoodCategory.CARBOHYDRATE, 360.0, 7.0, 79.0, 0.6),
            food(3, "Nueces", FoodCategory.FAT, 650.0, 15.0, 10.0, 60.0)
        ).associateBy { it.id }
        val result = RepertoireEvaluator.evaluate(
            rules = listOf(
                rule(1),
                rule(2).copy(isActive = false),
                rule(3).copy(allowedMealTypes = emptySet())
            ),
            foodsById = foods,
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = lunchOnly
        )

        assertEquals(1, result.metrics.availableFoods)
        assertEquals(1, result.coverage.single().alternatives)
        assertTrue(result.reactivationFoodIds.contains(2L))
    }

    @Test
    fun missingMealCoverageIsReportedAsARealConstraint() {
        val food = food(1, "Arroz", FoodCategory.CARBOHYDRATE, 360.0, 7.0, 79.0, 0.6)
        val shares = MealType.entries.associateWith {
            when (it) {
                MealType.LUNCH, MealType.DINNER -> .5
                else -> 0.0
            }
        }
        val result = RepertoireEvaluator.evaluate(
            listOf(rule(1)), mapOf(1L to food), emptyMap(), recommendation, shares
        )

        assertEquals(RepertoireStatus.INSUFFICIENT, result.status)
        assertTrue(result.limitingFactors.any { it.contains("cena", ignoreCase = true) })
    }

    @Test
    fun redundantProductsDoNotCreateFalseRobustness() {
        val foods = (1L..10L).map {
            food(it, "Yogur $it", FoodCategory.PROTEIN, 120.0, 10.0, 8.0, 5.0)
        }.associateBy { it.id }
        val result = RepertoireEvaluator.evaluate(
            foods.keys.map(::rule), foods, emptyMap(),
            Recommendation(1200, 100, 80, 55, ""), lunchOnly
        )

        assertEquals(1, result.metrics.distinctNutritionProfiles)
        assertNotEquals(RepertoireStatus.ROBUST, result.status)
    }

    @Test
    fun practicalWholeUnitsAreUsedByTheRealGenerator() {
        val yoghurt = food(1, "Yogur", FoodCategory.PROTEIN, 100.0, 10.0, 10.0, 2.0)
            .copy(unitName = "vasito", unitAmount = 120.0, wholeUnitsOnly = true)
        val result = RepertoireEvaluator.evaluate(
            listOf(rule(1).copy(preferredGrams = 120.0, minimumFactor = .5, maximumFactor = 2.0)),
            mapOf(1L to yoghurt), emptyMap(), Recommendation(240, 24, 24, 5, ""), lunchOnly
        )

        assertTrue(result.metrics.evaluatedSolutions > 0)
        assertEquals(0.0, result.nutrition.getValue(NutrientKind.CALORIES).bestAchievable % 120.0, .001)
    }

    private fun rule(id: Long, frequency: PlanningFrequency = PlanningFrequency.NORMAL) = PlanningRule(
        itemKind = PlannedItemKind.FOOD,
        itemId = id,
        allowedMealTypes = setOf(MealType.LUNCH),
        frequency = frequency,
        preferredGrams = 100.0
    )

    private fun food(
        id: Long,
        name: String,
        category: FoodCategory,
        calories: Double,
        protein: Double,
        carbs: Double,
        fat: Double
    ) = Food(id, name, category, calories, fat, carbs, protein, 0.0)
}
