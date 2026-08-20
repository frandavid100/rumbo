package es.david.rumbo.logic

import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealDayAmounts
import es.david.rumbo.model.MealType
import es.david.rumbo.model.MealDistributionPolicy
import es.david.rumbo.model.NutritionTotals
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import es.david.rumbo.model.nutrition
import es.david.rumbo.model.nutritionForGrams
import es.david.rumbo.model.resolvedGrams
import es.david.rumbo.model.sanitizedDayAmounts
import es.david.rumbo.model.totalWeightGrams
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
        val allowedAmounts: List<Double>
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
                            mealPreferenceScore(
                                mealWithoutCurrent + variable.perGram * amount,
                                mealTarget
                            ) +
                            portionConsistencyScore(amount, variable) +
                            mealPortionLoadScore(index, amount, variables, amounts)

                    var low = variable.minimum
                    var high = variable.maximum
                    repeat(28) {
                        val left = low + (high - low) / 3.0
                        val right = high - (high - low) / 3.0
                        if (combinedScore(left) <= combinedScore(right)) high = right else low = left
                    }
                    val continuousBest = ((low + high) / 2.0).coerceIn(variable.minimum, variable.maximum)
                    val nearestIndex = variable.allowedAmounts.binarySearch(continuousBest).let {
                        if (it >= 0) it else (-it - 1).coerceIn(variable.allowedAmounts.indices)
                    }
                    val best = ((nearestIndex - 2)..(nearestIndex + 2))
                        .filter { it in variable.allowedAmounts.indices }
                        .map(variable.allowedAmounts::get)
                        .minByOrNull(::combinedScore)!!
                    amounts[index] = best
                    actual = withoutCurrent + variable.perGram * best
                    mealActual[variable.mealId] = mealWithoutCurrent + variable.perGram * best
                }
            }

            val rounded = amounts.mapIndexed { index, amount ->
                variables[index].allowedAmounts.minByOrNull { abs(it - amount) }!!
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
                if (food?.hasComparableNutrition() == true) {
                    val step = food.practicalUnitStep()
                    val allowedAmounts = allowedAmounts(
                        item.minimumGrams, item.maximumGrams,
                        meal.resolvedGrams(item, day), step
                    )
                    add(
                        Variable(
                            meal.id, meal.type, item.foodId, false, food.name,
                            allowedAmounts.first(), allowedAmounts.last(), meal.resolvedGrams(item, day),
                            Vector(
                                food.calories!! / 100.0,
                                food.proteinGrams!! / 100.0,
                                food.carbohydrateGrams!! / 100.0,
                                food.fatGrams!! / 100.0
                            ),
                            allowedAmounts = allowedAmounts
                        )
                    )
                }
            }
            meal.dishes.filter { it.adjustable }.forEach { item ->
                val dish = dishesById[item.dishId]
                val perGram = dish?.nutritionForGrams(foodsById, 1.0)
                if (dish != null && perGram?.isComplete == true) {
                    val step = dish.practicalUnitStep() ?: dish.wholeUnitStep(foodsById)
                    val allowedAmounts = allowedAmounts(
                        item.minimumGrams, item.maximumGrams,
                        meal.resolvedGrams(item, day), step
                    )
                    add(
                        Variable(
                            meal.id, meal.type, item.dishId, true, dish.name,
                            allowedAmounts.first(), allowedAmounts.last(), meal.resolvedGrams(item, day),
                            perGram.toVector(),
                            allowedAmounts = allowedAmounts
                        )
                    )
                }
            }
        }
    }

    private fun allowedAmounts(
        minimum: Double,
        maximum: Double,
        initial: Double,
        step: Double?
    ): List<Double> {
        val candidates = if (step != null) {
            val first = ceil(minimum / step).toLong().coerceAtLeast(1L)
            val last = floor(maximum / step).toLong()
            if (first <= last) (first..last).map { it * step } else emptyList()
        } else {
            buildList {
                (1..9).forEach { add(it.toDouble()) }
                (10..100 step 5).forEach { add(it.toDouble()) }
                (110..5000 step 10).forEach { add(it.toDouble()) }
            }.filter { it in minimum..maximum }
        }
        if (candidates.isNotEmpty()) return candidates

        // Practical units and comfortable gram steps take precedence over
        // stale planning bounds that contain no usable amount.
        val nearest = if (step != null) {
            round(initial / step).toLong().coerceAtLeast(1L) * step
        } else practicalGramAmount(initial)
        return listOf(nearest.coerceIn(0.1, 5000.0))
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
        return tenths.reduce { accumulated, value -> lcm(accumulated, value) } / 10.0
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
            val foodRanges = indices.mapNotNull { index ->
                variables[index].takeUnless { it.isDish }?.let {
                    it.itemId to (it.minimum to it.maximum)
                }
            }.toMap()
            val dishRanges = indices.mapNotNull { index ->
                variables[index].takeIf { it.isDish }?.let {
                    it.itemId to (it.minimum to it.maximum)
                }
            }.toMap()
            meal.copy(
                items = meal.items.map { item ->
                    foodRanges[item.foodId]?.let { (minimum, maximum) ->
                        item.copy(minimumGrams = minimum, maximumGrams = maximum)
                    } ?: item
                },
                dishes = meal.dishes.map { item ->
                    dishRanges[item.dishId]?.let { (minimum, maximum) ->
                        item.copy(minimumGrams = minimum, maximumGrams = maximum)
                    } ?: item
                },
                dayAmounts = meal.dayAmounts.filterNot { it.day == day } +
                    MealDayAmounts(day, foodAmounts, dishAmounts)
            ).sanitizedDayAmounts()
        }
    }

    private fun score(actual: Vector, target: NutritionTarget): Double {
        val penalties = listOf(
            NutritionTolerancePolicy.optimizationPenalty(
                NutrientKind.CALORIES, actual.calories, target.calories
            ),
            NutritionTolerancePolicy.optimizationPenalty(
                NutrientKind.PROTEIN, actual.protein, target.proteinGrams
            ),
            NutritionTolerancePolicy.optimizationPenalty(
                NutrientKind.CARBOHYDRATES, actual.carbohydrates, target.carbohydrateGrams
            ),
            NutritionTolerancePolicy.optimizationPenalty(
                NutrientKind.FAT, actual.fat, target.fatGrams
            )
        )
        val weightedTotal = penalties[0] * 1.25 + penalties[1] * 1.15 + penalties[2] + penalties[3]
        return penalties.maxOrNull()!! * 1_000.0 + weightedTotal
    }

    private fun mealPreferenceScore(actual: Vector, target: NutritionTarget): Double {
        fun squaredRatio(value: Double, expected: Double): Double {
            if (expected <= 0.0) return 0.0
            val difference = (value - expected) / expected
            return difference * difference
        }
        val proteinDeficit = if (actual.protein < target.proteinGrams) {
            squaredRatio(actual.protein, target.proteinGrams)
        } else 0.0
        return squaredRatio(actual.calories, target.calories) * 2.0 +
            proteinDeficit * 0.35
    }

    /** Soft regularisation only: nutrition may override it whenever needed. */
    private fun portionConsistencyScore(amount: Double, variable: Variable): Double {
        val usefulRange = (variable.maximum - variable.minimum).coerceAtLeast(1.0)
        val deviation = (amount - variable.initial) / usefulRange
        return deviation * deviation * 0.60
    }

    /** Uses portions relative to their habitual amount instead of raw grams,
     * so water-rich foods are not treated as a disproportionately large meal. */
    private fun mealPortionLoadScore(
        candidateIndex: Int,
        candidateAmount: Double,
        variables: List<Variable>,
        amounts: List<Double>
    ): Double {
        val mealId = variables[candidateIndex].mealId
        val indices = variables.indices.filter { variables[it].mealId == mealId }
        if (indices.isEmpty()) return 0.0
        val averageLoad = indices.map { index ->
            val amount = if (index == candidateIndex) candidateAmount else amounts[index]
            amount / variables[index].initial.coerceAtLeast(1.0)
        }.average()
        return (averageLoad - 1.0).let { it * it } * 0.35
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
    private val defaultMealShares = MealDistributionPolicy.defaults

}
