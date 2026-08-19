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
import org.junit.Assert.assertTrue
import org.junit.Test

class Profile5AutomaticLevel1Test {
    @Test
    fun completedInitialRequestsProduceViableDayWithoutUserRetry() {
        fun food(
            id: Long, category: FoodCategory, calories: Double, protein: Double,
            carbs: Double, fat: Double, fiber: Double?, portion: Double,
            nutritional: Set<String>, culinary: Set<String>
        ) = Food(
            id = id, name = "Alimento $id", category = category,
            calories = calories, fatGrams = fat, carbohydrateGrams = carbs,
            proteinGrams = protein, fiberGrams = fiber,
            portionBasisGrams = portion, nutritionalRoles = nutritional,
            culinaryRoles = culinary
        )
        val foods = listOf(
            food(4217125742152372452, FoodCategory.PROTEIN, 96.0, 24.0, 0.0, .5, 0.0, 170.0, setOf("PRIMARY_PROTEIN"), setOf("PLATE_CENTER", "SANDWICH_FILLING")),
            food(4406634283030157560, FoodCategory.PROTEIN, 74.0, 17.0, .5, .5, null, 150.0, setOf("PRIMARY_PROTEIN"), setOf("PLATE_CENTER", "SANDWICH_FILLING")),
            food(5138918923368881607, FoodCategory.PROTEIN, 50.0, 11.0, 0.0, .7, null, 170.0, setOf("PRIMARY_PROTEIN"), setOf("PLATE_CENTER", "SANDWICH_FILLING")),
            food(5815299555744021797, FoodCategory.PROTEIN, 56.7, 11.0, 6.2, 1.6, 1.0, 100.0, setOf("COMPLEMENTARY_PROTEIN"), setOf("DESSERT", "STANDALONE")),
            food(4713451237391941996, FoodCategory.PROTEIN, 50.0, 8.2, 4.4, 0.0, 0.0, 150.0, setOf("COMPLEMENTARY_PROTEIN"), setOf("CEREAL_BASE", "DESSERT", "POWDER_BASE", "STANDALONE")),
            food(4910937687832180890, FoodCategory.PROTEIN, 213.3, 34.0, .5, 10.0, 0.0, 40.0, setOf("COMPLEMENTARY_PROTEIN"), setOf("SANDWICH_FILLING", "STANDALONE", "TOPPING")),
            food(4165202278542344017, FoodCategory.PROTEIN, 258.0, 35.0, .5, 13.0, null, 50.0, setOf("COMPLEMENTARY_PROTEIN", "COMPLEMENTARY_FAT"), setOf("SANDWICH_FILLING", "STANDALONE", "TOPPING")),
            food(5065604127361444435, FoodCategory.CARBOHYDRATE, 354.0, 6.7, 80.0, 0.0, 1.0, 80.0, setOf("PRIMARY_CARBOHYDRATE"), setOf("PLATE_BASE", "SIDE")),
            food(4287477524991240334, FoodCategory.CARBOHYDRATE, 351.0, 7.0, 79.0, .8, 0.0, 80.0, setOf("PRIMARY_CARBOHYDRATE"), setOf("PLATE_BASE", "SIDE")),
            food(4272082513170580006, FoodCategory.CARBOHYDRATE, 162.0, 3.1, 36.0, 0.0, 2.7, 250.0, setOf("PRIMARY_CARBOHYDRATE"), setOf("PLATE_BASE", "SIDE")),
            food(5709129380453908370, FoodCategory.FRUIT, 35.0, .4, 9.1, .4, 2.1, 150.0, setOf("COMPLEMENTARY_CARBOHYDRATE", "FRUIT"), setOf("DESSERT", "STANDALONE")),
            food(5052073938946012126, FoodCategory.CARBOHYDRATE, 333.0, 3.5, 90.0, .5, null, 100.0, setOf("COMPLEMENTARY_CARBOHYDRATE"), setOf("DESSERT", "STANDALONE")),
            food(4171607839944345756, FoodCategory.CARBOHYDRATE, 76.0, 0.0, 19.0, 0.0, 0.0, 100.0, setOf("COMPLEMENTARY_CARBOHYDRATE"), setOf("DESSERT", "STANDALONE")),
            food(4042487276430228545, FoodCategory.FAT, 824.0, 0.0, 0.0, 92.0, null, 10.0, setOf("CONCENTRATED_FAT"), setOf("COOKING_MEDIUM", "SAUCE_DRESSING")),
            food(5167803696619229883, FoodCategory.FAT, 492.8, .8, 3.0, 70.0, 0.0, 40.0, setOf("COMPLEMENTARY_FAT"), setOf("SAUCE_DRESSING", "TOPPING")),
            food(4011971294699118962, FoodCategory.FAT, 171.0, .5, 0.0, 18.0, 3.0, 30.0, setOf("COMPLEMENTARY_FAT"), setOf("STANDALONE", "TOPPING"))
        ).associateBy { it.id }
        fun rule(id: Long, vararg meals: MealType) = PlanningRule(
            PlannedItemKind.FOOD, id, meals.toSet(), frequency = PlanningFrequency.NORMAL,
            preferredGrams = 100.0, minimumFactor = .5, maximumFactor = 1.5
        )
        val rules = listOf(
            rule(4217125742152372452, MealType.LUNCH, MealType.DINNER),
            rule(4406634283030157560, MealType.LUNCH, MealType.DINNER),
            rule(5138918923368881607, MealType.LUNCH, MealType.DINNER),
            rule(5815299555744021797, MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER),
            rule(4713451237391941996, *MealType.entries.toTypedArray()),
            rule(4910937687832180890, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
            rule(4165202278542344017, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
            rule(5065604127361444435, MealType.LUNCH),
            rule(4287477524991240334, MealType.LUNCH),
            rule(4272082513170580006, MealType.LUNCH, MealType.DINNER),
            rule(5709129380453908370, MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER),
            rule(5052073938946012126, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
            rule(4171607839944345756, MealType.LUNCH),
            rule(4042487276430228545, *MealType.entries.toTypedArray()),
            rule(5167803696619229883, MealType.BREAKFAST),
            rule(4011971294699118962, MealType.LUNCH, MealType.DINNER)
        )
        val result = RepertoireEvaluator.evaluateAutomatically(
            rules = rules,
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

        assertEquals("Profile 5 assessment: $result", ConstraintSearchStatus.FEASIBLE, result.searchStatus)
        assertNotNull(result.witness)
        assertTrue(
            "El nivel 1 no puede sustituir las categorías principales por complementarias",
            MajorNutritionalRolePolicy.hasAllRequiredRoles(
                result.witness!!.meals, foods, emptyMap()
            )
        )
    }
}
