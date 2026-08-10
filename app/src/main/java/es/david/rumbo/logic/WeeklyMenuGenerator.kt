package es.david.rumbo.logic

import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.MenuHistoryEntry
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedDish
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.PlanningSlot
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import es.david.rumbo.model.nutrition
import es.david.rumbo.model.resolvedGrams
import java.util.Random
import kotlin.math.abs
import kotlin.math.pow

data class GeneratedWeeklyMenu(
    val meals: List<PlannedMeal>,
    val history: List<MenuHistoryEntry>,
    val generation: Int
)

class PlanningConflictException(message: String) : IllegalArgumentException(message)

object WeeklyMenuGenerator {
    private const val CANDIDATE_WEEKS = 80
    private const val HISTORY_GENERATIONS = 8

    fun generate(
        currentMeals: List<PlannedMeal>,
        rules: List<PlanningRule>,
        history: List<MenuHistoryEntry>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        seed: Long = System.currentTimeMillis()
    ): GeneratedWeeklyMenu {
        require(rules.isNotEmpty()) { "Añade al menos un alimento o plato al menú." }
        require(rules.all { it.isValid() }) { "Hay reglas de planificación incompletas." }
        require(rules.all { rule ->
            when (rule.itemKind) {
                PlannedItemKind.FOOD -> foodsById[rule.itemId]?.hasComparableNutrition() == true
                PlannedItemKind.DISH -> dishesById[rule.itemId]?.nutrition(foodsById)?.isComplete == true
            }
        }) { "Todos los elementos seleccionados necesitan datos nutricionales completos." }

        val fixedBySlot = rules
            .flatMap { rule -> rule.fixedSlots.map { it to rule } }
            .groupBy({ it.first }, { it.second })
            .mapValues { (_, values) -> values.distinctBy { it.itemKind to it.itemId } }

        val generatedTypes = MealType.entries.filter { type ->
            rules.any { type in it.allowedMealTypes && it.frequency != PlanningFrequency.NEVER } ||
                fixedBySlot.keys.any { it.mealType == type }
        }.toSet()
        require(generatedTypes.isNotEmpty()) { "Indica al menos una comida en las reglas del menú." }

        val slots = WeekDay.entries.flatMap { day ->
            generatedTypes.map { type -> PlanningSlot(day, type) }
        }
        slots.forEach { slot ->
            if (fixedBySlot[slot].isNullOrEmpty() && rules.none {
                    slot.mealType in it.allowedMealTypes && it.frequency != PlanningFrequency.NEVER
                }) {
                throw PlanningConflictException(
                    "No hay candidatos para ${slot.day.label.lowercase()} · ${slot.mealType.label.lowercase()}."
                )
            }
        }

        val generation = (history.maxOfOrNull { it.generation } ?: 0) + 1
        val recent = history.filter { it.generation >= generation - HISTORY_GENERATIONS }
        val preserved = currentMeals.filterNot { it.type in generatedTypes }
        var bestMeals: List<PlannedMeal>? = null
        var bestAssignments: Map<PlanningSlot, List<PlanningRule>>? = null
        var bestScore = Double.POSITIVE_INFINITY

        repeat(CANDIDATE_WEEKS) { candidateIndex ->
            val random = Random(seed + candidateIndex * 104729L)
            val assignments = linkedMapOf<PlanningSlot, List<PlanningRule>>()
            slots.forEach { slot ->
                val fixed = fixedBySlot[slot].orEmpty()
                val additions = when {
                    fixed.any { it.itemKind == PlannedItemKind.DISH } -> emptyList()
                    fixed.isNotEmpty() -> {
                        val dishCandidates = rules.filter { candidate ->
                            candidate.itemKind == PlannedItemKind.DISH &&
                                slot.mealType in candidate.allowedMealTypes &&
                                candidate.frequency != PlanningFrequency.NEVER &&
                                fixed.none { fixedRule -> fixedRule.sameItem(candidate) }
                        }
                        if (dishCandidates.isEmpty()) emptyList()
                        else listOf(chooseRule(slot, dishCandidates, assignments, recent, random))
                    }
                    else -> listOf(chooseRule(slot, rules, assignments, recent, random))
                }
                assignments[slot] = (fixed + additions).distinctBy { it.itemKind to it.itemId }
            }
            val generated = assignments.map { (slot, assignedRules) ->
                assignedRules.toMeal(slot, generation)
            }
            val optimized = MealQuantityOptimizer.optimize(
                preserved + generated, foodsById, dishesById, recommendation
            ).meals
            val score = score(
                optimized, assignments, recent, foodsById, dishesById, recommendation
            )
            if (score < bestScore) {
                bestScore = score
                bestMeals = optimized
                bestAssignments = assignments
            }
        }

        val assignments = checkNotNull(bestAssignments)
        val entriesPerGeneration = assignments.values.sumOf { it.size }.coerceAtLeast(1)
        val newHistory = (recent + assignments.flatMap { (slot, assignedRules) ->
            assignedRules.map { rule ->
                MenuHistoryEntry(
                    generation = generation,
                    itemKind = rule.itemKind,
                    itemId = rule.itemId,
                    day = slot.day,
                    mealType = slot.mealType
                )
            }
        }).takeLast(HISTORY_GENERATIONS * entriesPerGeneration)

        return GeneratedWeeklyMenu(
            meals = checkNotNull(bestMeals),
            history = newHistory,
            generation = generation
        )
    }

    private fun chooseRule(
        slot: PlanningSlot,
        rules: List<PlanningRule>,
        assigned: Map<PlanningSlot, List<PlanningRule>>,
        history: List<MenuHistoryEntry>,
        random: Random
    ): PlanningRule {
        val candidates = rules.filter {
            slot.mealType in it.allowedMealTypes && it.frequency != PlanningFrequency.NEVER
        }
        if (candidates.isEmpty()) {
            throw PlanningConflictException(
                "No hay candidatos para ${slot.day.label.lowercase()} · ${slot.mealType.label.lowercase()}."
            )
        }
        val weighted = candidates.map { rule ->
            val weeklyCount = assigned.values.flatten().count { it.sameItem(rule) }
            val previousDayRules = if (slot.day.ordinal > 0) {
                assigned[PlanningSlot(WeekDay.entries[slot.day.ordinal - 1], slot.mealType)].orEmpty()
            } else emptyList()
            val recentCount = history.count {
                it.itemKind == rule.itemKind && it.itemId == rule.itemId
            }
            val repetitionPenalty = 1.0 + weeklyCount * weeklyCount * 1.7 + recentCount * 0.35
            val adjacentPenalty = if (previousDayRules.any { it.sameItem(rule) }) 8.0 else 1.0
            rule to (rule.frequency.weight / repetitionPenalty / adjacentPenalty)
        }
        val total = weighted.sumOf { it.second }
        var draw = random.nextDouble() * total
        weighted.forEach { (rule, weight) ->
            draw -= weight
            if (draw <= 0.0) return rule
        }
        return weighted.last().first
    }

    private fun score(
        meals: List<PlannedMeal>,
        assignments: Map<PlanningSlot, List<PlanningRule>>,
        history: List<MenuHistoryEntry>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation
    ): Double {
        val daily = WeekDay.entries.map {
            MealPlanEvaluator.assessDay(it, meals, foodsById, dishesById, recommendation)
        }
        val nutritional = daily.sumOf { assessment ->
            relativeError(assessment.actual.calories, assessment.target.calories).pow(2) * 5.0 +
                relativeError(assessment.actual.proteinGrams, assessment.target.proteinGrams).pow(2) * 4.0 +
                relativeError(assessment.actual.carbohydrateGrams, assessment.target.carbohydrateGrams).pow(2) * 1.5 +
                relativeError(assessment.actual.fatGrams, assessment.target.fatGrams).pow(2) * 1.5
        }
        val quantityPenalty = assignments.entries.sumOf { (slot, assignedRules) ->
            val meal = meals.first { it.type == slot.mealType && slot.day in it.days }
            assignedRules.sumOf { rule ->
                val grams = when (rule.itemKind) {
                    PlannedItemKind.FOOD -> meal.items.first { it.foodId == rule.itemId }
                        .let { meal.resolvedGrams(it, slot.day) }
                    PlannedItemKind.DISH -> meal.dishes.first { it.dishId == rule.itemId }
                        .let { meal.resolvedGrams(it, slot.day) }
                }
                val factor = grams / rule.preferredGrams
                val halfRange = ((rule.maximumFactor - rule.minimumFactor) / 2.0).coerceAtLeast(0.1)
                (abs(factor - 1.0) / halfRange).pow(2)
            }
        }
        val allRules = assignments.values.flatten()
        val counts = allRules.groupingBy { it.itemKind to it.itemId }.eachCount()
        val varietyPenalty = counts.values.sumOf { count ->
            (count - 2).coerceAtLeast(0).toDouble().pow(2) * 1.5
        }
        val recentPenalty = allRules.sumOf { rule ->
            history.count { it.itemKind == rule.itemKind && it.itemId == rule.itemId } * 0.15
        }
        return nutritional + quantityPenalty + varietyPenalty + recentPenalty
    }

    private fun List<PlanningRule>.toMeal(slot: PlanningSlot, generation: Int): PlannedMeal {
        val id = generation.toLong() * 1000L + slot.day.ordinal * 10L + slot.mealType.ordinal + 1L
        return PlannedMeal(
            id = id,
            type = slot.mealType,
            days = setOf(slot.day),
            items = filter { it.itemKind == PlannedItemKind.FOOD }.map { rule ->
                PlannedFood(
                    rule.itemId,
                    rule.preferredGrams,
                    true,
                    rule.preferredGrams * rule.minimumFactor,
                    rule.preferredGrams * rule.maximumFactor
                )
            },
            dishes = filter { it.itemKind == PlannedItemKind.DISH }.map { rule ->
                PlannedDish(
                    rule.itemId,
                    rule.preferredGrams,
                    true,
                    rule.preferredGrams * rule.minimumFactor,
                    rule.preferredGrams * rule.maximumFactor
                )
            }
        )
    }

    private fun PlanningRule.sameItem(other: PlanningRule): Boolean =
        itemKind == other.itemKind && itemId == other.itemId

    private fun relativeError(actual: Double, target: Double): Double =
        if (target <= 0.0) 0.0 else abs(actual - target) / target
}
