package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CulinaryClassifierTest {
    @Test
    fun supermarketNamesIdentifyOnlyHighConfidenceRoles() {
        assertEquals(
            setOf(CulinaryRole.STARCH_BASE),
            CulinaryClassifier.roles(food("HACENDADO HÉLICES VEGETALES"))
        )
        assertEquals(
            setOf(CulinaryRole.BREAKFAST_CEREAL),
            CulinaryClassifier.roles(food("Corn flakes integrales"))
        )
        assertEquals(
            setOf(CulinaryRole.LIQUID_OR_CREAMY_BASE),
            CulinaryClassifier.roles(food("Hacendado leche semidesnatada"))
        )
        assertEquals(
            setOf(CulinaryRole.DEPENDENT_PREPARATION),
            CulinaryClassifier.roles(food("Polvo de proteínas Natural Isolate"))
        )
        assertTrue(CulinaryClassifier.roles(food("Pechuga de pavo" )).isEmpty())
    }

    private fun food(name: String) = Food(
        id = name.hashCode().toLong().let { if (it == 0L) 1L else kotlin.math.abs(it) },
        name = name,
        category = FoodCategory.OTHER,
        calories = 100.0,
        fatGrams = 1.0,
        carbohydrateGrams = 10.0,
        proteinGrams = 10.0,
        fiberGrams = 1.0
    )
}
