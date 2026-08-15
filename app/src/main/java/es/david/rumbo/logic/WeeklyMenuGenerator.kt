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
import es.david.rumbo.model.totalWeightGrams
import java.util.Random
import kotlin.math.abs
import kotlin.math.pow

data class GeneratedWeeklyMenu(
    val meals: List<PlannedMeal>,
    val history: List<MenuHistoryEntry>,
    val generation: Int,
    val diagnostics: List<NutritionDeviation> = emptyList()
)

data class NutritionDeviation(
    val day: WeekDay,
    val calories: Double,
    val protein: Double,
    val carbohydrates: Double,
    val fat: Double
) {
    val worst: Double get() = maxOf(calories, protein, carbohydrates, fat)
    val weightedTotal: Double get() = calories * 1.25 + protein * 1.15 + carbohydrates + fat
}

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
        seed: Long = 11L
    ): GeneratedWeeklyMenu {
        val foodRules = rules.filter { it.itemKind == PlannedItemKind.FOOD && it.isActive }
            .map { rule ->
                rule.copy(
                    allowedMealTypes = rule.allowedMealTypes + rule.fixedSlots.map { it.mealType },
                    allowedDays = WeekDay.entries.toSet(),
                    fixedSlots = emptySet()
                )
            }
        require(foodRules.isNotEmpty()) { "Añade al menos un alimento al menú." }
        require(foodRules.all { it.isValid() }) { "Hay reglas de planificación incompletas." }
        require(foodRules.all { foodsById[it.itemId]?.hasComparableNutrition() == true }) {
            "Todos los alimentos seleccionados necesitan datos nutricionales completos."
        }
        val activeFoodIds = foodRules.mapTo(mutableSetOf()) { it.itemId }
        val usableDishes = dishesById.values.filter { dish ->
            dish.nutrition(foodsById).isComplete && dish.ingredients.all { it.foodId in activeFoodIds }
        }
        val derivedRules = foodRules + usableDishes.mapNotNull { dish ->
            val ingredientRules = foodRules.filter { rule ->
                dish.ingredients.any { it.foodId == rule.itemId } && rule.allowedMealTypes.isNotEmpty()
            }
            val allowedMealTypes = ingredientRules.flatMapTo(mutableSetOf()) { it.allowedMealTypes }
                .intersect(dish.allowedMealTypes)
            if (ingredientRules.isEmpty() || allowedMealTypes.isEmpty()) null else PlanningRule(
                itemKind = PlannedItemKind.DISH,
                itemId = dish.id,
                allowedMealTypes = allowedMealTypes,
                allowedDays = WeekDay.entries.toSet(),
                frequency = PlanningFrequency.NORMAL,
                preferredGrams = dish.totalWeightGrams().coerceAtLeast(1.0)
            )
        }
        val fixedBySlot = resolveFixedSlots(foodRules, usableDishes)

        val generatedTypes = MealType.entries.filter { type ->
            (mealShares[type] ?: defaultMealShares.getValue(type)) > 0.0 &&
                (derivedRules.any { type in it.allowedMealTypes && it.frequency != PlanningFrequency.NEVER && it.frequency != PlanningFrequency.ALWAYS } ||
                    fixedBySlot.keys.any { it.mealType == type })
        }.toSet()
        require(generatedTypes.isNotEmpty()) { "Indica al menos una comida en las reglas del menú." }

        val slots = WeekDay.entries.flatMap { day ->
            generatedTypes.map { type -> PlanningSlot(day, type) }
        }
        slots.forEach { slot ->
            if (fixedBySlot[slot].isNullOrEmpty() && derivedRules.none {
                    slot.mealType in it.allowedMealTypes &&
                        it.frequency != PlanningFrequency.NEVER && it.frequency != PlanningFrequency.ALWAYS
                }) {
                throw PlanningConflictException(
                    "No hay candidatos para ${slot.day.label.lowercase()} · ${slot.mealType.label.lowercase()}."
                )
            }
        }

        val generation = (history.maxOfOrNull { it.generation } ?: 0) + 1
        val recent = history.filter { it.generation >= generation - HISTORY_GENERATIONS }
        val skippedTypes = MealType.entries.filterTo(mutableSetOf()) { type ->
            (mealShares[type] ?: defaultMealShares.getValue(type)) <= 0.0
        }
        val preserved = currentMeals.filterNot { it.type in generatedTypes || it.type in skippedTypes }
        var bestMeals: List<PlannedMeal>? = null
        var bestAssignments: Map<PlanningSlot, List<PlanningRule>>? = null
        var bestScore = Double.POSITIVE_INFINITY
        var bestDayTemplate: Map<MealType, List<PlanningRule>>? = null
        var bestDayScore = Double.POSITIVE_INFINITY

        repeat(CANDIDATE_WEEKS) { candidateIndex ->
            val random = Random(seed + candidateIndex * 104729L)
            val assignments = linkedMapOf<PlanningSlot, List<PlanningRule>>()
            slots.forEach { slot ->
                assignments[slot] = completeSlot(
                    slot = slot,
                    fixed = fixedBySlot[slot].orEmpty(),
                    rules = derivedRules,
                    foodRules = foodRules,
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
            WeekDay.entries.forEach { day ->
                val dayScore = dayNutritionQuality(
                    MealPlanEvaluator.assessDay(
                        day, optimized, foodsById, dishesById, recommendation
                    )
                )
                if (dayScore < bestDayScore) {
                    bestDayScore = dayScore
                    bestDayTemplate = assignments.filterKeys { it.day == day }
                        .mapKeys { it.key.mealType }
                }
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

        // Frequencies below ALWAYS are preferences, not weekly quotas. If a
        // nutritionally strong day was found, repeating its structure is a
        // valid fallback. Variety may beat it, but may never make an otherwise
        // feasible repertoire look impossible.
        bestDayTemplate?.let { template ->
            val repeatedAssignments = slots.associateWith { slot ->
                template[slot.mealType].orEmpty()
            }
            val repeatedMeals = repeatedAssignments.map { (slot, assignedRules) ->
                assignedRules.toMeal(slot, generation)
            }
            val optimizedRepeated = MealQuantityOptimizer.optimize(
                preserved + repeatedMeals, foodsById, dishesById, recommendation,
                mealShares = mealShares
            ).meals
            val repeatedScore = score(
                optimizedRepeated, repeatedAssignments, recent, foodsById,
                dishesById, recommendation, mealShares
            )
            if (repeatedScore < bestScore) {
                bestScore = repeatedScore
                bestMeals = optimizedRepeated
                bestAssignments = repeatedAssignments
            }
        }

        val assignments = bestAssignments ?: throw PlanningConflictException(
            "Las reglas de planificación son contradictorias y no permiten construir todos los huecos."
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

        val generatedMeals = checkNotNull(bestMeals)
        val incumbentIsComplete = currentMeals.isNotEmpty() && WeekDay.entries.all { day ->
            val assessment = MealPlanEvaluator.assessDay(
                day, currentMeals, foodsById, dishesById, recommendation
            )
            assessment.missingMealTypes.isEmpty() && assessment.actual.isComplete
        }
        val retainIncumbent = incumbentIsComplete &&
            nutritionalQuality(currentMeals, foodsById, dishesById, recommendation) <=
            nutritionalQuality(generatedMeals, foodsById, dishesById, recommendation)
        val selectedMeals = if (retainIncumbent) currentMeals else generatedMeals
        return GeneratedWeeklyMenu(
            meals = selectedMeals,
            history = if (retainIncumbent) history else newHistory,
            generation = if (retainIncumbent) {
                (history.maxOfOrNull { it.generation } ?: generation)
            } else {
                generation
            },
            diagnostics = WeekDay.entries.map { day ->
                deviation(day, MealPlanEvaluator.assessDay(
                    day, selectedMeals, foodsById, dishesById, recommendation
                ))
            }
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
        foodRules: List<PlanningRule>,
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
                it.frequency != PlanningFrequency.NEVER && it.frequency != PlanningFrequency.ALWAYS
        }
        val maximumItems = when (slot.mealType) {
            MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK -> 3
            else -> 4
        }

        while (chosen.size < maximumItems) {
            var candidates = eligible.filter { candidate ->
                chosen.none { it.sameItem(candidate) || it.overlaps(candidate, dishesById) } &&
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
                val frequencyBonus = kotlin.math.ln(
                    preferenceWeight(candidate, slot, foodRules, dishesById) + 1.0
                ) * 0.10
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

    private fun resolveFixedSlots(
        foodRules: List<PlanningRule>,
        dishes: List<Dish>
    ): Map<PlanningSlot, List<PlanningRule>> = foodRules
        .flatMap { rule -> rule.requiredSlots().map { it to rule } }
        .groupBy({ it.first }, { it.second })
        .mapValues { (slot, required) ->
            val remaining = required.distinctBy { it.itemId }.toMutableList()
            val selected = mutableListOf<PlanningRule>()
            while (true) {
                val best = dishes.filter { dish ->
                    slot.mealType in dish.allowedMealTypes
                }.map { dish ->
                    dish to remaining.count { rule ->
                        slot.mealType in rule.allowedMealTypes &&
                            dish.ingredients.any { it.foodId == rule.itemId }
                    }
                }.maxByOrNull { it.second }?.takeIf { it.second >= 2 } ?: break
                val covered = remaining.filter { rule ->
                    best.first.ingredients.any { it.foodId == rule.itemId }
                }
                selected += PlanningRule(
                    itemKind = PlannedItemKind.DISH,
                    itemId = best.first.id,
                    allowedMealTypes = setOf(slot.mealType),
                    fixedSlots = setOf(slot),
                    frequency = PlanningFrequency.FREQUENT,
                    preferredGrams = best.first.totalWeightGrams().coerceAtLeast(1.0)
                )
                remaining.removeAll(covered)
            }
            selected + remaining
        }

    private fun preferenceWeight(
        candidate: PlanningRule,
        slot: PlanningSlot,
        foodRules: List<PlanningRule>,
        dishesById: Map<Long, Dish>
    ): Double {
        fun alternatives(rule: PlanningRule): Int = 1 + dishesById.values.count { dish ->
            dish.ingredients.any { it.foodId == rule.itemId } &&
                slot.mealType in rule.allowedMealTypes
        }
        return when (candidate.itemKind) {
            PlannedItemKind.FOOD -> foodRules.firstOrNull { it.itemId == candidate.itemId }
                ?.let { it.frequency.weight / alternatives(it) } ?: 0.0
            PlannedItemKind.DISH -> {
                val ingredientIds = dishesById[candidate.itemId]?.ingredients?.mapTo(mutableSetOf()) { it.foodId }
                    .orEmpty()
                foodRules.filter { it.itemId in ingredientIds && slot.mealType in it.allowedMealTypes }
                    .sumOf { it.frequency.weight / alternatives(it) }
            }
        }
    }

    private fun PlanningRule.overlaps(
        other: PlanningRule,
        dishesById: Map<Long, Dish>
    ): Boolean {
        if (itemKind == PlannedItemKind.FOOD && other.itemKind == PlannedItemKind.DISH) {
            return dishesById[other.itemId]?.ingredients?.any { it.foodId == itemId } == true
        }
        if (itemKind == PlannedItemKind.DISH && other.itemKind == PlannedItemKind.FOOD) {
            return dishesById[itemId]?.ingredients?.any { it.foodId == other.itemId } == true
        }
        return false
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
        val grams = preferredGrams * minimumFactor
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
        val proteinTarget = recommendation.proteinGrams * share
        val proteinDeficit = if (protein < proteinTarget) {
            squared(protein, proteinTarget)
        } else 0.0
        // A meal should roughly occupy its chosen energy share, but it need
        // not reproduce the complete daily macro ratio. The whole day and
        // week are responsible for nutritional balance.
        return squared(calories, recommendation.calories * share) * 5.0 +
            proteinDeficit * 0.75
    }

    private fun chooseRule(
        slot: PlanningSlot,
        rules: List<PlanningRule>,
        assigned: Map<PlanningSlot, List<PlanningRule>>,
        history: List<MenuHistoryEntry>,
        random: Random
    ): PlanningRule {
        val candidates = rules.filter {
            slot.mealType in it.allowedMealTypes &&
                it.frequency != PlanningFrequency.NEVER && it.frequency != PlanningFrequency.ALWAYS
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

    private fun nutritionalQuality(
        meals: List<PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation
    ): Double {
        val daily = WeekDay.entries.map { day ->
            MealPlanEvaluator.assessDay(day, meals, foodsById, dishesById, recommendation)
        }
        return nutritionQuality(daily)
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
        val deviations = daily.mapIndexed { index, assessment ->
            deviation(WeekDay.entries[index], assessment)
        }
        // The weekly result is decisive. Daily fit remains a secondary
        // quality objective, so one imperfect day cannot outweigh a clearly
        // better week.
        val nutritional = nutritionQuality(daily)
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
        return nutritional + mealBalancePenalty * 10.0 + compositionPenalty +
            quantityPenalty + varietyPenalty + recentPenalty
    }

    private fun deviation(day: WeekDay, assessment: PlanNutritionAssessment) = NutritionDeviation(
        day = day,
        calories = NutritionTolerancePolicy.evaluate(
            NutrientKind.CALORIES, assessment.actual.calories, assessment.target.calories
        ).penalty,
        protein = NutritionTolerancePolicy.evaluate(
            NutrientKind.PROTEIN, assessment.actual.proteinGrams, assessment.target.proteinGrams
        ).penalty,
        carbohydrates = NutritionTolerancePolicy.evaluate(
            NutrientKind.CARBOHYDRATES,
            assessment.actual.carbohydrateGrams,
            assessment.target.carbohydrateGrams
        ).penalty,
        fat = NutritionTolerancePolicy.evaluate(
            NutrientKind.FAT, assessment.actual.fatGrams, assessment.target.fatGrams
        ).penalty
    )

    private fun nutritionQuality(daily: List<PlanNutritionAssessment>): Double {
        fun weeklyError(actual: (PlanNutritionAssessment) -> Double, target: Double): Double {
            if (target <= 0.0) return 0.0
            val ratio = daily.map(actual).average() / target
            return (ratio - 1.0).pow(2)
        }
        val target = daily.first().target
        val weeklyErrors = listOf(
            weeklyError({ it.actual.calories }, target.calories),
            weeklyError({ it.actual.proteinGrams }, target.proteinGrams),
            weeklyError({ it.actual.carbohydrateGrams }, target.carbohydrateGrams),
            weeklyError({ it.actual.fatGrams }, target.fatGrams)
        )
        val dailyDeviations = daily.mapIndexed { index, assessment ->
            deviation(WeekDay.entries[index], assessment)
        }
        return weeklyErrors.maxOrNull()!! * 1_000_000.0 +
            weeklyErrors.sum() * 100_000.0 +
            dailyDeviations.maxOf { it.worst } * 1_000.0 +
            dailyDeviations.sumOf { it.weightedTotal } * 100.0
    }

    private fun dayNutritionQuality(assessment: PlanNutritionAssessment): Double {
        fun error(actual: Double, target: Double): Double {
            if (target <= 0.0) return 0.0
            return ((actual - target) / target).pow(2)
        }
        val errors = listOf(
            error(assessment.actual.calories, assessment.target.calories),
            error(assessment.actual.proteinGrams, assessment.target.proteinGrams),
            error(
                assessment.actual.carbohydrateGrams,
                assessment.target.carbohydrateGrams
            ),
            error(assessment.actual.fatGrams, assessment.target.fatGrams)
        )
        return errors.maxOrNull()!! * 10.0 + errors.sum()
    }

    private fun List<PlanningRule>.toMeal(slot: PlanningSlot, generation: Int): PlannedMeal {
        val id = generation.toLong() * 1000L + slot.day.ordinal * 10L + slot.mealType.ordinal + 1L
        return PlannedMeal(
            id = id,
            type = slot.mealType,
            days = setOf(slot.day),
            items = filter { it.itemKind == PlannedItemKind.FOOD }.map { rule ->
                val grams = rule.preferredGrams
                PlannedFood(
                    rule.itemId,
                    grams,
                    true,
                    grams * rule.minimumFactor,
                    grams * rule.maximumFactor
                )
            },
            dishes = filter { it.itemKind == PlannedItemKind.DISH }.map { rule ->
                val grams = rule.preferredGrams
                PlannedDish(
                    rule.itemId,
                    grams,
                    true,
                    grams * rule.minimumFactor,
                    grams * rule.maximumFactor
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
