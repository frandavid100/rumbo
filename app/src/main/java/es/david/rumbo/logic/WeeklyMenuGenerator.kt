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
import es.david.rumbo.model.nutritionForGrams
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
    private const val CANDIDATE_WEEKS = 24
    private const val HISTORY_GENERATIONS = 8

    fun generate(
        currentMeals: List<PlannedMeal>,
        rules: List<PlanningRule>,
        history: List<MenuHistoryEntry>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double> = defaultMealShares,
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
                assignments[slot] = completeSlot(
                    slot = slot,
                    fixed = fixedBySlot[slot].orEmpty(),
                    rules = rules,
                    assigned = assignments,
                    history = recent,
                    random = random,
                    foodsById = foodsById,
                    dishesById = dishesById,
                    recommendation = recommendation,
                    mealShare = mealShares[slot.mealType] ?: defaultMealShares.getValue(slot.mealType)
                )
            }
            val generated = assignments.map { (slot, assignedRules) ->
                assignedRules.toMeal(slot, generation)
            }
            val optimized = MealQuantityOptimizer.optimize(
                preserved + generated, foodsById, dishesById, recommendation,
                mealShares = mealShares
            ).meals
            if (!isFeasible(optimized, foodsById, dishesById, recommendation)) {
                return@repeat
            }
            val score = score(
                optimized, assignments, recent, foodsById, dishesById, recommendation,
                mealShares
            )
            if (score < bestScore) {
                bestScore = score
                bestMeals = optimized
                bestAssignments = assignments
            }
        }

        val assignments = bestAssignments ?: throw PlanningConflictException(
            "Las cantidades fijas y los mínimos configurados no permiten generar un menú seguro. " +
                "Reduce alguna cantidad fija o amplía el margen de ajuste."
        )
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

    private data class MealVector(
        val calories: Double,
        val protein: Double,
        val carbohydrates: Double,
        val fat: Double
    ) {
        operator fun plus(other: MealVector) = MealVector(
            calories + other.calories,
            protein + other.protein,
            carbohydrates + other.carbohydrates,
            fat + other.fat
        )
    }

    private fun completeSlot(
        slot: PlanningSlot,
        fixed: List<PlanningRule>,
        rules: List<PlanningRule>,
        assigned: Map<PlanningSlot, List<PlanningRule>>,
        history: List<MenuHistoryEntry>,
        random: Random,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShare: Double
    ): List<PlanningRule> {
        val chosen = fixed.distinctBy { it.itemKind to it.itemId }.toMutableList()
        val eligible = rules.filter {
            slot.mealType in it.allowedMealTypes &&
                it.frequency != PlanningFrequency.NEVER
        }
        val maximumItems = when (slot.mealType) {
            MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK -> 3
            else -> 4
        }

        while (chosen.size < maximumItems) {
            var candidates = eligible.filter { candidate ->
                chosen.none { it.sameItem(candidate) } &&
                    !(candidate.itemKind == PlannedItemKind.DISH &&
                        chosen.any { it.itemKind == PlannedItemKind.DISH })
            }
            if (candidates.isEmpty()) break
            if (chosen.isEmpty() && candidates.any { it.itemKind == PlannedItemKind.DISH }) {
                candidates = candidates.filter { it.itemKind == PlannedItemKind.DISH }
            }

            // Evaluate every adjustable item at its minimum. If even its
            // minimum makes the meal worse, it must not be added merely to
            // increase variety.
            val before = combinationError(
                chosen, slot, foodsById, dishesById, recommendation, mealShare
            )
            val viable = candidates.mapNotNull { candidate ->
                val after = combinationError(
                    chosen + candidate, slot, foodsById, dishesById, recommendation, mealShare
                )
                val nutritionalImprovement = before - after
                val minimumCalories = (chosen + candidate).sumOf {
                    it.vector(slot, foodsById, dishesById).calories
                }
                val calorieCeiling = recommendation.calories * mealShare * 1.10
                if (chosen.isNotEmpty() &&
                    (nutritionalImprovement <= 0.01 || minimumCalories > calorieCeiling)
                ) {
                    return@mapNotNull null
                }
                val weeklyCount = assigned.values.flatten().count { it.sameItem(candidate) }
                val recentCount = history.count {
                    it.itemKind == candidate.itemKind && it.itemId == candidate.itemId
                }
                val frequencyBonus = kotlin.math.ln(candidate.frequency.weight + 1.0) * 0.10
                val varietyBonus = if (
                    candidate.itemKind == PlannedItemKind.FOOD &&
                    chosen.none {
                        it.itemKind == PlannedItemKind.FOOD &&
                            foodsById[it.itemId]?.category == foodsById[candidate.itemId]?.category
                    }
                ) 0.12 else 0.0
                val penalty = weeklyCount * 0.10 + recentCount * 0.025
                candidate to (nutritionalImprovement + frequencyBonus + varietyBonus - penalty +
                    random.nextDouble() * 0.04)
            }.sortedByDescending { it.second }

            val best = viable.firstOrNull() ?: break
            chosen += best.first
        }
        return chosen
    }

    private fun combinationError(
        rules: List<PlanningRule>,
        slot: PlanningSlot,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShare: Double
    ): Double {
        val total = rules.fold(MealVector(0.0, 0.0, 0.0, 0.0)) { sum, rule ->
            sum + rule.vector(slot, foodsById, dishesById)
        }
        return nutritionError(
            total.calories, total.protein, total.carbohydrates, total.fat,
            recommendation, mealShare
        )
    }

    private fun PlanningRule.vector(
        slot: PlanningSlot,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): MealVector {
        val grams = fixedGrams[slot.mealType]?.takeIf { slot in fixedSlots }
            ?: preferredGrams * minimumFactor
        return when (itemKind) {
        PlannedItemKind.FOOD -> {
            val food = foodsById[itemId]
            val factor = grams / 100.0
            MealVector(
                (food?.calories ?: 0.0) * factor,
                (food?.proteinGrams ?: 0.0) * factor,
                (food?.carbohydrateGrams ?: 0.0) * factor,
                (food?.fatGrams ?: 0.0) * factor
            )
        }
        PlannedItemKind.DISH -> dishesById[itemId]
            ?.nutritionForGrams(foodsById, grams)
            ?.let {
                MealVector(it.calories, it.proteinGrams, it.carbohydrateGrams, it.fatGrams)
            } ?: MealVector(0.0, 0.0, 0.0, 0.0)
        }
    }

    private fun nutritionError(
        calories: Double,
        protein: Double,
        carbohydrates: Double,
        fat: Double,
        recommendation: Recommendation,
        share: Double
    ): Double {
        fun squared(actual: Double, target: Double): Double {
            if (target <= 0.0) return 0.0
            val error = (actual - target) / target
            return error * error
        }
        return squared(calories, recommendation.calories * share) * 5.0 +
            squared(protein, recommendation.proteinGrams * share) * 4.0 +
            squared(carbohydrates, recommendation.carbohydrateGrams * share) * 1.5 +
            squared(fat, recommendation.fatGrams * share) * 2.0
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
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
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
        val mealBalancePenalty = assignments.keys.sumOf { slot ->
            val meal = meals.first { it.type == slot.mealType && slot.day in it.days }
            val actual = meal.nutrition(foodsById, dishesById, slot.day)
            nutritionError(
                actual.calories,
                actual.proteinGrams,
                actual.carbohydrateGrams,
                actual.fatGrams,
                recommendation,
                mealShares[slot.mealType] ?: defaultMealShares.getValue(slot.mealType)
            ) * 2.5
        }
        val compositionPenalty = assignments.values.sumOf { assignedRules ->
            if (assignedRules.isEmpty()) 100.0 else 0.0
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
        return nutritional + mealBalancePenalty + compositionPenalty +
            quantityPenalty + varietyPenalty + recentPenalty
    }

    private fun isFeasible(
        meals: List<PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation
    ): Boolean = WeekDay.entries.all { day ->
        val assessment = MealPlanEvaluator.assessDay(
            day, meals, foodsById, dishesById, recommendation
        )
        assessment.actual.calories <= assessment.target.calories * 1.10 &&
            assessment.actual.proteinGrams <= assessment.target.proteinGrams * 1.25 &&
            assessment.actual.carbohydrateGrams <= assessment.target.carbohydrateGrams * 1.25 &&
            assessment.actual.fatGrams <= assessment.target.fatGrams * 1.25
    }

    private fun List<PlanningRule>.toMeal(slot: PlanningSlot, generation: Int): PlannedMeal {
        val id = generation.toLong() * 1000L + slot.day.ordinal * 10L + slot.mealType.ordinal + 1L
        return PlannedMeal(
            id = id,
            type = slot.mealType,
            days = setOf(slot.day),
            items = filter { it.itemKind == PlannedItemKind.FOOD }.map { rule ->
                val fixed = rule.fixedGrams[slot.mealType]
                    ?.takeIf { slot in rule.fixedSlots }
                val grams = fixed ?: rule.preferredGrams
                PlannedFood(
                    rule.itemId,
                    grams,
                    fixed == null,
                    if (fixed == null) grams * rule.minimumFactor else grams,
                    if (fixed == null) grams * rule.maximumFactor else grams
                )
            },
            dishes = filter { it.itemKind == PlannedItemKind.DISH }.map { rule ->
                val fixed = rule.fixedGrams[slot.mealType]
                    ?.takeIf { slot in rule.fixedSlots }
                val grams = fixed ?: rule.preferredGrams
                PlannedDish(
                    rule.itemId,
                    grams,
                    fixed == null,
                    if (fixed == null) grams * rule.minimumFactor else grams,
                    if (fixed == null) grams * rule.maximumFactor else grams
                )
            }
        )
    }

    private fun PlanningRule.sameItem(other: PlanningRule): Boolean =
        itemKind == other.itemKind && itemId == other.itemId

    private fun relativeError(actual: Double, target: Double): Double =
        if (target <= 0.0) 0.0 else abs(actual - target) / target
    private val defaultMealShares = mapOf(
        MealType.BREAKFAST to 0.25,
        MealType.MORNING_SNACK to 0.10,
        MealType.LUNCH to 0.35,
        MealType.AFTERNOON_SNACK to 0.10,
        MealType.DINNER to 0.20
    )

}
