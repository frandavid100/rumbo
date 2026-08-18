package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CertifiedDayWitnessLevel1Test {
    private val recommendation = Recommendation(2000, 100, 250, 67, "test")

    private fun food(id: Long, name: String, kcal: Double, protein: Double, carbs: Double, fat: Double) =
        Food(
            id = id,
            name = name,
            category = when {
                protein >= carbs && protein >= fat -> FoodCategory.PROTEIN
                fat >= carbs -> FoodCategory.FAT
                else -> FoodCategory.CARBOHYDRATE
            },
            calories = kcal,
            proteinGrams = protein,
            carbohydrateGrams = carbs,
            fatGrams = fat,
            fiberGrams = 2.0,
            culinaryRoles = setOf("STANDALONE")
        )

    @Test
    fun generatorCanSearchOneDayWithoutConstructingTheRestOfTheWeek() {
        val foods = listOf(
            food(1, "A", 200.0, 12.0, 30.0, 4.0),
            food(2, "B", 180.0, 10.0, 25.0, 5.0),
            food(3, "C", 220.0, 15.0, 28.0, 6.0),
            food(4, "D", 190.0, 11.0, 26.0, 5.0)
        ).associateBy { it.id }
        val rules = foods.values.map { f ->
            PlanningRule(
                itemKind = PlannedItemKind.FOOD,
                itemId = f.id,
                allowedMealTypes = MealType.entries.toSet(),
                frequency = PlanningFrequency.NORMAL,
                preferredGrams = 100.0,
                minimumFactor = 0.5,
                maximumFactor = 5.0
            )
        }
        val generated = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = rules,
            history = emptyList(),
            foodsById = foods,
            dishesById = emptyMap(),
            recommendation = recommendation,
            days = setOf(WeekDay.MONDAY)
        )
        assertTrue(generated.meals.isNotEmpty())
        assertEquals(setOf(WeekDay.MONDAY), generated.meals.flatMap { it.days }.toSet())
        assertEquals(1, generated.diagnostics.size)
        assertEquals(WeekDay.MONDAY, generated.diagnostics.single().day)
    }
}
