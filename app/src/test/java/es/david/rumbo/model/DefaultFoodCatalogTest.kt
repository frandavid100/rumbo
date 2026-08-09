package es.david.rumbo.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DefaultFoodCatalogTest {
    @Test
    fun catalogContainsOnlyValidUniqueFoods() {
        val foods = DefaultFoodCatalog.items

        assertEquals(52, foods.size)
        assertEquals(foods.size, foods.map { it.id }.distinct().size)
        assertEquals(foods.size, foods.map { it.name.lowercase() }.distinct().size)
        assertTrue(foods.all { it.isValid() })
        assertTrue(foods.all { it.links.isNotEmpty() })
    }

    @Test
    fun catalogIncludesFoodsSelectedForTheWeeklyDiet() {
        val names = DefaultFoodCatalog.items.map { it.name }.toSet()

        assertTrue("Pimiento verde para freír" in names)
        assertTrue("Tomate rosa" in names)
        assertTrue("Calabacín" in names)
        assertTrue("Arroz basmati Hacendado" in names)
    }

    @Test
    fun foodsCanContainSeveralValidReferenceLinks() {
        val basmati = DefaultFoodCatalog.items.first { it.name == "Arroz basmati Hacendado" }

        assertEquals(3, basmati.links.size)
        assertTrue(basmati.links.all { it.startsWith("https://") })
    }
}
