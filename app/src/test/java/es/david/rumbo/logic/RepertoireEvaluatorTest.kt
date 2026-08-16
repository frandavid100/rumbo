package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.CulinaryType
import es.david.rumbo.model.DefaultFoodCatalog
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RepertoireEvaluatorTest {
    private val recommendation = Recommendation(2000, 140, 220, 65, "")
    private val lunchOnly = MealType.entries.associateWith { if (it == MealType.LUNCH) 1.0 else 0.0 }

    @Test
    fun inactiveAndUnprogrammedFoodsDoNotCount() {
        val foods = listOf(
            food(1, "Pollo", FoodCategory.PROTEIN, 165.0, 31.0, 0.0, 3.6),
            food(2, "Arroz", FoodCategory.CARBOHYDRATE, 360.0, 7.0, 79.0, 0.6),
            food(3, "Nueces", FoodCategory.FAT, 650.0, 15.0, 10.0, 60.0)
        ).associateBy { it.id }
        val result = RepertoireEvaluator.evaluate(
            rules = listOf(
                rule(1),
                rule(2).copy(isActive = false),
                rule(3).copy(allowedMealTypes = emptySet())
            ),
            foodsById = foods,
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = lunchOnly
        )

        assertEquals(1, result.metrics.availableFoods)
        assertEquals(1, result.coverage.single().alternatives)
        assertTrue(result.reactivationFoodIds.contains(2L))
    }

    @Test
    fun missingMealCoverageIsReportedAsARealConstraint() {
        val food = food(1, "Arroz", FoodCategory.CARBOHYDRATE, 360.0, 7.0, 79.0, 0.6)
        val shares = MealType.entries.associateWith {
            when (it) {
                MealType.LUNCH, MealType.DINNER -> .5
                else -> 0.0
            }
        }
        val result = RepertoireEvaluator.evaluate(
            listOf(rule(1)), mapOf(1L to food), emptyMap(), recommendation, shares
        )

        assertEquals(RepertoireStatus.INSUFFICIENT, result.status)
        assertTrue(result.limitingFactors.any { it.contains("cena", ignoreCase = true) })
    }

    @Test
    fun redundantProductsDoNotCreateFalseRobustness() {
        val foods = (1L..10L).map {
            food(it, "Yogur $it", FoodCategory.PROTEIN, 120.0, 10.0, 8.0, 5.0)
        }.associateBy { it.id }
        val result = RepertoireEvaluator.evaluate(
            foods.keys.map(::rule), foods, emptyMap(),
            Recommendation(1200, 100, 80, 55, ""), lunchOnly
        )

        assertEquals(1, result.metrics.distinctNutritionProfiles)
        assertNotEquals(RepertoireStatus.ROBUST, result.status)
    }

    @Test
    fun practicalWholeUnitsAreUsedByTheRealGenerator() {
        val yoghurt = food(1, "Yogur", FoodCategory.PROTEIN, 100.0, 10.0, 10.0, 2.0)
            .copy(unitName = "vasito", unitAmount = 120.0, wholeUnitsOnly = true)
        val result = RepertoireEvaluator.evaluate(
            listOf(rule(1).copy(preferredGrams = 120.0, minimumFactor = .5, maximumFactor = 2.0)),
            mapOf(1L to yoghurt), emptyMap(), Recommendation(240, 24, 24, 5, ""), lunchOnly
        )

        assertEquals(3, result.metrics.evaluatedSolutions)
        assertEquals(0.0, result.nutrition.getValue(NutrientKind.CALORIES).bestAchievable % 120.0, .001)
    }

    @Test
    fun occasionalFoodsMayRepeatDailyAndLegacyDayLimitsAreIgnored() {
        val shares = mapOf(
            MealType.BREAKFAST to .25,
            MealType.MORNING_SNACK to .10,
            MealType.LUNCH to .35,
            MealType.AFTERNOON_SNACK to .10,
            MealType.DINNER to .20
        )
        val foods = MealType.entries.mapIndexed { index, type ->
            val share = shares.getValue(type)
            food(
                index.toLong() + 1,
                "Option $index",
                FoodCategory.OTHER,
                recommendation.calories * share,
                recommendation.proteinGrams * share,
                recommendation.carbohydrateGrams * share,
                recommendation.fatGrams * share
            )
        }.associateBy { it.id }
        val rules = MealType.entries.mapIndexed { index, type ->
            rule(index.toLong() + 1, PlanningFrequency.OCCASIONAL).copy(
                allowedMealTypes = setOf(type),
                allowedDays = setOf(WeekDay.MONDAY)
            )
        }

        val result = RepertoireEvaluator.evaluate(
            rules, foods, emptyMap(), recommendation, shares
        )

        assertTrue(
            result.status == RepertoireStatus.SUFFICIENT ||
                result.status == RepertoireStatus.ROBUST
        )
    }

    @Test
    fun addingAnEquivalentAlternativeCannotInvalidateAnAcceptableRepertoire() {
        val shares = mapOf(
            MealType.BREAKFAST to .25,
            MealType.MORNING_SNACK to .10,
            MealType.LUNCH to .35,
            MealType.AFTERNOON_SNACK to .10,
            MealType.DINNER to .20
        )
        val foods = MealType.entries.mapIndexed { index, type ->
            val share = shares.getValue(type)
            food(
                index.toLong() + 1, "Option $type", FoodCategory.OTHER,
                recommendation.calories * share,
                recommendation.proteinGrams * share,
                recommendation.carbohydrateGrams * share,
                recommendation.fatGrams * share
            )
        }.toMutableList()
        val rules = MealType.entries.mapIndexed { index, type ->
            rule(index.toLong() + 1).copy(allowedMealTypes = setOf(type))
        }.toMutableList()
        val before = RepertoireEvaluator.evaluate(
            rules, foods.associateBy { it.id }, emptyMap(), recommendation, shares
        )
        val lunchAlternative = foods.single { it.name.endsWith(MealType.LUNCH.name) }
            .copy(id = 99, name = "Equivalent lunch option")
        foods += lunchAlternative
        rules += rule(lunchAlternative.id).copy(allowedMealTypes = setOf(MealType.LUNCH))
        val after = RepertoireEvaluator.evaluate(
            rules, foods.associateBy { it.id }, emptyMap(), recommendation, shares
        )

        assertTrue(before.acceptableSolutions > 0)
        assertTrue(after.acceptableSolutions > 0)
        assertTrue(after.status == RepertoireStatus.SUFFICIENT || after.status == RepertoireStatus.ROBUST)
    }

    @Test
    fun proteinPowderReportsItsMissingCompanionBeforeMenuCreation() {
        val powder = food(
            20, "Proteína en polvo", FoodCategory.PROTEIN,
            358.0, 83.0, 2.0, 2.0
        ).copy(culinaryType = CulinaryType.PROTEIN_POWDER)
        val result = RepertoireEvaluator.evaluate(
            rules = listOf(rule(powder.id).copy(
                allowedMealTypes = setOf(MealType.BREAKFAST),
                frequency = PlanningFrequency.ALWAYS
            )),
            foodsById = mapOf(powder.id to powder),
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = MealType.entries.associateWith {
                if (it == MealType.BREAKFAST) 1.0 else 0.0
            }
        )

        assertEquals(CulinaryNeedKind.COMPANION_BASE, result.culinaryNeeds.single().kind)
        assertTrue(result.culinaryNeeds.single().message.contains("leche"))
    }

    @Test
    fun profileTwoHasEnoughLeanProteinWithoutAddingMoreFoods() {
        val ids = setOf(
            42L, 37L, 48L, 36L, 34L, 39L, 44L, 17L, 22L, 11L,
            33L, 35L, 1L, 25L, 14L, 13L, 3L, 15L
        )
        val importedFoods = listOf(
            food(108480000229663, "Corn flakes", FoodCategory.CARBOHYDRATE, 373.0, 6.7, 82.0, 1.1)
                .copy(culinaryType = CulinaryType.BREAKFAST_CEREAL),
            food(108480000822277, "Pan rallado", FoodCategory.CARBOHYDRATE, 336.0, 8.7, 71.3, 1.7)
                .copy(culinaryType = CulinaryType.COOKING_INGREDIENT),
            food(108480000159533, "Barquillo", FoodCategory.CARBOHYDRATE, 390.0, 11.0, 79.0, 2.6)
                .copy(culinaryType = CulinaryType.SNACK_DESSERT),
            food(108480000063441, "Hélices", FoodCategory.CARBOHYDRATE, 359.0, 12.0, 74.0, 1.7)
                .copy(culinaryType = CulinaryType.DRY_PASTA),
            food(108480000242747, "Sepia", FoodCategory.PROTEIN, 78.0, 18.0, .8, .5)
                .copy(culinaryType = CulinaryType.MAIN_FISH),
            food(108480000062505, "Macarrones", FoodCategory.CARBOHYDRATE, 366.0, 12.0, 74.0, 1.5)
                .copy(culinaryType = CulinaryType.DRY_PASTA),
            food(108480000621283, "Merluza", FoodCategory.PROTEIN, 82.0, 18.0, .5, 1.2)
                .copy(culinaryType = CulinaryType.MAIN_FISH),
            food(108480000168764, "Membrillo", FoodCategory.CARBOHYDRATE, 142.0, .25, 41.0, .25)
                .copy(culinaryType = CulinaryType.SNACK_DESSERT),
            food(108480000167576, "Mazorca encurtida", FoodCategory.VEGETABLE, 33.0, 1.1, 4.8, .5)
                .copy(culinaryType = CulinaryType.VEGETABLE, category = FoodCategory.FRUIT)
        )
        val foods = (DefaultFoodCatalog.items.filter { it.id in ids } + importedFoods)
            .map { food ->
                if (food.id == 1L) food.copy(
                    unitName = "taza", unitAmount = 230.0,
                    wholeUnitsOnly = true, unitDivisions = 1
                ) else food
            }
            .associateBy { it.id }
        fun programmed(
            id: Long,
            meals: Set<MealType>,
            frequency: PlanningFrequency = PlanningFrequency.OCCASIONAL
        ) = rule(id, frequency).copy(allowedMealTypes = meals)
        val result = RepertoireEvaluator.evaluate(
            rules = listOf(
                programmed(42, setOf(MealType.BREAKFAST), PlanningFrequency.ALWAYS),
                programmed(37, setOf(MealType.LUNCH, MealType.DINNER)),
                programmed(48, setOf(MealType.LUNCH, MealType.DINNER), PlanningFrequency.FREQUENT),
                programmed(36, setOf(MealType.LUNCH, MealType.DINNER), PlanningFrequency.NORMAL),
                programmed(34, setOf(MealType.LUNCH, MealType.DINNER)),
                programmed(39, setOf(MealType.LUNCH, MealType.DINNER), PlanningFrequency.NORMAL),
                programmed(44, setOf(MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK), PlanningFrequency.FREQUENT),
                programmed(17, setOf(MealType.LUNCH), PlanningFrequency.NORMAL),
                programmed(22, setOf(MealType.LUNCH, MealType.DINNER)),
                programmed(11, setOf(MealType.BREAKFAST)),
                programmed(108480000229663, setOf(MealType.BREAKFAST)),
                programmed(108480000822277, setOf(MealType.DINNER)),
                programmed(108480000159533, setOf(MealType.AFTERNOON_SNACK)),
                programmed(108480000063441, setOf(MealType.LUNCH)),
                programmed(108480000242747, setOf(MealType.DINNER)),
                programmed(108480000062505, setOf(MealType.LUNCH)),
                programmed(108480000621283, setOf(MealType.DINNER)),
                programmed(33, setOf(MealType.LUNCH, MealType.DINNER)),
                programmed(35, setOf(MealType.DINNER)),
                programmed(1, setOf(MealType.BREAKFAST)),
                programmed(25, MealType.entries.toSet()),
                programmed(14, setOf(MealType.LUNCH)),
                programmed(13, setOf(MealType.LUNCH)),
                programmed(3, setOf(MealType.LUNCH)),
                programmed(108480000168764, setOf(MealType.BREAKFAST)),
                programmed(108480000167576, setOf(MealType.DINNER)),
                programmed(15, setOf(MealType.DINNER))
            ),
            foodsById = foods,
            dishesById = emptyMap(),
            recommendation = Recommendation(1875, 154, 198, 52, ""),
            mealShares = mapOf(
                MealType.BREAKFAST to 2.0 / 9.0,
                MealType.MORNING_SNACK to 1.0 / 9.0,
                MealType.LUNCH to 3.0 / 9.0,
                MealType.AFTERNOON_SNACK to 1.0 / 9.0,
                MealType.DINNER to 2.0 / 9.0
            )
        )

        assertTrue(
            "Expected an acceptable menu, assessment was $result",
            result.status == RepertoireStatus.SUFFICIENT ||
                result.status == RepertoireStatus.ROBUST
        )
    }

    private fun rule(id: Long, frequency: PlanningFrequency = PlanningFrequency.NORMAL) = PlanningRule(
        itemKind = PlannedItemKind.FOOD,
        itemId = id,
        allowedMealTypes = setOf(MealType.LUNCH),
        frequency = frequency,
        preferredGrams = 100.0
    )

    private fun food(
        id: Long,
        name: String,
        category: FoodCategory,
        calories: Double,
        protein: Double,
        carbs: Double,
        fat: Double
    ) = Food(id, name, category, calories, fat, carbs, protein, 0.0)
}
