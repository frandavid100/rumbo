package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RecipeRecommendationEngineTest {
    @Test
    fun commercialChickenBreastMatchesGenericIngredient() {
        assertTrue("pechuga_pollo" in GenericIngredientClassifier.classify(food(1, "Pechuga de pollo fileteada Hacendado")))
    }

    @Test
    fun nuggetsNeverRepresentChickenBreast() {
        assertFalse("pechuga_pollo" in GenericIngredientClassifier.classify(food(1, "Nuggets de pechuga de pollo rebozados")))
    }

    @Test
    fun onlyRecipesFullyCoveredByRepertoireAreRecommended() {
        val foods = listOf(
            food(1, "Arroz basmati"),
            food(2, "Pechuga de pollo fileteada"),
            food(3, "Calabacín"),
            food(4, "Aceite de oliva virgen extra")
        )
        val recommendations = RecipeRecommendationEngine.recommend(
            foods = foods,
            repertoireFoodIds = foods.mapTo(mutableSetOf()) { it.id },
            existingDishes = emptyList(),
            maxResults = 50
        )
        assertTrue(recommendations.any { it.recipe.name == "Arroz con pollo y calabacín" })
        assertFalse(recommendations.any { it.recipe.name == "Pasta con pollo y tomate" })
    }

    private fun food(id: Long, name: String) = Food(
        id = id,
        name = name,
        category = FoodCategory.OTHER,
        calories = 100.0,
        fatGrams = 1.0,
        carbohydrateGrams = 10.0,
        proteinGrams = 10.0,
        fiberGrams = 1.0
    )
}
