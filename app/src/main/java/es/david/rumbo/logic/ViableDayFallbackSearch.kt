package es.david.rumbo.logic

import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import java.util.PriorityQueue
import kotlin.math.pow

/**
 * Deterministic fallback for level 1.
 *
 * The normal generator is intentionally opinionated about the shape of each
 * meal. That is useful for good menus, but it is incomplete as a feasibility
 * proof: a valid day may need a very small snack and a much larger dinner. This
 * search enumerates one- and two-food culinary-valid meal compositions, prunes
 * combinations whose macro ranges cannot reach the daily target, and lets the
 * canonical quantity optimiser evaluate only the most promising complete days.
 */
object ViableDayFallbackSearch {
    private const val MAX_RANKED_COMPOSITIONS = 800

    private data class Vector(
        val calories: Double,
        val protein: Double,
        val carbohydrates: Double,
        val fat: Double
    ) {
        operator fun plus(other: Vector) = Vector(
            calories + other.calories,
            protein + other.protein,
            carbohydrates + other.carbohydrates,
            fat + other.fat
        )
    }

    private data class MealOption(
        val type: MealType,
        val rules: List<PlanningRule>,
        val minimum: Vector,
        val maximum: Vector,
        val middle: Vector
    )

    private data class RankedComposition(
        val options: List<MealOption>,
        val score: Double
    )

    fun find(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): MenuWitness? {
        val active = rules.asSequence()
            .filter {
                it.itemKind == PlannedItemKind.FOOD && it.isActive &&
                    it.frequency != PlanningFrequency.NEVER &&
                    foodsById[it.itemId]?.hasComparableNutrition() == true
            }
            .map { rule -> CulinaryPolicy.applyPortion(rule, foodsById.getValue(rule.itemId)) }
            .toList()
        val mealTypes = MealType.entries.filter {
            (mealShares[it] ?: 0.0) > 0.0
        }
        if (mealTypes.isEmpty()) return null

        val optionsByMeal = mealTypes.associateWith { mealType ->
            val eligible = active.filter { mealType in it.allowedMealTypes }
            buildList {
                eligible.forEach { add(listOf(it)) }
                eligible.indices.forEach { first ->
                    for (second in first + 1 until eligible.size) {
                        add(listOf(eligible[first], eligible[second]))
                    }
                }
            }.filter { option ->
                CulinaryPolicy.hasValidRoleAssignment(option.map { rule ->
                    CulinaryPolicy.roles(foodsById.getValue(rule.itemId))
                })
            }.map { option -> option.toOption(mealType, foodsById) }
        }
        if (optionsByMeal.values.any { it.isEmpty() }) return null

        val target = Vector(
            recommendation.calories.toDouble(),
            recommendation.proteinGrams.toDouble(),
            recommendation.carbohydrateGrams.toDouble(),
            recommendation.fatGrams.toDouble()
        )
        val lower = Vector(
            target.calories * .90, target.protein * .90,
            target.carbohydrates * .85, target.fat * .85
        )
        val upper = Vector(
            target.calories * 1.10, target.protein * 1.15,
            target.carbohydrates * 1.15, target.fat * 1.15
        )
        val remainingMaximum = Array(mealTypes.size + 1) { Vector(0.0, 0.0, 0.0, 0.0) }
        for (index in mealTypes.lastIndex downTo 0) {
            val maxima = optionsByMeal.getValue(mealTypes[index])
            remainingMaximum[index] = remainingMaximum[index + 1] + Vector(
                maxima.maxOf { it.maximum.calories },
                maxima.maxOf { it.maximum.protein },
                maxima.maxOf { it.maximum.carbohydrates },
                maxima.maxOf { it.maximum.fat }
            )
        }

        val ranked = PriorityQueue<RankedComposition>(compareByDescending { it.score })
        fun visit(
            index: Int,
            chosen: MutableList<MealOption>,
            minimum: Vector,
            maximum: Vector,
            middle: Vector
        ) {
            if (minimum.exceeds(upper)) return
            if (!(maximum + remainingMaximum[index]).canReach(lower)) return
            if (index == mealTypes.size) {
                if (!maximum.canReach(lower)) return
                val candidate = RankedComposition(chosen.toList(), middle.distance(target))
                ranked += candidate
                if (ranked.size > MAX_RANKED_COMPOSITIONS) ranked.poll()
                return
            }
            optionsByMeal.getValue(mealTypes[index]).forEach { option ->
                chosen += option
                visit(
                    index + 1, chosen,
                    minimum + option.minimum,
                    maximum + option.maximum,
                    middle + option.middle
                )
                chosen.removeAt(chosen.lastIndex)
            }
        }
        visit(
            0, mutableListOf(),
            Vector(0.0, 0.0, 0.0, 0.0),
            Vector(0.0, 0.0, 0.0, 0.0),
            Vector(0.0, 0.0, 0.0, 0.0)
        )

        return ranked.toList().sortedBy { it.score }.firstNotNullOfOrNull { composition ->
            val meals = composition.options.mapIndexed { index, option ->
                PlannedMeal(
                    id = 900_000L + index,
                    type = option.type,
                    days = setOf(WeekDay.MONDAY),
                    items = option.rules.map { rule ->
                        PlannedFood(
                            foodId = rule.itemId,
                            grams = rule.preferredGrams,
                            adjustable = true,
                            minimumGrams = rule.preferredGrams * rule.minimumFactor,
                            maximumGrams = rule.preferredGrams * rule.maximumFactor
                        )
                    }
                )
            }
            val optimized = MealQuantityOptimizer.optimize(
                meals, foodsById, dishesById, recommendation,
                days = setOf(WeekDay.MONDAY), mealShares = mealShares
            ).meals
            val assessment = MealPlanEvaluator.assessDay(
                WeekDay.MONDAY, optimized, foodsById, dishesById, recommendation
            )
            if (
                WeeklyMenuAcceptancePolicy.isDayAcceptable(assessment, mealTypes.toSet()) &&
                WeeklyMenuGenerator.isCulinarilyValid(optimized, foodsById, dishesById)
            ) MenuWitness(9_000_001L, optimized) else null
        }
    }

    private fun List<PlanningRule>.toOption(
        type: MealType,
        foodsById: Map<Long, Food>
    ): MealOption {
        fun totals(amount: (PlanningRule) -> Double) = fold(
            Vector(0.0, 0.0, 0.0, 0.0)
        ) { sum, rule ->
            val food = foodsById.getValue(rule.itemId)
            val factor = amount(rule) / 100.0
            sum + Vector(
                food.calories!! * factor,
                food.proteinGrams!! * factor,
                food.carbohydrateGrams!! * factor,
                food.fatGrams!! * factor
            )
        }
        val minimum = totals { it.preferredGrams * it.minimumFactor }
        val maximum = totals { it.preferredGrams * it.maximumFactor }
        return MealOption(
            type, this, minimum, maximum,
            totals { (it.preferredGrams * (it.minimumFactor + it.maximumFactor) / 2.0) }
        )
    }

    private fun Vector.exceeds(limit: Vector) =
        calories > limit.calories || protein > limit.protein ||
            carbohydrates > limit.carbohydrates || fat > limit.fat

    private fun Vector.canReach(limit: Vector) =
        calories >= limit.calories && protein >= limit.protein &&
            carbohydrates >= limit.carbohydrates && fat >= limit.fat

    private fun Vector.distance(target: Vector): Double =
        ((calories - target.calories) / target.calories).pow(2) * 1.25 +
            ((protein - target.protein) / target.protein).pow(2) * 1.15 +
            ((carbohydrates - target.carbohydrates) / target.carbohydrates).pow(2) +
            ((fat - target.fat) / target.fat).pow(2)
}
