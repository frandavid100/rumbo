package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.Dish
import es.david.rumbo.model.MealType
import es.david.rumbo.model.NutritionTotals
import es.david.rumbo.model.NutritionToleranceSettings
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import es.david.rumbo.model.nutrition
import es.david.rumbo.model.resolvedGrams
import es.david.rumbo.model.totalWeightGrams
import kotlin.math.abs

enum class TargetFit {
    ON_TARGET,
    CLOSE,
    OUTSIDE,
    INCOMPLETE
}

enum class NutrientKind { CALORIES, PROTEIN, CARBOHYDRATES, FAT }

data class NutrientTolerance(
    val optimalLowerAbsolute: Double,
    val optimalUpperAbsolute: Double,
    val adequateLowerAbsolute: Double,
    val adequateUpperAbsolute: Double,
    val outsideLowerRelative: Double,
    val outsideUpperRelative: Double
)

data class NutrientEvaluation(
    val kind: NutrientKind,
    val actual: Double,
    val target: Double,
    val fit: TargetFit,
    val difference: Double,
    val penalty: Double
)

/** Single source of truth for both menu scoring and user-facing assessment.
 * Absolute dead bands prevent meaningless optimisation; relative outer bands
 * keep the policy sensible for unusually small or large energy requirements.
 */
object NutritionTolerancePolicy {
    private val tolerances = mapOf(
        NutrientKind.CALORIES to NutrientTolerance(50.0, 50.0, 100.0, 100.0, .10, .10),
        NutrientKind.PROTEIN to NutrientTolerance(10.0, 15.0, 20.0, 30.0, .25, .35),
        NutrientKind.CARBOHYDRATES to NutrientTolerance(15.0, 15.0, 30.0, 30.0, .30, .30),
        NutrientKind.FAT to NutrientTolerance(5.0, 5.0, 10.0, 10.0, .25, .20)
    )

    fun evaluate(kind: NutrientKind, actual: Double, target: Double): NutrientEvaluation {
        if (target <= 0.0) {
            val fit = if (actual == 0.0) TargetFit.ON_TARGET else TargetFit.OUTSIDE
            return NutrientEvaluation(kind, actual, target, fit, actual, if (fit == TargetFit.ON_TARGET) 0.0 else 1.0)
        }
        val tolerance = checkNotNull(tolerances[kind])
        val difference = actual - target
        val magnitude = abs(difference)
        val optimal = if (difference < 0) tolerance.optimalLowerAbsolute else tolerance.optimalUpperAbsolute
        val adequate = if (difference < 0) tolerance.adequateLowerAbsolute else tolerance.adequateUpperAbsolute
        val outer = target * if (difference < 0) tolerance.outsideLowerRelative else tolerance.outsideUpperRelative
        val fit = when {
            magnitude <= optimal -> TargetFit.ON_TARGET
            magnitude <= maxOf(adequate, optimal) -> TargetFit.CLOSE
            else -> TargetFit.OUTSIDE
        }
        // No nutritional advantage inside the optimal band. Beyond it, grow
        // continuously so practical units and preferences can break ties.
        val scale = maxOf(outer, adequate, 1.0)
        val penalty = ((magnitude - optimal).coerceAtLeast(0.0) / scale).let { it * it }
        return NutrientEvaluation(kind, actual, target, fit, difference, penalty)
    }

    /**
     * Objective used while choosing quantities. Acceptance deliberately keeps
     * its dead bands, but optimisation must still prefer the centre of them;
     * otherwise it systematically settles at low protein/carbohydrates and
     * high fat because every point inside the band appears equally good.
     */
    fun optimizationPenalty(kind: NutrientKind, actual: Double, target: Double): Double {
        val tolerancePenalty = evaluate(kind, actual, target).penalty
        if (target <= 0.0) return tolerancePenalty
        val relativeDifference = (actual - target) / target
        return tolerancePenalty + relativeDifference * relativeDifference * 0.25
    }
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

    val evaluations: List<NutrientEvaluation>
        get() = listOf(
            NutritionTolerancePolicy.evaluate(NutrientKind.CALORIES, actual.calories, target.calories),
            NutritionTolerancePolicy.evaluate(NutrientKind.PROTEIN, actual.proteinGrams, target.proteinGrams),
            NutritionTolerancePolicy.evaluate(NutrientKind.CARBOHYDRATES, actual.carbohydrateGrams, target.carbohydrateGrams),
            NutritionTolerancePolicy.evaluate(NutrientKind.FAT, actual.fatGrams, target.fatGrams)
        )
}

object MealPlanEvaluator {
    private val mealShare = 1.0 / MealType.entries.size

    fun mealTarget(
        recommendation: Recommendation,
        share: Double = mealShare
    ): NutritionTarget = dailyTarget(recommendation).scaled(share.coerceIn(0.0, 1.0))

    fun assessMeal(
        meal: PlannedMeal,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        day: WeekDay? = null,
        mealShare: Double = this.mealShare
    ): PlanNutritionAssessment = assess(
        meal.nutrition(foodsById, dishesById, day),
        mealTarget(recommendation, mealShare)
    )

    fun assessDay(
        day: WeekDay,
        meals: List<PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation
    ): PlanNutritionAssessment {
        val dayMeals = meals.filter { day in it.days }
        val actual = dayMeals.fold(NutritionTotals()) { total, meal ->
            total + meal.nutrition(foodsById, dishesById, day)
        }
        val presentTypes = dayMeals.mapTo(mutableSetOf()) { it.type }
        val missing = MealType.entries.filterNot(presentTypes::contains)
        return assess(actual, dailyTarget(recommendation)).copy(missingMealTypes = missing)
    }

    fun assessWeek(
        meals: List<PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation
    ): PlanNutritionAssessment {
        val actual = WeekDay.entries.fold(NutritionTotals()) { total, day ->
            val dayMeals = meals.filter { day in it.days }
            total + dayMeals.fold(NutritionTotals()) { dayTotal, meal ->
                dayTotal + meal.nutrition(foodsById, dishesById, day)
            }
        }
        return assess(actual, dailyTarget(recommendation).scaled(WeekDay.entries.size.toDouble()))
    }

    fun weeklyFoodAmounts(
        meals: List<PlannedMeal>,
        dishesById: Map<Long, Dish>
    ): Map<Long, Double> {
        val totals = mutableMapOf<Long, Double>()
        meals.forEach { meal ->
            meal.days.forEach { day ->
                meal.items.forEach { item ->
                    totals[item.foodId] = totals.getOrDefault(item.foodId, 0.0) +
                        meal.resolvedGrams(item, day)
                }
                meal.dishes.forEach { plannedDish ->
                    dishesById[plannedDish.dishId]?.let { dish ->
                        val recipeWeight = dish.totalWeightGrams()
                        if (recipeWeight > 0.0) dish.ingredients.forEach { ingredient ->
                            totals[ingredient.foodId] = totals.getOrDefault(ingredient.foodId, 0.0) +
                                ingredient.grams * (meal.resolvedGrams(plannedDish, day) / recipeWeight)
                        }
                    }
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
                calories = NutritionTolerancePolicy.evaluate(NutrientKind.CALORIES, actual.calories, target.calories).fit,
                protein = NutritionTolerancePolicy.evaluate(NutrientKind.PROTEIN, actual.proteinGrams, target.proteinGrams).fit,
                carbohydrates = NutritionTolerancePolicy.evaluate(NutrientKind.CARBOHYDRATES, actual.carbohydrateGrams, target.carbohydrateGrams).fit,
                fat = NutritionTolerancePolicy.evaluate(NutrientKind.FAT, actual.fatGrams, target.fatGrams).fit
            )
        )
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

/** Decides whether a complete week is usable. Weekly nutrition is the actual
 * acceptance criterion; daily limits only reject clearly lopsided days. Meal
 * macro distribution is deliberately not part of this gate. */
object WeeklyMenuAcceptancePolicy {
    @Volatile
    private var settings = NutritionToleranceSettings()

    fun configure(value: NutritionToleranceSettings) {
        settings = value.takeIf { it.isValid() } ?: NutritionToleranceSettings()
    }

    fun isDayAcceptable(
        assessment: PlanNutritionAssessment,
        activeMealTypes: Set<MealType> = MealType.entries.toSet()
    ): Boolean {
        if (!assessment.actual.isComplete ||
            activeMealTypes.any { it in assessment.missingMealTypes }
        ) return false

        fun ratio(actual: Double, target: Double) = actual / target.coerceAtLeast(1.0)
        val tolerance = settings
        return ratio(assessment.actual.calories, assessment.target.calories) in
            tolerance.caloriesMinimum..tolerance.caloriesMaximum &&
            ratio(assessment.actual.proteinGrams, assessment.target.proteinGrams) in
                tolerance.proteinMinimum..tolerance.proteinMaximum &&
            ratio(assessment.actual.carbohydrateGrams, assessment.target.carbohydrateGrams) in
                tolerance.carbohydratesMinimum..tolerance.carbohydratesMaximum &&
            ratio(assessment.actual.fatGrams, assessment.target.fatGrams) in
                tolerance.fatMinimum..tolerance.fatMaximum
    }

    fun isAcceptable(
        assessments: List<PlanNutritionAssessment>,
        activeMealTypes: Set<MealType> = MealType.entries.toSet()
    ): Boolean {
        if (assessments.size != WeekDay.entries.size) return false
        if (assessments.any { assessment ->
                !assessment.actual.isComplete ||
                    activeMealTypes.any { it in assessment.missingMealTypes }
            }
        ) return false

        fun averageRatio(
            actual: (PlanNutritionAssessment) -> Double,
            target: (PlanNutritionAssessment) -> Double
        ) = assessments.map { actual(it) }.average() /
            assessments.map { target(it) }.average().coerceAtLeast(1.0)

        val tolerance = settings
        val weeklyAcceptable =
            averageRatio({ it.actual.calories }, { it.target.calories }) in
                tolerance.caloriesMinimum..tolerance.caloriesMaximum &&
            averageRatio({ it.actual.proteinGrams }, { it.target.proteinGrams }) in
                tolerance.proteinMinimum..tolerance.proteinMaximum &&
            averageRatio(
                { it.actual.carbohydrateGrams }, { it.target.carbohydrateGrams }
            ) in tolerance.carbohydratesMinimum..tolerance.carbohydratesMaximum &&
            averageRatio({ it.actual.fatGrams }, { it.target.fatGrams }) in
                tolerance.fatMinimum..tolerance.fatMaximum
        if (!weeklyAcceptable) return false

        fun PlanNutritionAssessment.ratio(actual: Double, target: Double) =
            actual / target.coerceAtLeast(1.0)

        return assessments.all {
            it.ratio(it.actual.calories, it.target.calories) in 0.70..1.30 &&
                it.ratio(it.actual.proteinGrams, it.target.proteinGrams) in 0.60..1.50 &&
                it.ratio(
                    it.actual.carbohydrateGrams, it.target.carbohydrateGrams
                ) in 0.55..1.50 &&
                it.ratio(it.actual.fatGrams, it.target.fatGrams) in 0.50..1.60
        }
    }
}
