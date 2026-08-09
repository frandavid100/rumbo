package es.david.rumbo.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WeeklyPlannerTest {
    private val chicken = Food(
        id = 1,
        name = "Pollo",
        category = FoodCategory.PROTEIN,
        calories = 100.0,
        fatGrams = 2.0,
        carbohydrateGrams = 0.0,
        proteinGrams = 20.0,
        fiberGrams = 0.0
    )
    private val rice = Food(
        id = 2,
        name = "Arroz",
        category = FoodCategory.CARBOHYDRATE,
        calories = 350.0,
        fatGrams = 1.0,
        carbohydrateGrams = 75.0,
        proteinGrams = 8.0,
        fiberGrams = null
    )

    @Test
    fun oneMealCanApplyToSeveralDays() {
        val meal = PlannedMeal(
            id = 10,
            type = MealType.MORNING_SNACK,
            days = setOf(WeekDay.MONDAY, WeekDay.TUESDAY, WeekDay.WEDNESDAY),
            items = listOf(PlannedFood(chicken.id, 150.0))
        )

        assertTrue(meal.isValid())
        assertEquals(3, meal.days.size)
    }

    @Test
    fun nutritionUsesThePlannedAmount() {
        val meal = PlannedMeal(
            id = 10,
            type = MealType.LUNCH,
            days = setOf(WeekDay.MONDAY),
            items = listOf(PlannedFood(chicken.id, 150.0), PlannedFood(rice.id, 50.0))
        )

        val total = meal.nutrition(listOf(chicken, rice).associateBy { it.id })

        assertEquals(325.0, total.calories, 0.001)
        assertEquals(34.0, total.proteinGrams, 0.001)
        assertEquals(37.5, total.carbohydrateGrams, 0.001)
        assertTrue(total.isComplete)
    }

    @Test
    fun missingNutritionalDataMarksTheTotalAsIncomplete() {
        val incomplete = rice.copy(calories = null)
        val meal = PlannedMeal(
            id = 10,
            type = MealType.DINNER,
            days = setOf(WeekDay.SUNDAY),
            items = listOf(PlannedFood(incomplete.id, 100.0))
        )

        assertFalse(meal.nutrition(mapOf(incomplete.id to incomplete)).isComplete)
    }

    @Test
    fun duplicateIngredientsOrEmptyDaysAreInvalid() {
        val duplicated = PlannedMeal(
            id = 10,
            type = MealType.DINNER,
            days = setOf(WeekDay.SUNDAY),
            items = listOf(PlannedFood(chicken.id, 100.0), PlannedFood(chicken.id, 50.0))
        )
        val noDays = duplicated.copy(days = emptySet(), items = listOf(PlannedFood(chicken.id, 100.0)))

        assertFalse(duplicated.isValid())
        assertFalse(noDays.isValid())
    }
}
