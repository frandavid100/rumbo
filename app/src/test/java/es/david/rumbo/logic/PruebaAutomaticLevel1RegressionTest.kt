package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

/** Regression reconstructed from profile "Prueba" in the 2026-08-19 backup. */
class PruebaAutomaticLevel1RegressionTest {
    @Test
    fun completedRequestsProduceViableDayAutomatically() {
        val foods = listOf(
            food(5751811545638569543L, FoodCategory.PROTEIN, 74.0, 17.0, .5, .5, null, 150.0, setOf("PRIMARY_PROTEIN"), setOf("PLATE_CENTER", "SANDWICH_FILLING")),
            food(4075357459513694932L, FoodCategory.PROTEIN, 75.0, 14.0, 3.5, 1.0, null, 150.0, setOf("PRIMARY_PROTEIN"), setOf("PLATE_CENTER", "SANDWICH_FILLING")),
            food(5128157429893053819L, FoodCategory.PROTEIN, 146.0, 11.9, 5.3, 7.7, null, 170.0, setOf("PRIMARY_PROTEIN"), setOf("PLATE_CENTER", "SANDWICH_FILLING")),
            food(4713451237391941996L, FoodCategory.PROTEIN, 50.0, 8.2, 4.4, 0.0, 0.0, 150.0, setOf("COMPLEMENTARY_PROTEIN"), setOf("CEREAL_BASE", "DESSERT", "POWDER_BASE", "STANDALONE")),
            food(4050314969728461425L, FoodCategory.PROTEIN, 214.0, 30.0, 1.0, 10.0, null, 50.0, setOf("COMPLEMENTARY_PROTEIN", "COMPLEMENTARY_FAT"), setOf("SANDWICH_FILLING", "STANDALONE", "TOPPING")),
            food(4897354112511112087L, FoodCategory.PROTEIN, 164.0, 18.5, 5.5, 7.5, null, 40.0, setOf("COMPLEMENTARY_PROTEIN"), setOf("SANDWICH_FILLING", "STANDALONE", "TOPPING")),
            food(5402871438372737346L, FoodCategory.CARBOHYDRATE, 353.0, 7.3, 78.0, 1.0, null, 80.0, setOf("PRIMARY_CARBOHYDRATE"), setOf("PLATE_BASE", "SIDE")),
            food(4374284991780745501L, FoodCategory.CARBOHYDRATE, 351.0, 7.0, 79.0, .8, 0.0, 80.0, setOf("PRIMARY_CARBOHYDRATE"), setOf("PLATE_BASE", "SIDE")),
            food(4530255594904942386L, FoodCategory.CARBOHYDRATE, 155.2, 3.7, 34.0, .5, 2.7, 250.0, setOf("PRIMARY_CARBOHYDRATE"), setOf("PLATE_BASE", "SIDE")),
            food(5208127188538238156L, FoodCategory.CARBOHYDRATE, 105.0, 3.1, 17.0, 2.8, 0.0, 100.0, setOf("COMPLEMENTARY_CARBOHYDRATE"), setOf("DESSERT", "STANDALONE")),
            food(5702260474992216514L, FoodCategory.CARBOHYDRATE, 58.0, 3.0, 9.2, 1.0, null, 250.0, setOf("COMPLEMENTARY_CARBOHYDRATE"), setOf("BEVERAGE", "STANDALONE")),
            food(5420910120549914128L, FoodCategory.CARBOHYDRATE, 77.0, 3.0, 11.9, 1.9, null, 150.0, setOf("COMPLEMENTARY_CARBOHYDRATE"), setOf("CEREAL_BASE", "DESSERT", "POWDER_BASE", "STANDALONE")),
            food(4042487276430228545L, FoodCategory.FAT, 824.0, 0.0, 0.0, 92.0, null, 10.0, setOf("CONCENTRATED_FAT"), setOf("COOKING_MEDIUM", "SAUCE_DRESSING")),
            food(4837621600519529960L, FoodCategory.FAT, 476.3, 5.8, 9.0, 46.0, 1.9, 40.0, setOf("COMPLEMENTARY_FAT"), setOf("SAUCE_DRESSING", "TOPPING")),
            food(5752944780387762276L, FoodCategory.PROTEIN, 486.0, 23.0, 1.8, 43.0, null, 50.0, setOf("COMPLEMENTARY_PROTEIN", "COMPLEMENTARY_FAT"), setOf("SANDWICH_FILLING", "STANDALONE", "TOPPING"))
        ).associateBy { it.id }
        fun rule(id: Long, vararg meals: MealType) = PlanningRule(
            PlannedItemKind.FOOD, id, meals.toSet(), frequency = PlanningFrequency.NORMAL,
            preferredGrams = 100.0, minimumFactor = .5, maximumFactor = 1.5
        )
        val rules = listOf(
            rule(5751811545638569543L, MealType.LUNCH, MealType.DINNER),
            rule(4075357459513694932L, MealType.LUNCH, MealType.DINNER),
            rule(5128157429893053819L, MealType.LUNCH, MealType.DINNER),
            rule(4713451237391941996L, MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER),
            rule(4050314969728461425L, MealType.LUNCH, MealType.AFTERNOON_SNACK, MealType.DINNER, MealType.MORNING_SNACK),
            rule(4897354112511112087L, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
            rule(5402871438372737346L, MealType.LUNCH),
            rule(4374284991780745501L, MealType.LUNCH),
            rule(4530255594904942386L, MealType.LUNCH, MealType.DINNER),
            rule(5208127188538238156L, MealType.LUNCH, MealType.DINNER),
            rule(5702260474992216514L, MealType.LUNCH, MealType.DINNER),
            rule(5420910120549914128L, MealType.LUNCH, MealType.DINNER),
            rule(4042487276430228545L, MealType.LUNCH, MealType.DINNER, MealType.AFTERNOON_SNACK, MealType.MORNING_SNACK),
            rule(4837621600519529960L, MealType.LUNCH),
            rule(5752944780387762276L, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK)
        )
        val result = RepertoireEvaluator.evaluateAutomatically(
            rules, foods, emptyMap(), Recommendation(1875, 154, 198, 52, "Prueba"),
            mapOf(MealType.BREAKFAST to 2.0/9, MealType.MORNING_SNACK to 1.0/9,
                MealType.LUNCH to 3.0/9, MealType.AFTERNOON_SNACK to 1.0/9, MealType.DINNER to 2.0/9)
        )
        assertEquals("Prueba assessment: $result", ConstraintSearchStatus.FEASIBLE, result.searchStatus)
        assertNotNull(result.witness)
    }

    private fun food(
        id: Long, category: FoodCategory, calories: Double, protein: Double, carbs: Double,
        fat: Double, fiber: Double?, portion: Double, nutritional: Set<String>, culinary: Set<String>
    ) = Food(id = id, name = "Alimento $id", category = category, calories = calories,
        fatGrams = fat, carbohydrateGrams = carbs, proteinGrams = protein, fiberGrams = fiber,
        portionBasisGrams = portion, nutritionalRoles = nutritional, culinaryRoles = culinary)
}
