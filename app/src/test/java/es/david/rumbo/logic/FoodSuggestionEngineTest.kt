package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FoodSuggestionEngineTest {
    @Test
    fun excludesRepertoireAndOtherRetailers() {
        val foods = listOf(
            food(1, "Arroz habitual", FoodCategory.CARBOHYDRATE, "Mercadona", 360.0, 7.0, 79.0, 1.0),
            food(2, "Lentejas", FoodCategory.PROTEIN, "Mercadona", 120.0, 9.0, 18.0, 0.5, 7.0),
            food(3, "Producto externo", FoodCategory.PROTEIN, "Otro", 100.0, 20.0, 2.0, 1.0)
        )
        val result = FoodSuggestionEngine.suggest(
            foods, setOf(1), listOf(rule(1)), emptyList(), emptyMap(),
            Recommendation(2000, 120, 220, 65, "")
        )
        assertEquals(listOf(2L), result.map { it.food.id })
    }

    @Test
    fun proteinDeficitFavoursProteinDenseCandidate() {
        val foods = listOf(
            food(1, "Arroz", FoodCategory.CARBOHYDRATE, "Mercadona", 360.0, 7.0, 79.0, 1.0),
            food(2, "Pechuga", FoodCategory.PROTEIN, "Mercadona", 110.0, 24.0, 0.0, 1.0),
            food(3, "Aceite", FoodCategory.FAT, "Mercadona", 900.0, 0.0, 0.0, 100.0)
        )
        val result = FoodSuggestionEngine.suggest(
            foods, setOf(1), listOf(rule(1)), emptyList(), emptyMap(),
            Recommendation(2000, 140, 220, 65, "")
        )
        assertEquals(2L, result.first().food.id)
        assertTrue(result.first().reason.contains("proteína"))
    }

    @Test
    fun dismissedFoodIsNotSuggestedAgain() {
        val foods = listOf(
            food(1, "Arroz", FoodCategory.CARBOHYDRATE, "Mercadona", 360.0, 7.0, 79.0, 1.0),
            food(2, "Pechuga", FoodCategory.PROTEIN, "Mercadona", 110.0, 24.0, 0.0, 1.0)
        )
        val result = FoodSuggestionEngine.suggest(
            foods = foods,
            repertoireFoodIds = setOf(1),
            planningRules = listOf(rule(1)),
            plannedMeals = emptyList(),
            dishesById = emptyMap(),
            recommendation = Recommendation(2000, 140, 220, 65, ""),
            excludedFoodIds = setOf(2)
        )
        assertTrue(result.isEmpty())
    }

    private fun rule(id: Long) = PlanningRule(
        PlannedItemKind.FOOD, id, MealType.entries.toSet(),
        frequency = PlanningFrequency.NORMAL, preferredGrams = 100.0
    )

    private fun food(
        id: Long, name: String, category: FoodCategory, retailer: String,
        calories: Double, protein: Double, carbohydrate: Double, fat: Double,
        fiber: Double = 0.0
    ) = Food(
        id, name, category, calories, fat, carbohydrate, protein, fiber, retailer = retailer
    )
}
