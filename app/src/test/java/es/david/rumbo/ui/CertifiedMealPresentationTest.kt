package es.david.rumbo.ui

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CertifiedMealPresentationTest {
    private fun food(id: Long, name: String, category: FoodCategory, vararg roles: String) = Food(
        id = id,
        name = name,
        category = category,
        calories = 100.0,
        fatGrams = 2.0,
        carbohydrateGrams = 10.0,
        proteinGrams = 10.0,
        fiberGrams = 1.0,
        culinaryRoles = roles.toSet()
    )

    @Test
    fun categoriesFollowTheMealReadingOrder() {
        val categories = FoodCategory.entries.sortedBy(::mealCategoryOrder)
        assertEquals(
            listOf(
                FoodCategory.PROTEIN,
                FoodCategory.CARBOHYDRATE,
                FoodCategory.FAT,
                FoodCategory.VEGETABLE,
                FoodCategory.FRUIT,
                FoodCategory.OTHER
            ),
            categories
        )
    }

    @Test
    fun culinaryCompanionsBecomeOneProposedDishButDessertStaysSeparate() {
        val turkey = food(1, "Pavo", FoodCategory.PROTEIN, "PLATE_CENTER")
        val beans = food(2, "Judía blanca", FoodCategory.CARBOHYDRATE, "PLATE_BASE")
        val mushrooms = food(3, "Champiñón", FoodCategory.VEGETABLE, "SIDE")
        val mango = food(4, "Mango", FoodCategory.FRUIT, "DESSERT", "STANDALONE")

        val groups = groupCulinaryCompanions(
            listOf(turkey, beans, mushrooms, mango).map { ProposedDishIngredient(it, 100.0) }
        )

        assertEquals(2, groups.size)
        assertEquals(setOf(1L, 2L, 3L), groups.first().map { it.food.id }.toSet())
        assertTrue(groups.last().single().food.id == mango.id)
    }
}
