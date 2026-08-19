package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.WeekDay
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MajorNutritionalRolePolicyTest {
    // Regression for the complementary-only day observed in profile "Prueba".
    private fun food(id: Long, category: FoodCategory, role: String) = Food(
        id = id, name = role, category = category, calories = 100.0,
        fatGrams = 10.0, carbohydrateGrams = 10.0, proteinGrams = 10.0,
        fiberGrams = 0.0,
        nutritionalRoles = setOf(role)
    )

    private val foods = listOf(
        food(1, FoodCategory.PROTEIN, "PRIMARY_PROTEIN"),
        food(2, FoodCategory.PROTEIN, "COMPLEMENTARY_PROTEIN"),
        food(3, FoodCategory.CARBOHYDRATE, "PRIMARY_CARBOHYDRATE"),
        food(4, FoodCategory.FAT, "CONCENTRATED_FAT")
    ).associateBy { it.id }

    private fun meal(vararg ids: Long) = PlannedMeal(
        id = 1, type = MealType.LUNCH, days = setOf(WeekDay.MONDAY),
        items = ids.map { PlannedFood(it, 100.0) }
    )

    @Test
    fun complementaryProteinCannotReplacePrimaryProtein() {
        assertFalse(
            MajorNutritionalRolePolicy.hasAllRequiredRoles(
                listOf(meal(2, 3, 4)), foods, emptyMap()
            )
        )
        assertTrue(
            MajorNutritionalRolePolicy.hasAllRequiredRoles(
                listOf(meal(1, 2, 3, 4)), foods, emptyMap()
            )
        )
    }
}
