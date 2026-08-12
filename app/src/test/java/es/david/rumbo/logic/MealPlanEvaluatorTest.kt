package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.MealDayAmounts
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import org.junit.Assert.assertEquals
import org.junit.Test

class MealPlanEvaluatorTest {
    private val recommendation = Recommendation(
        calories = 2000,
        proteinGrams = 100,
        carbohydrateGrams = 250,
        fatGrams = 60,
        reason = "Prueba"
    )
    private val balancedMeal = Food(
        id = 1,
        name = "Comida de prueba",
        category = FoodCategory.OTHER,
        calories = 400.0,
        proteinGrams = 20.0,
        carbohydrateGrams = 50.0,
        fatGrams = 12.0,
        fiberGrams = 5.0
    )
    private val foods = mapOf(balancedMeal.id to balancedMeal)

    @Test
    fun eachOfFiveMealsReceivesTwentyPercentOfDailyTarget() {
        val target = MealPlanEvaluator.mealTarget(recommendation)

        assertEquals(400.0, target.calories, 0.001)
        assertEquals(20.0, target.proteinGrams, 0.001)
        assertEquals(50.0, target.carbohydrateGrams, 0.001)
        assertEquals(12.0, target.fatGrams, 0.001)
    }

    @Test
    fun mealFitDistinguishesTargetCloseAndOutside() {
        fun meal(grams: Double) = PlannedMeal(
            id = grams.toLong() + 1,
            type = MealType.BREAKFAST,
            days = setOf(WeekDay.MONDAY),
            items = listOf(PlannedFood(balancedMeal.id, grams))
        )

        assertEquals(
            TargetFit.ON_TARGET,
            MealPlanEvaluator.assessMeal(meal(100.0), foods, emptyMap(), recommendation).overall
        )
        assertEquals(
            TargetFit.CLOSE,
            MealPlanEvaluator.assessMeal(meal(115.0), foods, emptyMap(), recommendation).overall
        )
        assertEquals(
            TargetFit.OUTSIDE,
            MealPlanEvaluator.assessMeal(meal(140.0), foods, emptyMap(), recommendation).overall
        )
    }

    @Test
    fun trivialDifferencesShareTheOptimalBand() {
        assertEquals(
            TargetFit.ON_TARGET,
            NutritionTolerancePolicy.evaluate(NutrientKind.CALORIES, 1985.0, 2000.0).fit
        )
        assertEquals(
            TargetFit.ON_TARGET,
            NutritionTolerancePolicy.evaluate(NutrientKind.PROTEIN, 147.0, 150.0).fit
        )
        assertEquals(
            0.0,
            NutritionTolerancePolicy.evaluate(NutrientKind.PROTEIN, 147.0, 150.0).penalty,
            0.0
        )
    }

    @Test
    fun relevantProteinDeficitIsOutsideAndAsymmetric() {
        val low = NutritionTolerancePolicy.evaluate(NutrientKind.PROTEIN, 115.0, 150.0)
        val equallyHigh = NutritionTolerancePolicy.evaluate(NutrientKind.PROTEIN, 185.0, 150.0)

        assertEquals(TargetFit.OUTSIDE, low.fit)
        assertEquals(TargetFit.OUTSIDE, equallyHigh.fit)
        org.junit.Assert.assertTrue(low.penalty > equallyHigh.penalty)
    }

    @Test
    fun completeDayAddsAllMealsAndMatchesDailyTarget() {
        val meals = MealType.entries.mapIndexed { index, type ->
            PlannedMeal(
                id = index.toLong() + 1,
                type = type,
                days = setOf(WeekDay.MONDAY),
                items = listOf(PlannedFood(balancedMeal.id, 100.0))
            )
        }

        val result = MealPlanEvaluator.assessDay(WeekDay.MONDAY, meals, foods, emptyMap(), recommendation)

        assertEquals(TargetFit.ON_TARGET, result.overall)
        assertEquals(2000.0, result.actual.calories, 0.001)
        assertEquals(emptyList<MealType>(), result.missingMealTypes)
    }

    @Test
    fun dayIsIncompleteWhenAnyMealTypeIsMissing() {
        val breakfast = PlannedMeal(
            id = 1,
            type = MealType.BREAKFAST,
            days = setOf(WeekDay.MONDAY),
            items = listOf(PlannedFood(balancedMeal.id, 100.0))
        )

        val result = MealPlanEvaluator.assessDay(
            WeekDay.MONDAY,
            listOf(breakfast),
            foods,
            emptyMap(),
            recommendation
        )

        assertEquals(TargetFit.INCOMPLETE, result.overall)
        assertEquals(4, result.missingMealTypes.size)
    }

    @Test
    fun shoppingAmountsMultiplyEachMealByItsAssignedDays() {
        val breakfast = PlannedMeal(
            id = 1,
            type = MealType.BREAKFAST,
            days = setOf(WeekDay.MONDAY, WeekDay.TUESDAY, WeekDay.WEDNESDAY),
            items = listOf(PlannedFood(balancedMeal.id, 100.0))
        )
        val dinner = PlannedMeal(
            id = 2,
            type = MealType.DINNER,
            days = setOf(WeekDay.MONDAY, WeekDay.FRIDAY),
            items = listOf(PlannedFood(balancedMeal.id, 50.0))
        )

        val amounts = MealPlanEvaluator.weeklyFoodAmounts(listOf(breakfast, dinner), emptyMap())

        assertEquals(400.0, amounts.getValue(balancedMeal.id), 0.001)
    }

    @Test
    fun shoppingAmountsExpandDishesFromPlannedGrams() {
        val dish = es.david.rumbo.model.Dish(
            id = 20,
            name = "Batido",
            ingredients = listOf(es.david.rumbo.model.DishIngredient(balancedMeal.id, 100.0))
        )
        val breakfast = PlannedMeal(
            id = 1,
            type = MealType.BREAKFAST,
            days = setOf(WeekDay.MONDAY, WeekDay.TUESDAY),
            dishes = listOf(es.david.rumbo.model.PlannedDish(dish.id, 150.0))
        )

        val amounts = MealPlanEvaluator.weeklyFoodAmounts(listOf(breakfast), mapOf(dish.id to dish))

        assertEquals(300.0, amounts.getValue(balancedMeal.id), 0.001)
    }

    @Test
    fun shoppingAmountsUseEachDaysResolvedAmount() {
        val adjustable = PlannedFood(balancedMeal.id, 100.0, true, 50.0, 200.0)
        val breakfast = PlannedMeal(
            id = 1,
            type = MealType.BREAKFAST,
            days = setOf(WeekDay.MONDAY, WeekDay.TUESDAY),
            items = listOf(adjustable),
            dayAmounts = listOf(
                MealDayAmounts(WeekDay.MONDAY, foodGrams = mapOf(balancedMeal.id to 80.0)),
                MealDayAmounts(WeekDay.TUESDAY, foodGrams = mapOf(balancedMeal.id to 130.0))
            )
        )

        val amounts = MealPlanEvaluator.weeklyFoodAmounts(listOf(breakfast), emptyMap())

        assertEquals(210.0, amounts.getValue(balancedMeal.id), 0.001)
    }
}
