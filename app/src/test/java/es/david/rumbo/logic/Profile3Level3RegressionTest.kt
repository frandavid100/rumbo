package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealDistributionPolicy
import es.david.rumbo.model.MealType
import es.david.rumbo.model.NutritionToleranceSettings
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Regression reconstructed from profile "3" in the 2026-08-19 backup. */
class Profile3Level3RegressionTest {
    private val target = Recommendation(1875, 154, 198, 52, "Perfil 3 · 2026-08-19")

    @Before
    fun resetPolicies() {
        CulinaryPolicy.configure(emptyList())
        WeeklyMenuAcceptancePolicy.configure(NutritionToleranceSettings())
    }

    private val foods = listOf(
        food(5751811545638569543L, FoodCategory.PROTEIN, 74.0, 17.0, 0.5, 0.5, null, 150.0, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
        food(5304878835083443904L, FoodCategory.PROTEIN, 82.0, 16.0, 2.2, 1.0, 0.0, 150.0, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
        food(4075357459513694932L, FoodCategory.PROTEIN, 75.0, 14.0, 3.5, 1.0, null, 150.0, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
        food(4220455841940971398L, FoodCategory.PROTEIN, 81.0, 12.0, 6.0, 1.0, null, 150.0, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
        food(5964066046420395539L, FoodCategory.PROTEIN, 187.0, 26.0, 0.0, 9.4, null, 170.0, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
        food(5104378881460984000L, FoodCategory.PROTEIN, 181.0, 23.0, 0.0, 11.0, null, 170.0, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
        food(5997987558082491165L, FoodCategory.PROTEIN, 190.0, 20.0, 0.0, 12.0, null, 150.0, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
        food(5815299555744021797L, FoodCategory.PROTEIN, 56.7, 11.0, 6.2, 1.6, 1.0, 100.0, setOf("DESSERT", "STANDALONE")),
        food(4910937687832180890L, FoodCategory.PROTEIN, 213.3, 34.0, 0.5, 10.0, 0.0, 40.0, setOf("SANDWICH_FILLING", "STANDALONE", "TOPPING")),
        food(4713451237391941996L, FoodCategory.PROTEIN, 50.0, 8.2, 4.4, 0.0, 0.0, 150.0, setOf("CEREAL_BASE", "DESSERT", "POWDER_BASE", "STANDALONE")),
        food(5998252704584821415L, FoodCategory.PROTEIN, 70.0, 10.0, 4.1, 1.5, 0.0, 100.0, setOf("DESSERT", "STANDALONE")),
        food(4050314969728461425L, FoodCategory.PROTEIN, 214.0, 30.0, 1.0, 10.0, null, 50.0, setOf("SANDWICH_FILLING", "STANDALONE", "TOPPING")),
        food(5675782418107809078L, FoodCategory.PROTEIN, 41.0, 4.4, 5.5, 0.5, 0.0, 150.0, setOf("CEREAL_BASE", "DESSERT", "POWDER_BASE", "STANDALONE")),
        food(5065604127361444435L, FoodCategory.CARBOHYDRATE, 354.0, 6.7, 80.0, 0.0, 1.0, 80.0, setOf("PLATE_BASE", "SIDE")),
        food(4374284991780745501L, FoodCategory.CARBOHYDRATE, 351.0, 7.0, 79.0, 0.8, 0.0, 80.0, setOf("PLATE_BASE", "SIDE")),
        food(4287477524991240334L, FoodCategory.CARBOHYDRATE, 351.0, 7.0, 79.0, 0.8, 0.0, 80.0, setOf("PLATE_BASE", "SIDE")),
        food(4272082513170580006L, FoodCategory.CARBOHYDRATE, 162.0, 3.1, 36.0, 0.0, 2.7, 250.0, setOf("PLATE_BASE", "SIDE")),
        food(5402871438372737346L, FoodCategory.CARBOHYDRATE, 353.0, 7.3, 78.0, 1.0, null, 80.0, setOf("PLATE_BASE", "SIDE")),
        food(4373007081554746702L, FoodCategory.VEGETABLE, 15.0, 1.3, 0.9, 0.5, 1.9, 80.0, setOf("SIDE", "STANDALONE", "TOPPING")),
        food(4494907683069959481L, FoodCategory.VEGETABLE, 255.0, 6.4, 44.0, 1.8, 23.0, 200.0, setOf("SIDE", "TOPPING")),
        food(5604755577279215131L, FoodCategory.VEGETABLE, 28.0, 0.6, 4.4, 0.5, 2.3, 200.0, setOf("SIDE", "TOPPING")),
        food(5412212443169419885L, FoodCategory.VEGETABLE, 24.0, 1.4, 2.7, 0.0, 1.3, 200.0, setOf("SIDE", "TOPPING")),
        food(4108023238282100017L, FoodCategory.VEGETABLE, 78.0, 1.1, 6.5, 4.7, 2.5, 200.0, setOf("SIDE", "TOPPING")),
        food(4392226846147210209L, FoodCategory.FRUIT, 59.0, 0.6, 13.0, 0.5, 1.3, 150.0, setOf("DESSERT", "STANDALONE")),
        food(4423635198821568210L, FoodCategory.FRUIT, 233.0, 2.5, 51.0, 0.7, 6.3, 30.0, setOf("DESSERT", "STANDALONE", "TOPPING")),
        food(4866047237089294781L, FoodCategory.FRUIT, 307.0, 1.6, 71.0, 1.2, 3.8, 30.0, setOf("DESSERT", "STANDALONE", "TOPPING")),
        food(4824921464295006360L, FoodCategory.FRUIT, 342.0, 0.0, 85.0, 0.0, 1.0, 30.0, setOf("DESSERT", "STANDALONE", "TOPPING"))
    ).associateBy { it.id }

    private val rules = listOf(
        rule(5751811545638569543L, MealType.LUNCH, MealType.DINNER),
        rule(5304878835083443904L, MealType.LUNCH, MealType.DINNER),
        rule(4075357459513694932L, MealType.LUNCH, MealType.DINNER),
        rule(4220455841940971398L, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        rule(5964066046420395539L, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        rule(5104378881460984000L, MealType.LUNCH, MealType.DINNER),
        rule(5997987558082491165L, MealType.LUNCH, MealType.DINNER),
        rule(5815299555744021797L, MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER),
        rule(4910937687832180890L, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        rule(4713451237391941996L, MealType.BREAKFAST),
        rule(5998252704584821415L, MealType.LUNCH, MealType.DINNER),
        rule(4050314969728461425L, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        rule(5675782418107809078L, MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER),
        rule(5065604127361444435L, MealType.LUNCH),
        rule(4374284991780745501L, MealType.LUNCH),
        rule(4287477524991240334L, MealType.LUNCH),
        rule(4272082513170580006L, MealType.LUNCH),
        rule(5402871438372737346L, MealType.LUNCH),
        rule(4373007081554746702L, MealType.DINNER, MealType.LUNCH),
        rule(4494907683069959481L, MealType.LUNCH),
        rule(5604755577279215131L, MealType.LUNCH, MealType.DINNER),
        rule(5412212443169419885L, MealType.LUNCH),
        rule(4108023238282100017L, MealType.DINNER),
        rule(4392226846147210209L, MealType.LUNCH, MealType.DINNER),
        rule(4423635198821568210L, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        rule(4866047237089294781L, MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        rule(4824921464295006360L, MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK)
    )

    private val complete = CertifiedDayWitness(
        level = CertifiedDayLevel.COMPLETE,
        seed = 701L,
        day = WeekDay.MONDAY,
        meals = listOf(
            meal(1L, MealType.BREAKFAST,
                4713451237391941996L to 126.0,
                5675782418107809078L to 100.0,
                5815299555744021797L to 40.0),
            meal(2L, MealType.MORNING_SNACK,
                5964066046420395539L to 93.0,
                4050314969728461425L to 14.0,
                4910937687832180890L to 11.0),
            meal(3L, MealType.LUNCH,
                4494907683069959481L to 71.0,
                4392226846147210209L to 125.0,
                4374284991780745501L to 99.0,
                5065604127361444435L to 40.0),
            meal(4L, MealType.AFTERNOON_SNACK,
                5964066046420395539L to 146.0,
                4050314969728461425L to 32.0,
                4910937687832180890L to 32.0),
            meal(5L, MealType.DINNER,
                5604755577279215131L to 223.0,
                4392226846147210209L to 125.0,
                5675782418107809078L to 200.0,
                5997987558082491165L to 93.0)
        )
    )

    @Test
    fun persistedCompleteWitnessRemainsCompleteAndSearchCanReachLevel3() {
        assertTrue(
            "El testigo COMPLETE persistido del perfil 3 debe seguir siendo válido",
            CertifiedDayWitnessEvaluator.isComplete(
                complete, rules, foods, emptyMap(), target, MealDistributionPolicy.defaults
            )
        )

        val result = CulinarilySatisfactoryDaySearch.find(
            rules = rules,
            foodsById = foods,
            dishesById = emptyMap(),
            recommendation = target,
            mealShares = MealDistributionPolicy.defaults,
            baselineCompleteWitness = complete
        )
        val detail = result.diagnostic?.issues?.joinToString(" | ") { issue ->
            "${issue.mealType}:${issue.kind}:${issue.foodName}:${issue.roles.joinToString()}"
        }.orEmpty()
        assertNotNull("El perfil 3 no alcanzó nivel 3. Diagnóstico: $detail", result.witness)
        assertTrue(
            CulinarySatisfactionEvaluator.isCulinarilySatisfactory(
                result.witness!!, rules, foods, emptyMap(), target, MealDistributionPolicy.defaults
            )
        )
    }

    private fun meal(id: Long, type: MealType, vararg entries: Pair<Long, Double>) = PlannedMeal(
        id = id,
        type = type,
        days = setOf(WeekDay.MONDAY),
        items = entries.map { (foodId, grams) -> PlannedFood(foodId, grams, false) }
    )

    private fun rule(id: Long, vararg meals: MealType) = PlanningRule(
        itemKind = PlannedItemKind.FOOD,
        itemId = id,
        allowedMealTypes = meals.toSet(),
        frequency = PlanningFrequency.NORMAL,
        preferredGrams = 100.0,
        minimumFactor = 0.5,
        maximumFactor = 1.5
    )

    private fun food(
        id: Long,
        category: FoodCategory,
        calories: Double,
        protein: Double,
        carbohydrates: Double,
        fat: Double,
        fiber: Double?,
        basis: Double,
        roles: Set<String>
    ) = Food(
        id = id,
        name = "F$id",
        category = category,
        calories = calories,
        fatGrams = fat,
        carbohydrateGrams = carbohydrates,
        proteinGrams = protein,
        fiberGrams = fiber,
        portionBasisGrams = basis,
        culinaryRoles = roles
    )
}
