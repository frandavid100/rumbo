package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningRule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class InitialRepertoireGateTest {
    private fun food(id: Long, role: String) = Food(
        id = id, name = role, category = FoodCategory.OTHER,
        calories = 100.0, fatGrams = 5.0, carbohydrateGrams = 10.0,
        proteinGrams = 10.0, fiberGrams = 0.0,
        nutritionalRoles = setOf(role)
    )

    private fun rule(id: Long, vararg meals: MealType) = PlanningRule(
        itemKind = PlannedItemKind.FOOD,
        itemId = id,
        allowedMealTypes = meals.toSet()
    )

    @Test
    fun generatorGateRequiresExactInitialSetAndProteinCoverage() {
        var id = 0L
        val foods = mutableListOf<Food>()
        val rules = mutableListOf<PlanningRule>()
        fun add(role: String, vararg meals: MealType) {
            id += 1
            foods += food(id, role)
            rules += rule(id, *meals)
        }
        repeat(2) { add("PRIMARY_PROTEIN", MealType.LUNCH, MealType.DINNER) }
        add("PRIMARY_PROTEIN", MealType.LUNCH)
        repeat(3) { add("PRIMARY_CARBOHYDRATE", MealType.LUNCH) }
        add("CONCENTRATED_FAT", MealType.LUNCH)
        repeat(3) { add("COMPLEMENTARY_PROTEIN", MealType.BREAKFAST) }
        repeat(3) { add("COMPLEMENTARY_CARBOHYDRATE", MealType.BREAKFAST) }

        val foodsById = foods.associateBy { it.id }
        val blocked = InitialRepertoireGate.evaluate(rules, foodsById, foodsById.keys)
        assertFalse(blocked.isSatisfied)
        assertEquals("PRIMARY_PROTEIN", blocked.nextMissing?.role)
        assertEquals(1, blocked.nextMissing?.missing)

        rules[rules.indexOfFirst { it.itemId == 3L }] =
            rule(3L, MealType.LUNCH, MealType.DINNER)
        val ready = InitialRepertoireGate.evaluate(rules, foodsById, foodsById.keys)
        assertTrue(ready.isSatisfied)
        assertTrue(ready.requirements.none { it.role == "COMPLEMENTARY_FAT" })
    }
}
