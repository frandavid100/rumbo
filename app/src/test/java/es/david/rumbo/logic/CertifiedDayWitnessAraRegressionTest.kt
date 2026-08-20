package es.david.rumbo.logic

import es.david.rumbo.model.*
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CertifiedDayWitnessAraRegressionTest {
    private val target = Recommendation(1675, 105, 208, 47, "Ara 2026-08-18")

    private fun food(
        id: Long,
        category: FoodCategory,
        calories: Double,
        protein: Double,
        carbohydrates: Double,
        fat: Double,
        fiber: Double?,
        culinaryRoles: Set<String>
    ) = Food(
        id = id,
        name = "F$id",
        category = category,
        calories = calories,
        fatGrams = fat,
        carbohydrateGrams = carbohydrates,
        proteinGrams = protein,
        fiberGrams = fiber,
        culinaryRoles = culinaryRoles
    )

    private fun rule(id: Long, meals: Set<MealType>) = PlanningRule(
        itemKind = PlannedItemKind.FOOD,
        itemId = id,
        allowedMealTypes = meals,
        frequency = PlanningFrequency.NORMAL,
        preferredGrams = 100.0,
        minimumFactor = 0.5,
        maximumFactor = 1.5,
        ruleId = id
    )

    private val portionBasisById = mapOf(
        5751811545638569543L to 150.0,
        5304878835083443904L to 150.0,
        5138918923368881607L to 170.0,
        4713451237391941996L to 150.0,
        5998252704584821415L to 100.0,
        4912645548334196354L to 100.0,
        5065604127361444435L to 80.0,
        4374284991780745501L to 80.0,
        4530255594904942386L to 250.0,
        5427737837577403981L to 250.0,
        4824921464295006360L to 30.0,
        5863259172627146722L to 250.0,
        4042487276430228545L to 10.0,
        4927534216171556707L to 200.0,
        4108023238282100017L to 200.0,
        5409764689805397597L to 200.0,
        4359402894918143880L to 150.0,
        4373007081554746702L to 80.0,
        5412212443169419885L to 200.0,
        5803238462349753934L to 200.0,
        4494907683069959481L to 200.0,
        5466605370625528297L to 200.0,
        4825073144419713243L to 200.0,
        5273024687756059532L to 200.0
    )

    private val foods = listOf(
        food(5751811545638569543L, FoodCategory.PROTEIN, 74.0, 17.0, 0.5, 0.5, null, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
        food(5304878835083443904L, FoodCategory.PROTEIN, 82.0, 16.0, 2.2, 1.0, 0.0, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
        food(5138918923368881607L, FoodCategory.PROTEIN, 50.0, 11.0, 0.0, 0.7, null, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
        food(4713451237391941996L, FoodCategory.PROTEIN, 50.0, 8.2, 4.4, 0.0, 0.0, setOf("CEREAL_BASE", "DESSERT", "POWDER_BASE", "STANDALONE")),
        food(5998252704584821415L, FoodCategory.PROTEIN, 70.0, 10.0, 4.1, 1.5, 0.0, setOf("DESSERT", "STANDALONE")),
        food(4912645548334196354L, FoodCategory.PROTEIN, 82.0, 10.0, 6.0, 2.0, 2.0, setOf("DESSERT", "STANDALONE")),
        food(5065604127361444435L, FoodCategory.CARBOHYDRATE, 354.0, 6.7, 80.0, 0.0, 1.0, setOf("PLATE_BASE", "SIDE")),
        food(4374284991780745501L, FoodCategory.CARBOHYDRATE, 351.0, 7.0, 79.0, 0.8, 0.0, setOf("PLATE_BASE", "SIDE")),
        food(4530255594904942386L, FoodCategory.CARBOHYDRATE, 155.2, 3.7, 34.0, 0.5, 2.7, setOf("PLATE_BASE", "SIDE")),
        food(5427737837577403981L, FoodCategory.CARBOHYDRATE, 41.0, 0.0, 10.0, 0.0, 0.5, setOf("BEVERAGE", "STANDALONE")),
        food(4824921464295006360L, FoodCategory.FRUIT, 342.0, 0.0, 85.0, 0.0, 1.0, setOf("DESSERT", "STANDALONE", "TOPPING")),
        food(5863259172627146722L, FoodCategory.CARBOHYDRATE, 42.0, 0.4, 10.1, 0.0, null, setOf("BEVERAGE", "STANDALONE")),
        food(4042487276430228545L, FoodCategory.FAT, 824.0, 0.0, 0.0, 92.0, null, setOf("COOKING_MEDIUM", "SAUCE_DRESSING")),
        food(4927534216171556707L, FoodCategory.VEGETABLE, 78.0, 5.4, 10.0, 0.7, 5.2, setOf("SIDE", "TOPPING")),
        food(4108023238282100017L, FoodCategory.VEGETABLE, 78.0, 1.1, 6.5, 4.7, 2.5, setOf("SIDE", "TOPPING")),
        food(5409764689805397597L, FoodCategory.VEGETABLE, 77.0, 2.4, 13.0, 1.2, 3.0, setOf("SIDE", "TOPPING")),
        food(4359402894918143880L, FoodCategory.FRUIT, 323.0, 0.0, 75.0, 1.2, 5.4, setOf("DESSERT", "STANDALONE")),
        food(4373007081554746702L, FoodCategory.VEGETABLE, 15.0, 1.3, 0.9, 0.5, 1.9, setOf("SIDE", "STANDALONE", "TOPPING")),
        food(5412212443169419885L, FoodCategory.VEGETABLE, 24.0, 1.4, 2.7, 0.0, 1.3, setOf("SIDE", "TOPPING")),
        food(5803238462349753934L, FoodCategory.VEGETABLE, 32.0, 0.5, 5.0, 0.5, 3.0, setOf("SIDE", "TOPPING")),
        food(4494907683069959481L, FoodCategory.VEGETABLE, 255.0, 6.4, 44.0, 1.8, 23.0, setOf("SIDE", "TOPPING")),
        food(5466605370625528297L, FoodCategory.VEGETABLE, 30.0, 1.5, 5.4, 0.0, 1.4, setOf("SIDE", "TOPPING")),
        food(4825073144419713243L, FoodCategory.VEGETABLE, 77.0, 2.4, 11.0, 1.8, 2.9, setOf("SIDE", "TOPPING")),
        food(5273024687756059532L, FoodCategory.VEGETABLE, 15.0, 1.4, 1.6, 0.0, 1.7, setOf("SIDE", "TOPPING"))
    ).map { food ->
        food.copy(portionBasisGrams = portionBasisById[food.id])
    }.associateBy { it.id }

    private val rules = listOf(
        rule(5751811545638569543L, setOf(MealType.LUNCH, MealType.DINNER)),
        rule(5304878835083443904L, setOf(MealType.LUNCH, MealType.DINNER)),
        rule(5138918923368881607L, setOf(MealType.DINNER, MealType.LUNCH)),
        rule(4713451237391941996L, setOf(MealType.LUNCH, MealType.BREAKFAST, MealType.DINNER)),
        rule(5998252704584821415L, setOf(MealType.LUNCH, MealType.DINNER)),
        rule(4912645548334196354L, setOf(MealType.LUNCH, MealType.DINNER)),
        rule(5065604127361444435L, setOf(MealType.LUNCH)),
        rule(4374284991780745501L, setOf(MealType.LUNCH)),
        rule(4530255594904942386L, setOf(MealType.LUNCH)),
        rule(5427737837577403981L, setOf(MealType.LUNCH, MealType.DINNER, MealType.BREAKFAST)),
        rule(4824921464295006360L, setOf(MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK)),
        rule(5863259172627146722L, setOf(MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK)),
        rule(4042487276430228545L, setOf(MealType.BREAKFAST, MealType.DINNER, MealType.LUNCH, MealType.AFTERNOON_SNACK, MealType.MORNING_SNACK)),
        rule(4927534216171556707L, setOf(MealType.DINNER, MealType.LUNCH)),
        rule(4108023238282100017L, setOf(MealType.DINNER)),
        rule(5409764689805397597L, setOf(MealType.DINNER, MealType.LUNCH)),
        rule(4359402894918143880L, setOf(MealType.LUNCH, MealType.DINNER, MealType.BREAKFAST)),
        rule(4373007081554746702L, setOf(MealType.LUNCH, MealType.DINNER)),
        rule(5412212443169419885L, setOf(MealType.LUNCH, MealType.DINNER)),
        rule(5803238462349753934L, setOf(MealType.LUNCH)),
        rule(4494907683069959481L, setOf(MealType.LUNCH, MealType.DINNER)),
        rule(5466605370625528297L, setOf(MealType.DINNER, MealType.LUNCH)),
        rule(4825073144419713243L, setOf(MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK)),
        rule(5273024687756059532L, setOf(MealType.BREAKFAST))
    )

    private val baseline = CertifiedDayWitness(
        level = CertifiedDayLevel.VIABLE,
        seed = 37L,
        day = WeekDay.MONDAY,
        meals = listOf(
            PlannedMeal(
                id = 1L,
                type = MealType.BREAKFAST,
                days = setOf(WeekDay.MONDAY),
                items = listOf(
                    PlannedFood(4042487276430228545L, 10.0, true, 5.0, 15.0),
                    PlannedFood(4713451237391941996L, 200.0, true, 100.0, 350.0),
                    PlannedFood(5427737837577403981L, 250.0, true, 100.0, 500.0)
                ),
                dayAmounts = listOf(
                    MealDayAmounts(WeekDay.MONDAY, mapOf(
                        4042487276430228545L to 15.0,
                        4713451237391941996L to 200.0,
                        5427737837577403981L to 190.0
                    ))
                )
            ),
            PlannedMeal(
                id = 2L,
                type = MealType.MORNING_SNACK,
                days = setOf(WeekDay.MONDAY),
                items = listOf(
                    PlannedFood(4042487276430228545L, 10.0, true, 5.0, 15.0),
                    PlannedFood(5863259172627146722L, 250.0, true, 100.0, 500.0),
                    PlannedFood(4824921464295006360L, 20.0, true, 5.0, 60.0)
                ),
                dayAmounts = listOf(
                    MealDayAmounts(WeekDay.MONDAY, mapOf(
                        4042487276430228545L to 15.0,
                        5863259172627146722L to 100.0,
                        4824921464295006360L to 5.0
                    ))
                )
            ),
            PlannedMeal(
                id = 3L,
                type = MealType.LUNCH,
                days = setOf(WeekDay.MONDAY),
                items = listOf(
                    PlannedFood(4374284991780745501L, 100.0, true, 40.0, 300.0),
                    PlannedFood(5065604127361444435L, 100.0, true, 40.0, 300.0),
                    PlannedFood(4713451237391941996L, 200.0, true, 100.0, 350.0),
                    PlannedFood(5998252704584821415L, 125.0, true, 40.0, 250.0)
                ),
                dayAmounts = listOf(
                    MealDayAmounts(WeekDay.MONDAY, mapOf(
                        4374284991780745501L to 80.0,
                        5065604127361444435L to 40.0,
                        4713451237391941996L to 140.0,
                        5998252704584821415L to 180.0
                    ))
                )
            ),
            PlannedMeal(
                id = 4L,
                type = MealType.AFTERNOON_SNACK,
                days = setOf(WeekDay.MONDAY),
                items = listOf(
                    PlannedFood(4042487276430228545L, 10.0, true, 5.0, 15.0),
                    PlannedFood(5863259172627146722L, 250.0, true, 100.0, 500.0),
                    PlannedFood(4824921464295006360L, 20.0, true, 5.0, 60.0)
                ),
                dayAmounts = listOf(
                    MealDayAmounts(WeekDay.MONDAY, mapOf(
                        4042487276430228545L to 15.0,
                        5863259172627146722L to 180.0,
                        4824921464295006360L to 7.0
                    ))
                )
            ),
            PlannedMeal(
                id = 5L,
                type = MealType.DINNER,
                days = setOf(WeekDay.MONDAY),
                items = listOf(
                    PlannedFood(5138918923368881607L, 60.0, true, 20.0, 150.0),
                    PlannedFood(4713451237391941996L, 200.0, true, 100.0, 350.0),
                    PlannedFood(5427737837577403981L, 250.0, true, 100.0, 500.0),
                    PlannedFood(4912645548334196354L, 125.0, true, 40.0, 250.0)
                ),
                dayAmounts = listOf(
                    MealDayAmounts(WeekDay.MONDAY, mapOf(
                        5138918923368881607L to 80.0,
                        4713451237391941996L to 175.0,
                        5427737837577403981L to 180.0,
                        4912645548334196354L to 240.0
                    ))
                )
            )
        )
    )

    @Test
    fun araReachesCompleteFromHerExistingViableWitness() {
        assertTrue(
            CertifiedDayWitnessEvaluator.isViable(
                baseline, rules, foods, emptyMap(), target, MealDistributionPolicy.defaults
            )
        )

        val result = CertifiedDayWitnessEvaluator.findCompleteDay(
            rules = rules,
            foodsById = foods,
            dishesById = emptyMap(),
            recommendation = target,
            mealShares = MealDistributionPolicy.defaults,
            baselineWitness = baseline
        )

        assertNotNull(result.witness)
        assertTrue(
            CertifiedDayWitnessEvaluator.isComplete(
                result.witness!!,
                rules,
                foods,
                emptyMap(),
                target,
                MealDistributionPolicy.defaults
            )
        )
    }
    @Test
    fun araCanAdvanceFromHerCertifiedCompleteDayTowardLevel3WithoutFalseInsufficiency() {
        val complete = CertifiedDayWitnessEvaluator.findCompleteDay(
            rules = rules,
            foodsById = foods,
            dishesById = emptyMap(),
            recommendation = target,
            mealShares = MealDistributionPolicy.defaults,
            baselineWitness = baseline
        ).witness
        assertNotNull(complete)

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
        assertNotNull("Ara no alcanzó nivel 3. Diagnóstico: $detail", result.witness)
        assertTrue(
            CulinarySatisfactionEvaluator.isCulinarilySatisfactory(
                result.witness!!, rules, foods, emptyMap(), target, MealDistributionPolicy.defaults
            )
        )
    }

}
