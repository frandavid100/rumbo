package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FoodSuggestionEngineTest {
    @Test
    fun emptyRepertoireStillGetsColdStartSuggestions() {
        val foods = listOf(
            food(1, "Pechuga", FoodCategory.PROTEIN, "Mercadona", 110.0, 24.0, 0.0, 1.0),
            food(2, "Arroz", FoodCategory.CARBOHYDRATE, "Mercadona", 360.0, 7.0, 79.0, 1.0),
            food(3, "Nueces", FoodCategory.FAT, "Mercadona", 650.0, 15.0, 12.0, 60.0)
        )
        val result = FoodSuggestionEngine.suggest(
            foods = foods,
            repertoireFoodIds = emptySet(),
            planningRules = emptyList(),
            plannedMeals = emptyList(),
            dishesById = emptyMap(),
            recommendation = Recommendation(1875, 152, 200, 52, "")
        )
        assertTrue(result.isNotEmpty())
        assertTrue(result.size <= 3)
    }

    @Test
    fun excludesRepertoireAndOtherRetailers() {
        val foods = listOf(
            food(1, "Arroz habitual", FoodCategory.CARBOHYDRATE, "Mercadona", 360.0, 7.0, 79.0, 1.0),
            food(2, "Lentejas", FoodCategory.PROTEIN, "Mercadona", 120.0, 9.0, 18.0, 0.5, 7.0),
            food(3, "Producto externo", FoodCategory.PROTEIN, "Otro", 100.0, 20.0, 2.0, 1.0)
        )
        val result = FoodSuggestionEngine.suggest(
            foods, setOf(1), listOf(rule(1)), emptyList(), emptyMap(),
            Recommendation(2000, 120, 220, 65, "")
        )
        assertEquals(listOf(2L), result.map { it.food.id })
    }

    @Test
    fun proteinDeficitFavoursProteinDenseCandidate() {
        val foods = listOf(
            food(1, "Arroz", FoodCategory.CARBOHYDRATE, "Mercadona", 360.0, 7.0, 79.0, 1.0),
            food(2, "Pechuga", FoodCategory.PROTEIN, "Mercadona", 110.0, 24.0, 0.0, 1.0),
            food(3, "Aceite", FoodCategory.FAT, "Mercadona", 900.0, 0.0, 0.0, 100.0)
        )
        val result = FoodSuggestionEngine.suggest(
            foods, setOf(1), listOf(rule(1)), emptyList(), emptyMap(),
            Recommendation(2000, 140, 220, 65, "")
        )
        assertEquals(2L, result.first().food.id)
        assertTrue(result.first().reason.contains("proteína"))
    }

    @Test
    fun efficientProteinSourceBeatsFattyAlternative() {
        val foods = listOf(
            food(1, "Arroz", FoodCategory.CARBOHYDRATE, "Mercadona", 360.0, 7.0, 79.0, 1.0),
            food(2, "Pechuga", FoodCategory.PROTEIN, "Mercadona", 110.0, 24.0, 0.0, 1.0),
            food(3, "Embutido", FoodCategory.PROTEIN, "Mercadona",
                400.0, 24.0, 1.0, 32.0, saturated = 12.0)
        )
        val result = FoodSuggestionEngine.suggest(
            foods, setOf(1), listOf(rule(1)), emptyList(), emptyMap(),
            Recommendation(2000, 140, 220, 65, "")
        )
        assertEquals(2L, result.first().food.id)
        assertEquals("Aporta proteína con pocas calorías.", result.first().reason)
    }

    @Test
    fun carbohydrateDeficitRejectsFattyProcessedCandidates() {
        val foods = listOf(
            food(1, "Arroz", FoodCategory.CARBOHYDRATE, "Mercadona", 360.0, 7.0, 79.0, 1.0),
            food(2, "Patatas fritas", FoodCategory.CARBOHYDRATE, "Mercadona", 540.0, 6.0, 55.0, 34.0),
            food(3, "Galletas", FoodCategory.CARBOHYDRATE, "Mercadona", 470.0, 7.0, 70.0, 19.0),
            food(4, "Pasta con queso", FoodCategory.CARBOHYDRATE, "Mercadona", 390.0, 14.0, 64.0, 9.1)
        )
        val result = FoodSuggestionEngine.suggest(
            foods = foods,
            repertoireFoodIds = emptySet(),
            planningRules = emptyList(),
            plannedMeals = emptyList(),
            dishesById = emptyMap(),
            recommendation = Recommendation(1875, 152, 200, 52, "")
        )
        assertEquals(listOf(1L), result.map { it.food.id })
    }

    @Test
    fun smallRepertoireKeepsReceivingSuggestionsWithoutAStrongMenuDeficit() {
        val repertoire = (1L..14L).map { id ->
            food(
                id, "Alimento $id", FoodCategory.PROTEIN, "Mercadona",
                120.0, 20.0, 2.0, 2.0
            )
        }
        val candidate = food(
            100, "Alternativa", FoodCategory.PROTEIN, "Mercadona",
            150.0, 12.0, 8.0, 6.0
        )
        val result = FoodSuggestionEngine.suggest(
            foods = repertoire + candidate,
            repertoireFoodIds = repertoire.mapTo(mutableSetOf()) { it.id },
            planningRules = repertoire.map { rule(it.id) },
            plannedMeals = emptyList(),
            dishesById = emptyMap(),
            recommendation = null
        )
        assertEquals(listOf(100L), result.map { it.food.id })
    }

    @Test
    fun undersizedRepertoireDiversifiesSuggestionsAcrossFoodGroups() {
        val existingNut = food(
            1, "Almendra", FoodCategory.FAT, "Mercadona",
            600.0, 20.0, 10.0, 52.0, subcategory = "Frutos secos"
        )
        val foods = listOf(
            existingNut,
            food(2, "Nuez", FoodCategory.FAT, "Mercadona", 650.0, 15.0, 7.0, 65.0,
                subcategory = "Frutos secos"),
            food(3, "Avellana", FoodCategory.FAT, "Mercadona", 630.0, 15.0, 8.0, 61.0,
                subcategory = "Frutos secos"),
            food(4, "Arroz", FoodCategory.CARBOHYDRATE, "Mercadona", 360.0, 7.0, 79.0, 1.0,
                subcategory = "Arroz"),
            food(5, "Pechuga", FoodCategory.PROTEIN, "Mercadona", 110.0, 24.0, 0.0, 1.0,
                subcategory = "Aves"),
            food(6, "Calabacín", FoodCategory.VEGETABLE, "Mercadona", 20.0, 1.2, 3.1, 0.3,
                subcategory = "Hortalizas")
        )
        val result = FoodSuggestionEngine.suggest(
            foods = foods,
            repertoireFoodIds = setOf(1),
            planningRules = listOf(rule(1)),
            plannedMeals = emptyList(),
            dishesById = emptyMap(),
            recommendation = null
        )
        assertEquals(3, result.size)
        assertEquals(3, result.map { it.food.subcategory }.distinct().size)
        assertTrue(result.none { it.reason.startsWith("Ya comes otros productos") })
    }

    @Test
    fun saltyFattyPorkSnackIsNotRecommendedForProtein() {
        val foods = listOf(
            food(
                1, "Morro de cerdo", FoodCategory.FAT, "Mercadona",
                580.0, 60.3, 0.5, 37.2, saturated = 12.3, salt = 4.0
            ),
            food(
                2, "Pechuga de pollo", FoodCategory.PROTEIN, "Mercadona",
                110.0, 24.0, 0.0, 1.0, saturated = 0.3, salt = 0.2
            )
        )
        val result = FoodSuggestionEngine.suggest(
            foods = foods,
            repertoireFoodIds = emptySet(),
            planningRules = emptyList(),
            plannedMeals = emptyList(),
            dishesById = emptyMap(),
            recommendation = Recommendation(1875, 154, 198, 52, "")
        )
        assertTrue(result.none { it.food.id == 1L })
        assertEquals(2L, result.first().food.id)
        assertTrue(result.first().reason.contains("proteína"))
    }

    @Test
    fun repertoireAssessmentOverridesDisplayedMenu() {
        val protein = food(
            1, "Pechuga", FoodCategory.PROTEIN, "Mercadona",
            110.0, 24.0, 0.0, 1.0, subcategory = "Aves"
        )
        val carbohydrate = food(
            2, "Arroz", FoodCategory.CARBOHYDRATE, "Mercadona",
            360.0, 7.0, 79.0, 1.0, subcategory = "Arroz"
        )
        val toastWithSomeProtein = food(
            3, "Tosta", FoodCategory.CARBOHYDRATE, "Mercadona",
            360.0, 10.0, 70.0, 3.0, subcategory = "Pan"
        )
        val assessment = RepertoireAssessment(
            status = RepertoireStatus.INSUFFICIENT,
            nutrition = mapOf(
                NutrientKind.CALORIES to NutrientCapacity(1875.0, 1875.0, 0.0, TargetFit.ON_TARGET),
                NutrientKind.PROTEIN to NutrientCapacity(154.0, 100.0, -54.0, TargetFit.OUTSIDE),
                NutrientKind.CARBOHYDRATES to NutrientCapacity(198.0, 198.0, 0.0, TargetFit.ON_TARGET),
                NutrientKind.FAT to NutrientCapacity(52.0, 52.0, 0.0, TargetFit.ON_TARGET)
            ),
            coverage = emptyList(),
            fruitConcepts = 0,
            vegetableConcepts = 0,
            acceptableSolutions = 0,
            limitingFactors = emptyList(),
            suggestions = listOf(FoodCategory.PROTEIN),
            reactivationFoodIds = emptyList(),
            metrics = RepertoireMetrics(1.0, 1.0, 15, 3, 0, 4)
        )
        val result = FoodSuggestionEngine.suggest(
            foods = listOf(protein, carbohydrate, toastWithSomeProtein),
            repertoireFoodIds = emptySet(),
            planningRules = emptyList(),
            plannedMeals = listOf(
                PlannedMeal(
                    1, MealType.LUNCH, WeekDay.entries.toSet(),
                    items = listOf(PlannedFood(carbohydrate.id, 500.0))
                )
            ),
            dishesById = emptyMap(),
            recommendation = Recommendation(1875, 154, 198, 52, ""),
            repertoireAssessment = assessment,
            candidateAssessments = mapOf(
                protein.id to assessment,
                carbohydrate.id to assessment,
                toastWithSomeProtein.id to assessment
            )
        )
        assertEquals(listOf(protein.id), result.map { it.food.id })
        assertTrue(result.none { it.food.id == toastWithSomeProtein.id })
        assertTrue(result.first().reason.contains("proteína"))
    }

    @Test
    fun coldStartPrioritizesMacrosBeforeFiber() {
        val foods = listOf(
            food(1, "Soja", FoodCategory.PROTEIN, "Mercadona", 330.0, 45.0, 20.0, 5.0,
                fiber = 18.0, subcategory = "Soja"),
            food(2, "Tosta", FoodCategory.CARBOHYDRATE, "Mercadona", 360.0, 10.0, 70.0, 3.0,
                fiber = 12.0, subcategory = "Pan"),
            food(3, "Cacahuete", FoodCategory.FAT, "Mercadona", 620.0, 26.0, 8.0, 50.0,
                fiber = 10.0, subcategory = "Frutos secos")
        )
        val result = FoodSuggestionEngine.suggest(
            foods = foods,
            repertoireFoodIds = emptySet(),
            planningRules = emptyList(),
            plannedMeals = emptyList(),
            dishesById = emptyMap(),
            recommendation = Recommendation(1875, 154, 198, 52, "")
        )
        assertEquals(3, result.size)
        assertTrue(result.none { it.reason.contains("fibra") })
        assertTrue(result.all {
            it.reason.contains("proteína") ||
                it.reason.contains("hidratos") ||
                it.reason.contains("grasa")
        })
    }

    @Test
    fun carbohydrateSuggestionContinuesAtEightyFourPercentWithLargeRepertoire() {
        val menuBase = food(
            1, "Base del menú", FoodCategory.CARBOHYDRATE, "Mercadona",
            400.0, 22.0, 100.0, 7.0, subcategory = "Base"
        )
        val repertoire = listOf(menuBase) + (2L..15L).map { id ->
            food(
                id, "Alimento $id", FoodCategory.PROTEIN, "Mercadona",
                120.0, 20.0, 2.0, 2.0, subcategory = "Grupo $id"
            )
        }
        val candidate = food(
            100, "Arroz", FoodCategory.CARBOHYDRATE, "Mercadona",
            360.0, 7.0, 79.0, 1.0, subcategory = "Arroz"
        )
        val result = FoodSuggestionEngine.suggest(
            foods = repertoire + candidate,
            repertoireFoodIds = repertoire.mapTo(mutableSetOf()) { it.id },
            planningRules = repertoire.map { rule(it.id) },
            plannedMeals = listOf(
                PlannedMeal(
                    id = 1,
                    type = MealType.LUNCH,
                    days = WeekDay.entries.toSet(),
                    items = listOf(PlannedFood(menuBase.id, 168.0))
                )
            ),
            dishesById = emptyMap(),
            recommendation = Recommendation(1875, 154, 200, 52, "")
        )
        assertTrue(result.any { it.food.id == candidate.id })
        assertTrue(
            result.first { it.food.id == candidate.id }.reason.contains("hidratos")
        )
    }

    @Test
    fun dismissedFoodIsNotSuggestedAgain() {
        val foods = listOf(
            food(1, "Arroz", FoodCategory.CARBOHYDRATE, "Mercadona", 360.0, 7.0, 79.0, 1.0),
            food(2, "Pechuga", FoodCategory.PROTEIN, "Mercadona", 110.0, 24.0, 0.0, 1.0)
        )
        val result = FoodSuggestionEngine.suggest(
            foods = foods,
            repertoireFoodIds = setOf(1),
            planningRules = listOf(rule(1)),
            plannedMeals = emptyList(),
            dishesById = emptyMap(),
            recommendation = Recommendation(2000, 140, 220, 65, ""),
            excludedFoodIds = setOf(2)
        )
        assertTrue(result.isEmpty())
    }

    private fun rule(id: Long) = PlanningRule(
        PlannedItemKind.FOOD, id, MealType.entries.toSet(),
        frequency = PlanningFrequency.NORMAL, preferredGrams = 100.0
    )

    private fun food(
        id: Long, name: String, category: FoodCategory, retailer: String,
        calories: Double, protein: Double, carbohydrate: Double, fat: Double,
        fiber: Double = 0.0,
        saturated: Double? = null,
        subcategory: String? = null,
        salt: Double? = null
    ) = Food(
        id, name, category, calories, fat, carbohydrate, protein, fiber,
        retailer = retailer,
        saturatedFatGrams = saturated,
        subcategory = subcategory,
        saltGrams = salt
    )
}
