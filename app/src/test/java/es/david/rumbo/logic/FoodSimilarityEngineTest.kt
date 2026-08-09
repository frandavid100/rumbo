package es.david.rumbo.logic

import es.david.rumbo.model.DefaultFoodCatalog
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FoodSimilarityEngineTest {
    private val foods = DefaultFoodCatalog.items

    @Test
    fun chickenOffersCloseProteinAlternativesButNotSalmon() {
        val chicken = foods.first { it.name == "Pechuga de pollo" }
        val similarNames = FoodSimilarityEngine.findSimilar(chicken, foods).map { it.name }

        assertTrue("Pechuga de pavo" in similarNames)
        assertTrue("Filetes de pechuga de pavo" in similarNames)
        assertFalse("Lomos de salmón" in similarNames)
    }

    @Test
    fun potatoAndSweetPotatoAreInterchangeableByTheConfiguredTolerance() {
        val potato = foods.first { it.name == "Patata" }

        assertTrue(FoodSimilarityEngine.findSimilar(potato, foods).any { it.name == "Boniato" })
    }

    @Test
    fun resultsNeverCrossTheFoodCategory() {
        val melon = foods.first { it.name == "Melón" }

        assertTrue(FoodSimilarityEngine.findSimilar(melon, foods).all { it.category == melon.category })
    }
}
