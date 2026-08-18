package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.PlannedItemKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CulinaryPolicyTest {
    @Test
    fun catalogueFoodsExposeOnlyCanonicalRoles() {
        val milk = food(setOf("CEREAL_BASE", "POWDER_BASE", "BEVERAGE", "STANDALONE"))
        assertEquals(
            setOf(CulinaryRole.CEREAL_BASE, CulinaryRole.POWDER_BASE, CulinaryRole.BEVERAGE, CulinaryRole.STANDALONE),
            CulinaryPolicy.roles(milk)
        )
    }

    @Test
    fun hardDependenciesAreDefinedOnceByRole() {
        assertEquals(
            setOf(CulinaryRole.CEREAL_BASE),
            CulinaryPolicy.defaultPolicy(CulinaryRole.CEREAL_MIX_IN).requiredRoles
        )
        assertEquals(
            setOf(CulinaryRole.POWDER_BASE),
            CulinaryPolicy.defaultPolicy(CulinaryRole.POWDER_MIX_IN).requiredRoles
        )
        assertEquals(
            setOf(CulinaryRole.SANDWICH_BASE),
            CulinaryPolicy.defaultPolicy(CulinaryRole.SANDWICH_FILLING).requiredRoles
        )
        assertEquals(
            setOf(CulinaryRole.SANDWICH_BASE),
            CulinaryPolicy.defaultPolicy(CulinaryRole.SPREAD).requiredRoles
        )
    }

    @Test
    fun multiRoleFoodCanChooseAValidUseForTheMeal() {
        assertTrue(CulinaryPolicy.hasValidRoleAssignment(listOf(
            setOf(CulinaryRole.SANDWICH_FILLING, CulinaryRole.STANDALONE)
        )))
        assertFalse(CulinaryPolicy.hasValidRoleAssignment(listOf(
            setOf(CulinaryRole.SANDWICH_FILLING)
        )))
        assertTrue(CulinaryPolicy.hasValidRoleAssignment(listOf(
            setOf(CulinaryRole.SANDWICH_FILLING),
            setOf(CulinaryRole.SANDWICH_BASE)
        )))
    }

    @Test
    fun plateCardinalitiesAreHardButRoleChoiceRemainsFlexible() {
        assertFalse(CulinaryPolicy.hasValidRoleAssignment(listOf(
            setOf(CulinaryRole.PLATE_CENTER),
            setOf(CulinaryRole.PLATE_CENTER)
        )))
        assertTrue(CulinaryPolicy.hasValidRoleAssignment(listOf(
            setOf(CulinaryRole.PLATE_CENTER, CulinaryRole.STANDALONE),
            setOf(CulinaryRole.PLATE_CENTER)
        )))
    }

    @Test
    fun portionsComeFromRolePolicy() {
        val oil = food(setOf("COOKING_MEDIUM"))
        val input = PlanningRule(
            itemKind = PlannedItemKind.FOOD,
            itemId = oil.id,
            allowedMealTypes = setOf(es.david.rumbo.model.MealType.LUNCH),
            frequency = PlanningFrequency.NORMAL,
            preferredGrams = 100.0
        )
        val result = CulinaryPolicy.applyPortion(input, oil)
        assertEquals(10.0, result.preferredGrams, 0.001)
        assertEquals(5.0, result.preferredGrams * result.minimumFactor, 0.001)
        assertEquals(15.0, result.preferredGrams * result.maximumFactor, 0.001)
    }

    private fun food(roles: Set<String>) = Food(
        id = 1L,
        name = "fixture",
        category = FoodCategory.OTHER,
        calories = 100.0,
        fatGrams = 1.0,
        carbohydrateGrams = 10.0,
        proteinGrams = 10.0,
        fiberGrams = 1.0,
        culinaryRoles = roles
    )
}
