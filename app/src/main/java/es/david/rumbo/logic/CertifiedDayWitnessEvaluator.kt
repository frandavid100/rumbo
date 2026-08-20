package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.WeekDay
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.resolvedGrams

object CertifiedDayWitnessEvaluator {
    fun fromMenuWitness(
        witness: MenuWitness,
        level: CertifiedDayLevel = CertifiedDayLevel.VIABLE
    ): CertifiedDayWitness? {
        val days = witness.meals.flatMap { it.days }.distinct()
        if (days.size != 1) return null
        return CertifiedDayWitness(
            level = level,
            seed = witness.seed,
            day = days.single(),
            meals = witness.meals,
            fingerprint = witness.fingerprint
        ).takeIf { it.isStructurallyValid() }
    }

    fun isViable(
        witness: CertifiedDayWitness,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): Boolean {
        if (!witness.isStructurallyValid()) return false
        val constraints = MenuConstraintModel.fromLegacyData(rules, foodsById, mealShares)
        if (constraints.structuralViolations.isNotEmpty()) return false
        val activeRules = constraints.activeRules
        val activeByFood = activeRules.groupBy { it.itemId }
        val activeMealTypes = constraints.activeMealTypes
        val meals = witness.meals

        if (meals.any { meal ->
                meal.items.any { item ->
                    val food = foodsById[item.foodId] ?: return false
                    val grams = meal.resolvedGrams(item, witness.day)
                    !usesPracticalUnits(grams, food.practicalUnitStep())
                } || meal.dishes.any { item ->
                    val dish = dishesById[item.dishId] ?: return false
                    val grams = meal.resolvedGrams(item, witness.day)
                    !usesPracticalUnits(grams, dish.practicalUnitStep())
                }
            }
        ) return false

        if (meals.map { it.type }.toSet() != activeMealTypes) return false
        if (meals.any { it.type !in activeMealTypes }) return false

        meals.forEach { meal ->
            meal.items.forEach { item ->
                val compatible = activeByFood[item.foodId].orEmpty().any { rule ->
                    meal.type in rule.allowedMealTypes && rule.frequency != PlanningFrequency.NEVER
                }
                if (!compatible) return false
            }
            meal.dishes.forEach { plannedDish ->
                val dish = dishesById[plannedDish.dishId] ?: return false
                if (meal.type !in dish.allowedMealTypes) return false
                if (dish.ingredients.any { ingredient ->
                        activeByFood[ingredient.foodId].orEmpty().none { rule ->
                            meal.type in rule.allowedMealTypes && rule.frequency != PlanningFrequency.NEVER
                        }
                    }
                ) return false
            }
        }

        activeRules.filter { it.frequency == PlanningFrequency.ALWAYS }.forEach { rule ->
            rule.allowedMealTypes.intersect(activeMealTypes).forEach { mealType ->
                val meal = meals.singleOrNull { it.type == mealType } ?: return false
                val direct = meal.items.any { it.foodId == rule.itemId }
                val inDish = meal.dishes.any { plannedDish ->
                    dishesById[plannedDish.dishId]?.ingredients?.any { it.foodId == rule.itemId } == true
                }
                if (!direct && !inDish) return false
            }
        }

        if (!WeeklyMenuGenerator.isCulinarilyValid(meals, foodsById, dishesById)) return false
        val assessment = MealPlanEvaluator.assessDay(
            witness.day, meals, foodsById, dishesById, recommendation
        )
        return WeeklyMenuAcceptancePolicy.isDayAcceptable(assessment, activeMealTypes)
    }

    /** COMPLETE = viable + fruit in two distinct meals + vegetables in two distinct meals + >=25 g fibre. */
    fun isComplete(
        witness: CertifiedDayWitness,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): Boolean {
        if (witness.level != CertifiedDayLevel.COMPLETE || !isViable(
                witness, rules, foodsById, dishesById, recommendation, mealShares
            )) return false
        return completeCriteria(witness.day, witness.meals, foodsById, dishesById, recommendation)
    }

    data class CompleteDayDiagnostic(
        val fruitMeals: Int,
        val vegetableMeals: Int,
        val fiberGrams: Double,
        val viable: Boolean,
        val limitingNutrient: NutrientKind? = null,
        val limitingDifference: Double? = null,
        val deficientNutrient: NutrientKind? = null,
        val deficientDifference: Double? = null,
        val availableFruitMeals: Int = 0,
        val availableVegetableMeals: Int = 0
    )

    data class CompleteDaySearchResult(
        val witness: CertifiedDayWitness?,
        val diagnostic: CompleteDayDiagnostic?,
        val progressWitness: CertifiedDayWitness? = null
    )

    fun findCompleteWitness(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): CertifiedDayWitness? = findCompleteDay(
        rules, foodsById, dishesById, recommendation, mealShares
    ).witness

    fun findCompleteDay(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        baselineWitness: CertifiedDayWitness? = null
    ): CompleteDaySearchResult {
        val constraints = MenuConstraintModel.fromLegacyData(rules, foodsById, mealShares)
        if (constraints.structuralViolations.isNotEmpty()) return CompleteDaySearchResult(null, null)
        fun availableMeals(category: FoodCategory): Int = constraints.activeMealTypes.count { mealType ->
            constraints.activeRules.any { rule ->
                mealType in rule.allowedMealTypes && rule.frequency != PlanningFrequency.NEVER &&
                    foodsById[rule.itemId]?.category == category
            }
        }
        val availableFruitMeals = availableMeals(FoodCategory.FRUIT)
        val availableVegetableMeals = availableMeals(FoodCategory.VEGETABLE)
        val seeds = listOf(
            11L, 37L, 89L, 131L, 197L, 251L, 313L, 401L, 509L, 607L, 701L, 809L,
            907L, 1009L, 1103L, 1201L, 1301L, 1409L, 1511L, 1601L, 1709L, 1801L,
            1901L, 2003L, 2111L, 2203L, 2309L, 2411L, 2503L, 2609L, 2707L, 2801L
        )
        var bestDiagnostic: CompleteDayDiagnostic? = null
        var bestProgressWitness: CertifiedDayWitness? = null
        var bestScore = Double.NEGATIVE_INFINITY
        var bestAttemptDiagnostic: CompleteDayDiagnostic? = null
        var bestAttemptScore = Double.NEGATIVE_INFINITY

        fun considerProgressWitness(candidate: CertifiedDayWitness) {
            if (!isViable(candidate, rules, foodsById, dishesById, recommendation, mealShares)) return
            val assessment = MealPlanEvaluator.assessDay(
                candidate.day, candidate.meals, foodsById, dishesById, recommendation
            )
            val fruitMeals = mealsContaining(candidate.meals, FoodCategory.FRUIT, foodsById, dishesById)
            val vegetableMeals = mealsContaining(candidate.meals, FoodCategory.VEGETABLE, foodsById, dishesById)
            val limitingEvaluation = assessment.evaluations
                .filter { it.fit == TargetFit.OUTSIDE }
                .maxByOrNull { kotlin.math.abs(it.difference / it.target.coerceAtLeast(1.0)) }
            val deficientEvaluation = assessment.evaluations
                .filter { it.kind != NutrientKind.CALORIES && it.difference < 0.0 }
                .minByOrNull { it.difference / it.target.coerceAtLeast(1.0) }
            val diagnostic = CompleteDayDiagnostic(
                fruitMeals = fruitMeals,
                vegetableMeals = vegetableMeals,
                fiberGrams = assessment.actual.fiberGrams,
                viable = true,
                limitingNutrient = limitingEvaluation?.kind,
                limitingDifference = limitingEvaluation?.difference,
                deficientNutrient = deficientEvaluation?.kind,
                deficientDifference = deficientEvaluation?.difference,
                availableFruitMeals = availableFruitMeals,
                availableVegetableMeals = availableVegetableMeals
            )
            val score = fruitMeals.coerceAtMost(2) * 1_000_000.0 +
                vegetableMeals.coerceAtMost(2) * 1_000_000.0 +
                assessment.actual.fiberGrams.coerceAtMost(25.0) * 1_000.0
            if (score > bestScore) {
                bestScore = score
                bestDiagnostic = diagnostic
                bestProgressWitness = candidate.copy(level = CertifiedDayLevel.VIABLE)
            }
        }

        fun repairedResult(repaired: CertifiedDayWitness): CompleteDaySearchResult {
            val assessment = MealPlanEvaluator.assessDay(
                repaired.day, repaired.meals, foodsById, dishesById, recommendation
            )
            return CompleteDaySearchResult(
                witness = repaired,
                diagnostic = CompleteDayDiagnostic(
                    fruitMeals = mealsContaining(
                        repaired.meals, FoodCategory.FRUIT, foodsById, dishesById
                    ),
                    vegetableMeals = mealsContaining(
                        repaired.meals, FoodCategory.VEGETABLE, foodsById, dishesById
                    ),
                    fiberGrams = assessment.actual.fiberGrams,
                    viable = true,
                    availableFruitMeals = availableFruitMeals,
                    availableVegetableMeals = availableVegetableMeals
                ),
                progressWitness = repaired.copy(level = CertifiedDayLevel.VIABLE)
            )
        }

        // Prefer an explicitly supplied persisted witness, but recover a fresh
        // deterministic viable witness if the caller has none (or an old one has
        // become invalid). This keeps COMPLETE repair available for new/migrated
        // profiles and avoids making UI recomposition order part of correctness.
        val suppliedBaseline = baselineWitness
            ?.takeIf { it.isStructurallyValid() }
            ?.takeIf { isViable(it, rules, foodsById, dishesById, recommendation, mealShares) }
        val freshBaseline = if (suppliedBaseline == null) {
            runCatching {
                RepertoireEvaluator.evaluate(
                    rules = rules,
                    foodsById = foodsById,
                    dishesById = dishesById,
                    recommendation = recommendation,
                    mealShares = mealShares
                )
            }.getOrNull()
                ?.takeIf { it.searchStatus == ConstraintSearchStatus.FEASIBLE }
                ?.witness
                ?.let(::fromMenuWitness)
                ?.takeIf { isViable(it, rules, foodsById, dishesById, recommendation, mealShares) }
        } else null
        val repairBaseline = suppliedBaseline ?: freshBaseline

        repairBaseline?.let { baseline ->
            considerProgressWitness(baseline)
            CompleteDayWitnessRepair.find(
                baseline,
                rules,
                foodsById,
                dishesById,
                recommendation,
                mealShares
            )?.let { return repairedResult(it) }
        }

        for (seed in seeds) {
            val generated = runCatching {
                WeeklyMenuGenerator.generate(
                    currentMeals = emptyList(),
                    rules = rules,
                    history = emptyList(),
                    foodsById = foodsById,
                    dishesById = dishesById,
                    recommendation = recommendation,
                    mealShares = mealShares,
                    seed = seed,
                    days = setOf(WeekDay.MONDAY),
                    objective = MenuGenerationObjective.COMPLETE
                )
            }.getOrNull() ?: continue
            val assessment = MealPlanEvaluator.assessDay(
                WeekDay.MONDAY, generated.meals, foodsById, dishesById, recommendation
            )
            val fruitMeals = mealsContaining(
                generated.meals, FoodCategory.FRUIT, foodsById, dishesById
            )
            val vegetableMeals = mealsContaining(
                generated.meals, FoodCategory.VEGETABLE, foodsById, dishesById
            )
            val viable = WeeklyMenuAcceptancePolicy.isDayAcceptable(
                assessment, constraints.activeMealTypes
            )
            val limitingEvaluation = assessment.evaluations
                .filter { it.fit == TargetFit.OUTSIDE }
                .maxByOrNull { kotlin.math.abs(it.difference / it.target.coerceAtLeast(1.0)) }
            val deficientEvaluation = assessment.evaluations
                .filter { it.kind != NutrientKind.CALORIES && it.difference < 0.0 }
                .minByOrNull { it.difference / it.target.coerceAtLeast(1.0) }
            val diagnostic = CompleteDayDiagnostic(
                fruitMeals = fruitMeals,
                vegetableMeals = vegetableMeals,
                fiberGrams = assessment.actual.fiberGrams,
                viable = viable,
                limitingNutrient = limitingEvaluation?.kind,
                limitingDifference = limitingEvaluation?.difference,
                deficientNutrient = deficientEvaluation?.kind,
                deficientDifference = deficientEvaluation?.difference,
                availableFruitMeals = availableFruitMeals,
                availableVegetableMeals = availableVegetableMeals
            )
            val attemptScore = fruitMeals.coerceAtMost(2) * 1_000_000.0 +
                vegetableMeals.coerceAtMost(2) * 1_000_000.0 +
                assessment.actual.fiberGrams.coerceAtMost(25.0) * 1_000.0 +
                if (viable) 100.0 else 0.0
            if (attemptScore > bestAttemptScore) {
                bestAttemptScore = attemptScore
                bestAttemptDiagnostic = diagnostic
            }
            val progressCandidate = CertifiedDayWitness(
                level = CertifiedDayLevel.VIABLE,
                seed = seed,
                day = WeekDay.MONDAY,
                meals = generated.meals,
                fingerprint = generated.meals.hashCode()
            )
            if (viable) considerProgressWitness(progressCandidate)
            if (viable && fruitMeals >= 2 && vegetableMeals >= 2 && assessment.actual.fiberGrams >= 25.0) {
                val candidate = progressCandidate.copy(level = CertifiedDayLevel.COMPLETE)
                if (isComplete(candidate, rules, foodsById, dishesById, recommendation, mealShares)) {
                    return CompleteDaySearchResult(candidate, diagnostic, progressCandidate)
                }
            }
        }

        bestProgressWitness?.let { progress ->
            CompleteDayWitnessRepair.find(
                progress,
                rules,
                foodsById,
                dishesById,
                recommendation,
                mealShares
            )?.let { return repairedResult(it) }
        }

        val rawDiagnostic = bestDiagnostic ?: bestAttemptDiagnostic
        val uiSafeDiagnostic = rawDiagnostic?.let { raw ->
            // Availability across distinct meals is a structural fact and can
            // justify an add-food action. Fiber in the best bounded attempt is
            // not a proof of fiber insufficiency: another composition may reach
            // 25 g (Ara is a real regression for exactly this distinction).
            // Keep the compatibility diagnostic non-actionable when coverage is
            // structurally available so the UI falls through to "search
            // inconclusive" rather than inventing a fiber shortage.
            if (availableFruitMeals >= 2 && availableVegetableMeals >= 2) {
                raw.copy(
                    fiberGrams = maxOf(raw.fiberGrams, 25.0),
                    viable = false,
                    limitingNutrient = null,
                    limitingDifference = null,
                    deficientNutrient = null,
                    deficientDifference = null
                )
            } else {
                raw.copy(viable = false)
            }
        }

        return CompleteDaySearchResult(
            null,
            uiSafeDiagnostic,
            bestProgressWitness
        )
    }

    private fun mealsContaining(
        meals: List<es.david.rumbo.model.PlannedMeal>,
        category: FoodCategory,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): Int = meals.count { meal ->
        val direct = meal.items.any { foodsById[it.foodId]?.category == category }
        val inDish = meal.dishes.any { plannedDish ->
            dishesById[plannedDish.dishId]?.ingredients?.any {
                foodsById[it.foodId]?.category == category
            } == true
        }
        direct || inDish
    }

    private fun completeCriteria(
        day: WeekDay,
        meals: List<es.david.rumbo.model.PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation
    ): Boolean {
        val assessment = MealPlanEvaluator.assessDay(day, meals, foodsById, dishesById, recommendation)
        if (!WeeklyMenuAcceptancePolicy.isDayAcceptable(assessment, meals.mapTo(mutableSetOf()) { it.type })) return false
        if (assessment.actual.fiberGrams < 25.0) return false
        return mealsContaining(meals, FoodCategory.VEGETABLE, foodsById, dishesById) >= 2 &&
            mealsContaining(meals, FoodCategory.FRUIT, foodsById, dishesById) >= 2
    }

}
