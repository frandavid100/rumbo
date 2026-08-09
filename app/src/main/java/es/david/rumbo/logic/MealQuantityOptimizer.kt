package es.david.rumbo.logic

import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealDayAmounts
import es.david.rumbo.model.MealType
import es.david.rumbo.model.NutritionTotals
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import es.david.rumbo.model.nutritionForGrams
import es.david.rumbo.model.resolvedGrams
import es.david.rumbo.model.sanitizedDayAmounts
import kotlin.math.abs
import kotlin.math.round

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
        val perGram: Vector
    )

    fun optimize(
        meals: List<PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        days: Set<WeekDay> = WeekDay.entries.toSet()
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

            repeat(16) {
                variables.forEachIndexed { index, variable ->
                    val withoutCurrent = actual - variable.perGram * amounts[index]
                    var low = variable.minimum
                    var high = variable.maximum
                    repeat(28) {
                        val left = low + (high - low) / 3.0
                        val right = high - (high - low) / 3.0
                        if (score(withoutCurrent + variable.perGram * left, target) <=
                            score(withoutCurrent + variable.perGram * right, target)
                        ) high = right else low = left
                    }
                    val best = ((low + high) / 2.0).coerceIn(variable.minimum, variable.maximum)
                    amounts[index] = best
                    actual = withoutCurrent + variable.perGram * best
                }
            }

            val rounded = amounts.mapIndexed { index, amount ->
                round(amount).coerceIn(variables[index].minimum, variables[index].maximum)
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
                        )
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
                        perGram.toVector()
                    )
                )
            }
        }
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
}
