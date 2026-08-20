package es.david.rumbo.ui

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import org.junit.Assert.assertEquals
import org.junit.Test

class FoodEditorMetadataPreservationTest {
    @Test
    fun editingUnitPreservesImportedMetadata() {
        val imported = Food(
            id = 42L,
            name = "Leche semidesnatada",
            category = FoodCategory.PROTEIN,
            calories = 46.4,
            fatGrams = 1.6,
            carbohydrateGrams = 4.6,
            proteinGrams = 3.4,
            fiberGrams = 0.0,
            brand = "BEDCA",
            family = "Lácteos y derivados",
            saltGrams = 0.1,
            source = "BEDCA",
            nutritionalRoles = setOf("COMPLEMENTARY_PROTEIN"),
            culinaryRoles = setOf("MIXING_BASE", "DRINK")
        )

        val edited = mergeFoodEditorChanges(
            initial = imported,
            newId = 99L,
            name = imported.name,
            category = imported.category,
            calories = imported.calories!!,
            fat = imported.fatGrams!!,
            carbohydrates = imported.carbohydrateGrams!!,
            protein = imported.proteinGrams!!,
            fiber = imported.fiberGrams,
            links = imported.links,
            unitName = "taza",
            unitAmount = 230.0,
            wholeUnitsOnly = true
        )

        assertEquals(imported.id, edited.id)
        assertEquals(imported.brand, edited.brand)
        assertEquals(imported.family, edited.family)
        assertEquals(imported.saltGrams, edited.saltGrams)
        assertEquals(imported.source, edited.source)
        assertEquals(imported.nutritionalRoles, edited.nutritionalRoles)
        assertEquals(imported.culinaryRoles, edited.culinaryRoles)
        assertEquals("taza", edited.unitName)
        assertEquals(230.0, edited.unitAmount!!, 0.0)
    }
}
