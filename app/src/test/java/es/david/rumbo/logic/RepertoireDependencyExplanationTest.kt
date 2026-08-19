package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RepertoireDependencyExplanationTest {
    private val breakfastOnly = MealType.entries.associateWith {
        if (it == MealType.MORNING_SNACK) 1.0 else 0.0
    }
    private val target = Recommendation(400, 20, 40, 18, "test")

    @Test
    fun unavoidableSandwichDependencyNamesTheFoodThatCausesIt() {
        val filling = food(
            1L,
            "Pavo en lonchas",
            setOf("SANDWICH_FILLING")
        )
        val result = RepertoireEvaluator.evaluate(
            rules = listOf(rule(filling.id)),
            foodsById = mapOf(filling.id to filling),
            dishesById = emptyMap(),
            recommendation = target,
            mealShares = breakfastOnly
        )

        val need = result.culinaryNeeds.first { it.kind == CulinaryNeedKind.COMPANION_BASE }
        assertEquals(filling.id, need.sourceFoodId)
        assertEquals(filling.name, need.sourceFoodName)
        assertEquals(CulinaryRole.SANDWICH_FILLING, need.sourceRole)
        assertTrue(CulinaryRole.SANDWICH_BASE in need.acceptedRoles)
        assertTrue(need.message.contains("Pavo en lonchas"))
        assertTrue(need.message.contains("base de bocadillo", ignoreCase = true))
    }

    @Test
    fun alternativeRoleWithoutBreadPreventsFalseSandwichRequest() {
        val versatile = food(
            2L,
            "Pavo versátil",
            setOf("PLATE_CENTER", "SANDWICH_FILLING")
        )
        val result = RepertoireEvaluator.evaluate(
            rules = listOf(rule(versatile.id)),
            foodsById = mapOf(versatile.id to versatile),
            dishesById = emptyMap(),
            recommendation = target,
            mealShares = breakfastOnly
        )

        assertNull(result.culinaryNeeds.firstOrNull { it.kind == CulinaryNeedKind.COMPANION_BASE })
    }

    private fun rule(id: Long) = PlanningRule(
        itemKind = PlannedItemKind.FOOD,
        itemId = id,
        allowedMealTypes = setOf(MealType.MORNING_SNACK),
        frequency = PlanningFrequency.ALWAYS,
        preferredGrams = 100.0
    )

    private fun food(id: Long, name: String, roles: Set<String>) = Food(
        id = id,
        name = name,
        category = FoodCategory.PROTEIN,
        calories = 120.0,
        fatGrams = 4.0,
        carbohydrateGrams = 2.0,
        proteinGrams = 20.0,
        fiberGrams = 0.0,
        culinaryRoles = roles
    )
}
