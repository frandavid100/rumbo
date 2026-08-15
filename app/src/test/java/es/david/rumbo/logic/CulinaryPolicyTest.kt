package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.CulinaryType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CulinaryPolicyTest {
    @Test
    fun explicitCatalogTypesProvideCentralPolicies() {
        assertEquals(
            setOf(CulinaryRole.STARCH_BASE),
            CulinaryPolicy.roles(food(CulinaryType.DRY_PASTA))
        )
        assertEquals(
            setOf(CulinaryRole.BREAKFAST_CEREAL),
            CulinaryPolicy.roles(food(CulinaryType.BREAKFAST_CEREAL))
        )
        assertEquals(
            setOf(CulinaryRole.LIQUID_OR_CREAMY_BASE),
            CulinaryPolicy.roles(food(CulinaryType.MILK_BASE))
        )
        assertEquals(
            setOf(CulinaryRole.DEPENDENT_PREPARATION),
            CulinaryPolicy.roles(food(CulinaryType.PROTEIN_POWDER))
        )
        assertTrue(CulinaryPolicy.roles(food(CulinaryType.UNKNOWN)).isEmpty())
    }

    private fun food(type: CulinaryType) = Food(
        id = type.ordinal.toLong() + 1,
        name = type.name,
        category = FoodCategory.OTHER,
        calories = 100.0,
        fatGrams = 1.0,
        carbohydrateGrams = 10.0,
        proteinGrams = 10.0,
        fiberGrams = 1.0,
        culinaryType = type
    )
}
