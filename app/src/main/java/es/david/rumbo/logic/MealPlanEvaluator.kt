package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.Dish
import es.david.rumbo.model.MealType
import es.david.rumbo.model.NutritionTotals
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import es.david.rumbo.model.nutrition
import kotlin.math.abs

enum class TargetFit {
    ON_TARGET,
    CLOSE,
    OUTSIDE,
    INCOMPLETE
}

data class NutritionTarget(
    val calories: Double,
    val proteinGrams: Double,
    val carbohydrateGrams: Double,
    val fatGrams: Double
)

data class NutrientFits(
    val calories: TargetFit,
    val protein: TargetFit,
    val carbohydrates: TargetFit,
    val fat: TargetFit
) {
    val overall: TargetFit
        get() = listOf(calories, protein, carbohydrates, fat).maxBy { it.ordinal }
}

data class PlanNutritionAssessment(
    val actual: NutritionTotals,
    val target: NutritionTarget,
    val fits: NutrientFits,
    val missingMealTypes: List<MealType> = emptyList()
) {
    val overall: TargetFit
        get() = if (missingMealTypes.isNotEmpty()) TargetFit.INCOMPLETE else fits.overall
}

object MealPlanEvaluator {
    private const val ON_TARGET_TOLERANCE = 0.10
    private const val CLOSE_TOLERANCE = 0.20
    private val mealShare = 1.0 / MealType.entries.size

    fun mealTarget(recommendation: Recommendation): NutritionTarget =
        dailyTarget(recommendation).scaled(mealShare)

    fun assessMeal(
        meal: PlannedMeal,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation
    ): PlanNutritionAssessment = assess(meal.nutrition(foodsById, dishesById), mealTarget(recommendation))

    fun assessDay(
        day: WeekDay,
        meals: List<PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation
    ): PlanNutritionAssessment {
        val dayMeals = meals.filter { day in it.days }
        val actual = dayMeals.fold(NutritionTotals()) { total, meal ->
            total + meal.nutrition(foodsById, dishesById)
        }
        val presentTypes = dayMeals.mapTo(mutableSetOf()) { it.type }
        val missing = MealType.entries.filterNot(presentTypes::contains)
        return assess(actual, dailyTarget(recommendation)).copy(missingMealTypes = missing)
    }

    fun weeklyFoodAmounts(
        meals: List<PlannedMeal>,
        dishesById: Map<Long, Dish>
    ): Map<Long, Double> {
        val totals = mutableMapOf<Long, Double>()
        meals.forEach { meal ->
            meal.items.forEach { item ->
                totals[item.foodId] = totals.getOrDefault(item.foodId, 0.0) +
                    item.grams * meal.days.size
            }
            meal.dishes.forEach { plannedDish ->
                dishesById[plannedDish.dishId]?.ingredients?.forEach { ingredient ->
                    totals[ingredient.foodId] = totals.getOrDefault(ingredient.foodId, 0.0) +
                        ingredient.grams * plannedDish.servings * meal.days.size
                }
            }
        }
        return totals
    }

    fun dailyTarget(recommendation: Recommendation): NutritionTarget = NutritionTarget(
        calories = recommendation.calories.toDouble(),
        proteinGrams = recommendation.proteinGrams.toDouble(),
        carbohydrateGrams = recommendation.carbohydrateGrams.toDouble(),
        fatGrams = recommendation.fatGrams.toDouble()
    )

    private fun assess(actual: NutritionTotals, target: NutritionTarget): PlanNutritionAssessment {
        if (!actual.isComplete) {
            return PlanNutritionAssessment(
                actual = actual,
                target = target,
                fits = NutrientFits(
                    TargetFit.INCOMPLETE,
                    TargetFit.INCOMPLETE,
                    TargetFit.INCOMPLETE,
                    TargetFit.INCOMPLETE
                )
            )
        }
        return PlanNutritionAssessment(
            actual = actual,
            target = target,
            fits = NutrientFits(
                calories = fit(actual.calories, target.calories),
                protein = fit(actual.proteinGrams, target.proteinGrams),
                carbohydrates = fit(actual.carbohydrateGrams, target.carbohydrateGrams),
                fat = fit(actual.fatGrams, target.fatGrams)
            )
        )
    }

    private fun fit(actual: Double, target: Double): TargetFit {
        if (target <= 0.0) return if (actual == 0.0) TargetFit.ON_TARGET else TargetFit.OUTSIDE
        val difference = abs(actual - target) / target
        return when {
            difference <= ON_TARGET_TOLERANCE -> TargetFit.ON_TARGET
            difference <= CLOSE_TOLERANCE -> TargetFit.CLOSE
            else -> TargetFit.OUTSIDE
        }
    }

    private fun NutritionTarget.scaled(factor: Double) = NutritionTarget(
        calories = calories * factor,
        proteinGrams = proteinGrams * factor,
        carbohydrateGrams = carbohydrateGrams * factor,
        fatGrams = fatGrams * factor
    )

    private operator fun NutritionTotals.plus(other: NutritionTotals) = NutritionTotals(
        calories = calories + other.calories,
        proteinGrams = proteinGrams + other.proteinGrams,
        carbohydrateGrams = carbohydrateGrams + other.carbohydrateGrams,
        fatGrams = fatGrams + other.fatGrams,
        fiberGrams = fiberGrams + other.fiberGrams,
        isComplete = isComplete && other.isComplete
    )
}
