package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.CulinaryType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
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

    @Test
    fun aStarchTypeMustStillProvideAUsefulServingOfCarbohydrate() {
        val need = CulinaryNeed(
            CulinaryNeedKind.STARCH_BASE,
            es.david.rumbo.model.MealType.DINNER,
            setOf(CulinaryType.FRESH_STARCH),
            "Añade una base de hidratos para la cena."
        )
        val pickledCorn = food(CulinaryType.FRESH_STARCH).copy(
            category = FoodCategory.CARBOHYDRATE,
            carbohydrateGrams = 4.8
        )
        val potato = food(CulinaryType.FRESH_STARCH).copy(
            category = FoodCategory.CARBOHYDRATE,
            carbohydrateGrams = 17.5
        )
        val preparedSalad = potato.copy(category = FoodCategory.OTHER)

        assertFalse(CulinaryPolicy.addresses(need, pickledCorn))
        assertTrue(CulinaryPolicy.addresses(need, potato))
        assertFalse(CulinaryPolicy.addresses(need, preparedSalad))
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
