package es.david.rumbo.logic

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
