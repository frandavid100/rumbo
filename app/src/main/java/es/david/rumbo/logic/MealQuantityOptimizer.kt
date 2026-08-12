package es.david.rumbo.logic

import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealDayAmounts
import es.david.rumbo.model.MealType
import es.david.rumbo.model.NutritionTotals
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import es.david.rumbo.model.nutrition
import es.david.rumbo.model.nutritionForGrams
import es.david.rumbo.model.resolvedGrams
import es.david.rumbo.model.sanitizedDayAmounts
import kotlin.math.abs
import kotlin.math.round
import kotlin.math.ceil
import kotlin.math.floor

data class QuantityChange(
    val day: WeekDay,
    val mealId: Long,
    val mealType: MealType,
    val label: String,
    val beforeGrams: Double,
    val afterGrams: Double
)

data class DayOptimizationSummary(
    val day: WeekDay,
    val before: PlanNutritionAssessment,
    val after: PlanNutritionAssessment
)

data class QuantityOptimizationResult(
    val meals: List<PlannedMeal>,
    val changes: List<QuantityChange>,
    val days: List<DayOptimizationSummary>
)

object MealQuantityOptimizer {
    private data class Vector(
        val calories: Double,
        val protein: Double,
        val carbohydrates: Double,
        val fat: Double
    )

    private data class Variable(
        val mealId: Long,
        val mealType: MealType,
        val itemId: Long,
        val isDish: Boolean,
        val label: String,
        val minimum: Double,
        val maximum: Double,
        val initial: Double,
        val perGram: Vector,
        val step: Double? = null
    )

    fun optimize(
        meals: List<PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        days: Set<WeekDay> = WeekDay.entries.toSet(),
        mealShares: Map<MealType, Double> = defaultMealShares
    ): QuantityOptimizationResult {
        var optimizedMeals = meals
        val changes = mutableListOf<QuantityChange>()
        val summaries = mutableListOf<DayOptimizationSummary>()

        WeekDay.entries.filter(days::contains).forEach { day ->
            val before = MealPlanEvaluator.assessDay(
                day, optimizedMeals, foodsById, dishesById, recommendation
            )
            val variables = variablesFor(day, optimizedMeals, foodsById, dishesById)
            if (before.missingMealTypes.isNotEmpty() || !before.actual.isComplete || variables.isEmpty()) {
                return@forEach
            }

            val target = before.target
            val amounts = variables.map { it.initial }.toMutableList()
            var actual = before.actual.toVector()
            val mealActual = optimizedMeals
                .filter { day in it.days }
                .associate { meal ->
                    meal.id to meal.nutrition(foodsById, dishesById, day).toVector()
                }.toMutableMap()

            repeat(16) {
                variables.forEachIndexed { index, variable ->
                    val withoutCurrent = actual - variable.perGram * amounts[index]
                    val currentMeal = mealActual.getValue(variable.mealId)
                    val mealWithoutCurrent = currentMeal - variable.perGram * amounts[index]
                    val mealTarget = MealPlanEvaluator.mealTarget(
                        recommendation,
                        mealShares[variable.mealType]
                            ?: defaultMealShares.getValue(variable.mealType)
                    )
                    fun combinedScore(amount: Double): Double =
                        score(withoutCurrent + variable.perGram * amount, target) +
                            score(mealWithoutCurrent + variable.perGram * amount, mealTarget) * 2.0

                    var low = variable.minimum
                    var high = variable.maximum
                    repeat(28) {
                        val left = low + (high - low) / 3.0
                        val right = high - (high - low) / 3.0
                        if (combinedScore(left) <= combinedScore(right)) high = right else low = left
                    }
                    val continuousBest = ((low + high) / 2.0).coerceIn(variable.minimum, variable.maximum)
                    val best = variable.step?.let { step ->
                        val first = ceil(variable.minimum / step).toLong()
                        val last = floor(variable.maximum / step).toLong()
                        if (first > last) continuousBest else {
                            val center = round(continuousBest / step).toLong().coerceIn(first, last)
                            ((center - 2)..(center + 2)).filter { it in first..last }
                                .minByOrNull { combinedScore(it * step) }!! * step
                        }
                    } ?: continuousBest
                    amounts[index] = best
                    actual = withoutCurrent + variable.perGram * best
                    mealActual[variable.mealId] = mealWithoutCurrent + variable.perGram * best
                }
            }

            val rounded = amounts.mapIndexed { index, amount ->
                variables[index].step?.let { step -> round(amount / step) * step }
                    ?: round(amount)
            }.mapIndexed { index, amount ->
                amount.coerceIn(variables[index].minimum, variables[index].maximum)
            }
            optimizedMeals = applyDayAmounts(optimizedMeals, day, variables, rounded)
            val after = MealPlanEvaluator.assessDay(
                day, optimizedMeals, foodsById, dishesById, recommendation
            )
            summaries += DayOptimizationSummary(day, before, after)
            variables.forEachIndexed { index, variable ->
                if (abs(variable.initial - rounded[index]) >= 0.5) {
                    changes += QuantityChange(
                        day = day,
                        mealId = variable.mealId,
                        mealType = variable.mealType,
                        label = variable.label,
                        beforeGrams = variable.initial,
                        afterGrams = rounded[index]
                    )
                }
            }
        }
        return QuantityOptimizationResult(optimizedMeals, changes, summaries)
    }

    private fun variablesFor(
        day: WeekDay,
        meals: List<PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): List<Variable> = buildList {
        meals.filter { day in it.days }.forEach { meal ->
            meal.items.filter { it.adjustable }.forEach { item ->
                val food = foodsById[item.foodId]
                if (food?.hasComparableNutrition() == true) add(
                    Variable(
                        meal.id, meal.type, item.foodId, false, food.name,
                        item.minimumGrams, item.maximumGrams, meal.resolvedGrams(item, day),
                        Vector(
                            food.calories!! / 100.0,
                            food.proteinGrams!! / 100.0,
                            food.carbohydrateGrams!! / 100.0,
                            food.fatGrams!! / 100.0
                        ),
                        step = food.unitAmount.takeIf { food.wholeUnitsOnly }
                    )
                )
            }
            meal.dishes.filter { it.adjustable }.forEach { item ->
                val dish = dishesById[item.dishId]
                val perGram = dish?.nutritionForGrams(foodsById, 1.0)
                if (dish != null && perGram?.isComplete == true) add(
                    Variable(
                        meal.id, meal.type, item.dishId, true, dish.name,
                        item.minimumGrams, item.maximumGrams, meal.resolvedGrams(item, day),
                        perGram.toVector(),
                        step = dish.wholeUnitStep(foodsById)
                    )
                )
            }
        }
    }

    private fun Dish.wholeUnitStep(foodsById: Map<Long, Food>): Double? {
        val total = totalWeightGrams()
        if (total <= 0.0) return null
        val steps = ingredients.mapNotNull { ingredient ->
            val food = foodsById[ingredient.foodId]
            val unit = food?.unitAmount
            if (food?.wholeUnitsOnly == true && unit != null) unit * total / ingredient.grams else null
        }
        if (steps.isEmpty()) return null
        // Recipes keep fixed proportions. Find the smallest 0.1 g dish increment
        // that makes every indivisible ingredient an integer number of units.
        val tenths = steps.map { round(it * 10.0).toLong().coerceAtLeast(1L) }
        fun gcd(a0: Long, b0: Long): Long {
            var a = a0; var b = b0
            while (b != 0L) { val r = a % b; a = b; b = r }
            return a
        }
        fun lcm(a: Long, b: Long): Long = (a / gcd(a, b) * b).coerceAtMost(50_000L)
        return tenths.reduce(::lcm) / 10.0
    }

    private fun applyDayAmounts(
        meals: List<PlannedMeal>,
        day: WeekDay,
        variables: List<Variable>,
        amounts: List<Double>
    ): List<PlannedMeal> {
        val byMeal = variables.indices.groupBy { variables[it].mealId }
        return meals.map { meal ->
            val indices = byMeal[meal.id] ?: return@map meal
            val existing = meal.dayAmounts.firstOrNull { it.day == day }
            val foodAmounts = existing?.foodGrams.orEmpty().toMutableMap()
            val dishAmounts = existing?.dishGrams.orEmpty().toMutableMap()
            indices.forEach { index ->
                val variable = variables[index]
                val amount = amounts[index]
                if (variable.isDish) dishAmounts[variable.itemId] = amount
                else foodAmounts[variable.itemId] = amount
            }
            meal.copy(
                dayAmounts = meal.dayAmounts.filterNot { it.day == day } +
                    MealDayAmounts(day, foodAmounts, dishAmounts)
            ).sanitizedDayAmounts()
        }
    }

    private fun score(actual: Vector, target: NutritionTarget): Double {
        fun relative(actualValue: Double, targetValue: Double): Double =
            if (targetValue <= 0.0) 0.0 else (actualValue - targetValue) / targetValue

        val calories = relative(actual.calories, target.calories)
        val protein = relative(actual.protein, target.proteinGrams)
        val carbohydrates = relative(actual.carbohydrates, target.carbohydrateGrams)
        val fatRatio = if (target.fatGrams <= 0.0) 1.0 else actual.fat / target.fatGrams
        val fatOutsideBand = when {
            fatRatio < 0.90 -> fatRatio - 0.90
            fatRatio > 1.10 -> fatRatio - 1.10
            else -> 0.0
        }
        return 5.0 * calories * calories +
            (if (protein < 0.0) 5.0 else 2.0) * protein * protein +
            carbohydrates * carbohydrates +
            2.0 * fatOutsideBand * fatOutsideBand
    }

    private fun NutritionTotals.toVector() = Vector(
        calories, proteinGrams, carbohydrateGrams, fatGrams
    )

    private operator fun Vector.plus(other: Vector) = Vector(
        calories + other.calories,
        protein + other.protein,
        carbohydrates + other.carbohydrates,
        fat + other.fat
    )

    private operator fun Vector.minus(other: Vector) = Vector(
        calories - other.calories,
        protein - other.protein,
        carbohydrates - other.carbohydrates,
        fat - other.fat
    )

    private operator fun Vector.times(factor: Double) = Vector(
        calories * factor,
        protein * factor,
        carbohydrates * factor,
        fat * factor
    )
    private val defaultMealShares = mapOf(
        MealType.BREAKFAST to 0.25,
        MealType.MORNING_SNACK to 0.10,
        MealType.LUNCH to 0.35,
        MealType.AFTERNOON_SNACK to 0.10,
        MealType.DINNER to 0.20
    )

}
