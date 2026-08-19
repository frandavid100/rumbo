package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation

/**
 * Deterministic bounded repair around an already certified viable day.
 *
 * COMPLETE adds coverage/fibre requirements on top of viability. Rebuilding the
 * whole day from random seeds can miss a nearby valid composition even when the
 * existing viable witness only needs one or two substitutions. This repair
 * explores those substitutions directly and reuses the real quantity optimiser
 * and culinary validator.
 */
object CompleteDayWitnessRepair {
    private const val BEAM_WIDTH = 4
    private const val MAX_DEPTH = 4
    private const val MAX_CANDIDATES_PER_MEAL = 2
    private const val MAX_VARIANTS_PER_STATE = 4
    private const val MAX_OPTIMIZATIONS = 24

    fun find(
        baseline: CertifiedDayWitness,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): CertifiedDayWitness? {
        val start = baseline.copy(level = CertifiedDayLevel.VIABLE)
        if (!CertifiedDayWitnessEvaluator.isViable(
                start, rules, foodsById, dishesById, recommendation, mealShares
            )
        ) return null

        val activeRules = rules.filter {
            it.itemKind == PlannedItemKind.FOOD &&
                it.isActive &&
                it.frequency != PlanningFrequency.NEVER &&
                foodsById[it.itemId]?.hasComparableNutrition() == true
        }

        var beam = listOf(start)
        var optimizations = 0
        repeat(MAX_DEPTH + 1) { depth ->
            beam.forEach { state ->
                val complete = state.copy(
                    level = CertifiedDayLevel.COMPLETE,
                    fingerprint = state.meals.hashCode()
                )
                if (CertifiedDayWitnessEvaluator.isComplete(
                        complete, rules, foodsById, dishesById, recommendation, mealShares
                    )
                ) return complete
            }
            if (depth == MAX_DEPTH) return@repeat

            val next = linkedMapOf<String, CertifiedDayWitness>()
            beam.forEach { state ->
                expand(
                    state, activeRules, foodsById, dishesById, recommendation
                ).take(MAX_VARIANTS_PER_STATE).forEach variantLoop@ { variant ->
                    if (optimizations >= MAX_OPTIMIZATIONS) return null
                    optimizations += 1
                    val optimized = runCatching {
                        MealQuantityOptimizer.optimize(
                            variant.meals,
                            foodsById,
                            dishesById,
                            recommendation,
                            days = setOf(variant.day),
                            mealShares = mealShares
                        ).meals
                    }.getOrNull() ?: return@variantLoop
                    if (!WeeklyMenuGenerator.isCulinarilyValid(
                            optimized, foodsById, dishesById
                        )
                    ) return@variantLoop
                    val candidate = variant.copy(
                        meals = optimized,
                        fingerprint = optimized.hashCode()
                    )
                    if (!candidate.isStructurallyValid()) return@variantLoop
                    val key = compositionKey(candidate)
                    val previous = next[key]
                    if (previous == null || score(
                            candidate, foodsById, dishesById, recommendation
                        ) < score(previous, foodsById, dishesById, recommendation)
                    ) {
                        next[key] = candidate
                    }
                }
            }
            if (next.isEmpty()) return null
            beam = next.values
                .sortedBy { score(it, foodsById, dishesById, recommendation) }
                .take(BEAM_WIDTH)
        }
        return null
    }

    private fun expand(
        witness: CertifiedDayWitness,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation
    ): List<CertifiedDayWitness> {
        val fruitMeals = mealsContaining(witness, FoodCategory.FRUIT, foodsById, dishesById)
        val vegetableMeals = mealsContaining(witness, FoodCategory.VEGETABLE, foodsById, dishesById)
        val assessment = MealPlanEvaluator.assessDay(
            witness.day, witness.meals, foodsById, dishesById, recommendation
        )
        val fiberDeficient = assessment.actual.fiberGrams < 25.0
        val neededCategories = buildSet {
            if (fruitMeals < 2) add(FoodCategory.FRUIT)
            if (vegetableMeals < 2) add(FoodCategory.VEGETABLE)
        }

        return buildList {
            witness.meals.forEachIndexed { mealIndex, meal ->
                val maximumItems = when (meal.type) {
                    MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK -> 3
                    else -> 4
                }
                val candidates = rules.asSequence()
                    .filter { meal.type in it.allowedMealTypes }
                    .mapNotNull { rule ->
                        val food = foodsById[rule.itemId] ?: return@mapNotNull null
                        val categoryNeeded = food.category in neededCategories &&
                            !mealContains(meal, food.category, foodsById, dishesById)
                        val fiberUseful = fiberDeficient && (food.fiberGrams ?: 0.0) > 0.0
                        if (!categoryNeeded && !fiberUseful) return@mapNotNull null
                        val adjusted = CulinaryPolicy.applyPortion(rule, food)
                        adjusted to food
                    }
                    .filter { (rule, _) -> meal.items.none { it.foodId == rule.itemId } }
                    .sortedByDescending { (rule, food) ->
                        candidatePriority(
                            rule, food, neededCategories, fiberDeficient, meal.type
                        )
                    }
                    .distinctBy { it.first.itemId }
                    .take(MAX_CANDIDATES_PER_MEAL)
                    .toList()

                candidates.forEach { (rule, _) ->
                    val planned = rule.toPlannedFood()
                    if (meal.items.size + meal.dishes.size < maximumItems) {
                        val changed = meal.copy(
                            items = meal.items + planned,
                            dayAmounts = emptyList()
                        )
                        val meals = witness.meals.toMutableList().also {
                            it[mealIndex] = changed
                        }
                        if (WeeklyMenuGenerator.isCulinarilyValid(
                                meals, foodsById, dishesById
                            )
                        ) {
                            add(witness.copy(meals = meals, fingerprint = meals.hashCode()))
                        }
                    }

                    meal.items.indices.forEach replaceLoop@ { itemIndex ->
                        val replacedId = meal.items[itemIndex].foodId
                        val mandatory = rules.any {
                            it.itemId == replacedId &&
                                it.frequency == PlanningFrequency.ALWAYS &&
                                meal.type in it.allowedMealTypes
                        }
                        if (mandatory) return@replaceLoop
                        val items = meal.items.toMutableList().also {
                            it[itemIndex] = planned
                        }
                        val changed = meal.copy(items = items, dayAmounts = emptyList())
                        val meals = witness.meals.toMutableList().also {
                            it[mealIndex] = changed
                        }
                        if (WeeklyMenuGenerator.isCulinarilyValid(
                                meals, foodsById, dishesById
                            )
                        ) {
                            add(witness.copy(meals = meals, fingerprint = meals.hashCode()))
                        }
                    }
                }
            }
        }.distinctBy(::compositionKey)
    }

    private fun candidatePriority(
        rule: PlanningRule,
        food: Food,
        neededCategories: Set<FoodCategory>,
        fiberDeficient: Boolean,
        mealType: MealType
    ): Double {
        val categoryBonus = if (food.category in neededCategories) 1_000_000.0 else 0.0
        val adjusted = CulinaryPolicy.applyPortion(rule, food)
        val fiberCapacity = if (fiberDeficient) {
            (food.fiberGrams ?: 0.0) * adjusted.preferredGrams * adjusted.maximumFactor / 100.0
        } else 0.0
        val culinaryBonus = if (CulinaryPolicy.isSuggestedForMeal(food, mealType)) 100.0 else 0.0
        return categoryBonus + fiberCapacity * 1_000.0 + culinaryBonus
    }

    private fun score(
        witness: CertifiedDayWitness,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation
    ): Double {
        val assessment = MealPlanEvaluator.assessDay(
            witness.day, witness.meals, foodsById, dishesById, recommendation
        )
        val fruitMissing = (2 - mealsContaining(
            witness, FoodCategory.FRUIT, foodsById, dishesById
        )).coerceAtLeast(0)
        val vegetableMissing = (2 - mealsContaining(
            witness, FoodCategory.VEGETABLE, foodsById, dishesById
        )).coerceAtLeast(0)
        val fiberMissing = (25.0 - assessment.actual.fiberGrams).coerceAtLeast(0.0) / 25.0
        val macroPenalty = assessment.evaluations.sumOf { evaluation ->
            val relative = evaluation.difference / evaluation.target.coerceAtLeast(1.0)
            relative * relative
        }
        return (fruitMissing + vegetableMissing) * 1_000_000.0 +
            fiberMissing * 10_000.0 + macroPenalty
    }

    private fun mealsContaining(
        witness: CertifiedDayWitness,
        category: FoodCategory,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): Int = witness.meals.count { meal ->
        mealContains(meal, category, foodsById, dishesById)
    }

    private fun mealContains(
        meal: es.david.rumbo.model.PlannedMeal,
        category: FoodCategory,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): Boolean {
        if (meal.items.any { foodsById[it.foodId]?.category == category }) return true
        return meal.dishes.any { plannedDish ->
            dishesById[plannedDish.dishId]?.ingredients?.any {
                foodsById[it.foodId]?.category == category
            } == true
        }
    }

    private fun PlanningRule.toPlannedFood(): PlannedFood {
        val minimum = preferredGrams * minimumFactor
        val maximum = preferredGrams * maximumFactor
        return PlannedFood(
            foodId = itemId,
            grams = preferredGrams,
            adjustable = true,
            minimumGrams = minimum,
            maximumGrams = maximum
        )
    }

    private fun compositionKey(witness: CertifiedDayWitness): String =
        witness.meals.sortedBy { it.type.ordinal }.joinToString("|") { meal ->
            val foods = meal.items.map { it.foodId }.sorted().joinToString(",")
            val dishes = meal.dishes.map { it.dishId }.sorted().joinToString(",")
            "${meal.type.name}:f[$foods]:d[$dishes]"
        }
}
