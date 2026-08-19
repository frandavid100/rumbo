package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.resolvedGrams
import es.david.rumbo.model.sanitizedDayAmounts
import kotlin.math.abs
import kotlin.math.round

/**
 * Deterministic bounded repair from a certified COMPLETE day to level 3.
 *
 * Every accepted intermediate state remains COMPLETE. The repair changes the
 * smallest local cause first: quantity, optional incoherent source, then an
 * already-available compatible companion. Broad generation remains a later
 * fallback and is never evidence of insufficiency.
 */
object CulinarilySatisfactoryWitnessRepair {
    private const val BEAM_WIDTH = 48
    private const val MAX_DEPTH = 7
    private const val MAX_COMPANIONS_PER_ISSUE = 8

    fun find(
        baseline: CertifiedDayWitness,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        portionContext: PortionContext = PortionContext.GENERAL_ADULT
    ): CertifiedDayWitness? {
        val complete = baseline.copy(level = CertifiedDayLevel.COMPLETE)
        if (!CertifiedDayWitnessEvaluator.isComplete(
                complete, rules, foodsById, dishesById, recommendation, mealShares
            )
        ) return null

        fun promoted(candidate: CertifiedDayWitness): CertifiedDayWitness? {
            val level3 = candidate.copy(
                level = CertifiedDayLevel.CULINARILY_SATISFACTORY,
                fingerprint = candidate.meals.hashCode()
            )
            return level3.takeIf {
                CulinarySatisfactionEvaluator.isCulinarilySatisfactory(
                    it, rules, foodsById, dishesById, recommendation, mealShares, portionContext
                )
            }
        }

        promoted(complete)?.let { return it }

        val activeRules = rules.filter {
            it.itemKind == PlannedItemKind.FOOD && it.isActive &&
                it.frequency != PlanningFrequency.NEVER &&
                foodsById[it.itemId]?.hasComparableNutrition() == true
        }
        var beam = listOf(complete)

        repeat(MAX_DEPTH) {
            val next = linkedMapOf<String, CertifiedDayWitness>()
            beam.forEach { state ->
                expand(
                    state,
                    activeRules,
                    foodsById,
                    dishesById,
                    recommendation,
                    mealShares,
                    portionContext
                ).forEach { variant ->
                    val accepted = optimizeAndKeepComplete(
                        variant,
                        rules,
                        foodsById,
                        dishesById,
                        recommendation,
                        mealShares
                    ) ?: return@forEach
                    promoted(accepted)?.let { return it }
                    val key = stateKey(accepted)
                    val previous = next[key]
                    if (previous == null || score(
                            accepted, foodsById, dishesById, recommendation, mealShares, portionContext
                        ) < score(
                            previous, foodsById, dishesById, recommendation, mealShares, portionContext
                        )
                    ) next[key] = accepted
                }
            }
            if (next.isEmpty()) return null
            beam = next.values.sortedBy {
                score(it, foodsById, dishesById, recommendation, mealShares, portionContext)
            }.take(BEAM_WIDTH)
        }
        return null
    }

    private fun expand(
        witness: CertifiedDayWitness,
        activeRules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        portionContext: PortionContext
    ): List<CertifiedDayWitness> {
        val evaluation = CulinarySatisfactionEvaluator.evaluateDay(
            witness.day,
            witness.meals,
            foodsById,
            dishesById,
            recommendation,
            mealShares,
            portionContext
        )
        if (evaluation.satisfactory) return emptyList()

        return buildList {
            evaluation.issues.take(8).forEach { issue ->
                val mealIndex = witness.meals.indexOfFirst { it.type == issue.mealType }
                if (mealIndex < 0) return@forEach
                val originalMeal = materialize(witness.meals[mealIndex], witness.day)
                val sourceIndex = issue.foodId?.let { id ->
                    originalMeal.items.indexOfFirst { it.foodId == id }.takeIf { it >= 0 }
                }

                when (issue.kind) {
                    CulinarySatisfactionIssueKind.QUANTITY_OUTSIDE_SATISFACTORY_RANGE -> {
                        val index = sourceIndex ?: return@forEach
                        val food = foodsById[originalMeal.items[index].foodId] ?: return@forEach
                        issue.roles.sortedBy { it.ordinal }.forEach { role ->
                            val policy = PortionPolicyResolver.resolve(
                                food,
                                role,
                                originalMeal.type,
                                recommendation,
                                mealShares,
                                portionContext
                            )
                            val items = originalMeal.items.toMutableList()
                            items[index] = satisfactoryItem(food.id, policy)
                            add(replaceMeal(witness, mealIndex, originalMeal.copy(items = items)))
                        }
                    }

                    CulinarySatisfactionIssueKind.SOFT_RELATION_UNSATISFIED -> {
                        val sourceRole = issue.roles.firstOrNull() ?: return@forEach
                        val targetRoles = CulinarySoftPolicy.preferredCompanions(sourceRole)
                        if (targetRoles.isEmpty()) return@forEach

                        // If the source is optional, removal is often the most
                        // natural fix (e.g. cooking oil in a fruit snack).
                        sourceIndex?.let { index ->
                            val sourceId = originalMeal.items[index].foodId
                            if (!isMandatory(sourceId, originalMeal.type, activeRules)) {
                                val items = originalMeal.items.toMutableList().also { it.removeAt(index) }
                                if (items.isNotEmpty() || originalMeal.dishes.isNotEmpty()) {
                                    add(replaceMeal(witness, mealIndex, originalMeal.copy(items = items)))
                                }

                                // Preserve nutritional contribution when possible by
                                // relocating an optional modifier to a meal where its
                                // preferred vehicle already exists. This is especially
                                // useful for oil inherited in a fruit snack.
                                val sourceItem = originalMeal.items[index]
                                val sourceAllowedMeals = activeRules
                                    .filter { it.itemId == sourceId }
                                    .flatMapTo(mutableSetOf()) { it.allowedMealTypes }
                                witness.meals.indices
                                    .filter { it != mealIndex }
                                    .forEach destinationLoop@ { destinationIndex ->
                                        val destination = materialize(
                                            witness.meals[destinationIndex], witness.day
                                        )
                                        if (destination.type !in sourceAllowedMeals) return@destinationLoop
                                        if (destination.items.any { it.foodId == sourceId }) return@destinationLoop
                                        val hasPreferredVehicle = destination.items.any { planned ->
                                            foodsById[planned.foodId]?.let(CulinaryPolicy::roles)
                                                ?.any(targetRoles::contains) == true
                                        } || destination.dishes.any { plannedDish ->
                                            dishesById[plannedDish.dishId]?.ingredients.orEmpty().any { ingredient ->
                                                foodsById[ingredient.foodId]?.let(CulinaryPolicy::roles)
                                                    ?.any(targetRoles::contains) == true
                                            }
                                        }
                                        if (!hasPreferredVehicle) return@destinationLoop

                                        val sourceWithout = originalMeal.copy(
                                            items = originalMeal.items.toMutableList().also {
                                                it.removeAt(index)
                                            }
                                        )
                                        val maximum = maximumItems(destination.type)
                                        if (destination.items.size + destination.dishes.size < maximum) {
                                            val meals = witness.meals.toMutableList()
                                            meals[mealIndex] = sourceWithout
                                            meals[destinationIndex] = destination.copy(
                                                items = destination.items + sourceItem
                                            )
                                            add(witness.copy(meals = meals, fingerprint = meals.hashCode()))
                                        } else {
                                            destination.items.indices.forEach replacementLoop@ { replaceIndex ->
                                                val replacedId = destination.items[replaceIndex].foodId
                                                if (isMandatory(
                                                        replacedId, destination.type, activeRules
                                                    )
                                                ) return@replacementLoop
                                                val destinationItems = destination.items.toMutableList().also {
                                                    it[replaceIndex] = sourceItem
                                                }
                                                val meals = witness.meals.toMutableList()
                                                meals[mealIndex] = sourceWithout
                                                meals[destinationIndex] = destination.copy(items = destinationItems)
                                                add(witness.copy(meals = meals, fingerprint = meals.hashCode()))
                                            }
                                        }
                                    }
                            }
                        }

                        val existingIds = originalMeal.items.mapTo(mutableSetOf()) { it.foodId }
                        val candidates = activeRules.asSequence()
                            .filter { originalMeal.type in it.allowedMealTypes && it.itemId !in existingIds }
                            .mapNotNull { rule ->
                                val food = foodsById[rule.itemId] ?: return@mapNotNull null
                                val role = CulinaryPolicy.roles(food)
                                    .intersect(targetRoles)
                                    .minByOrNull { it.ordinal } ?: return@mapNotNull null
                                Triple(rule, food, role)
                            }
                            .distinctBy { it.first.itemId }
                            .sortedWith(
                                compareByDescending<Triple<PlanningRule, Food, CulinaryRole>> {
                                    it.third.let { role ->
                                        originalMeal.type in CulinaryPolicy.policy(role).suggestedMealTypes
                                    }
                                }.thenByDescending { it.second.portionBasisGrams != null }
                                    .thenBy { it.first.itemId }
                            )
                            .take(MAX_COMPANIONS_PER_ISSUE)
                            .toList()

                        candidates.forEach { (_, food, role) ->
                            val policy = PortionPolicyResolver.resolve(
                                food,
                                role,
                                originalMeal.type,
                                recommendation,
                                mealShares,
                                portionContext
                            )
                            val added = satisfactoryItem(food.id, policy)
                            val maxItems = maximumItems(originalMeal.type)
                            if (originalMeal.items.size + originalMeal.dishes.size < maxItems) {
                                add(
                                    replaceMeal(
                                        witness,
                                        mealIndex,
                                        originalMeal.copy(items = originalMeal.items + added)
                                    )
                                )
                            } else {
                                originalMeal.items.indices.forEach { replaceIndex ->
                                    val replaced = originalMeal.items[replaceIndex].foodId
                                    if (replaced == issue.foodId || isMandatory(
                                            replaced, originalMeal.type, activeRules
                                        )
                                    ) return@forEach
                                    val items = originalMeal.items.toMutableList().also {
                                        it[replaceIndex] = added
                                    }
                                    add(replaceMeal(witness, mealIndex, originalMeal.copy(items = items)))
                                }
                            }
                        }
                    }

                    CulinarySatisfactionIssueKind.ROLE_UNRESOLVED -> {
                        // Legacy/custom roleless foods cannot be made level-3
                        // satisfactory by inventing a role. An optional one may
                        // disappear if COMPLETE survives; mandatory ones remain a
                        // real diagnostic for the user/catalogue.
                        sourceIndex?.let { index ->
                            val sourceId = originalMeal.items[index].foodId
                            if (!isMandatory(sourceId, originalMeal.type, activeRules)) {
                                val items = originalMeal.items.toMutableList().also { it.removeAt(index) }
                                if (items.isNotEmpty() || originalMeal.dishes.isNotEmpty()) {
                                    add(replaceMeal(witness, mealIndex, originalMeal.copy(items = items)))
                                }
                            }
                        }
                    }

                    CulinarySatisfactionIssueKind.HARD_ROLE_ASSIGNMENT_INVALID -> Unit
                }
            }
        }.distinctBy(::stateKey)
    }

    private fun optimizeAndKeepComplete(
        witness: CertifiedDayWitness,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): CertifiedDayWitness? {
        val optimized = runCatching {
            MealQuantityOptimizer.optimize(
                meals = witness.meals,
                foodsById = foodsById,
                dishesById = dishesById,
                recommendation = recommendation,
                days = setOf(witness.day),
                mealShares = mealShares
            ).meals
        }.getOrNull() ?: return null
        val candidate = witness.copy(
            level = CertifiedDayLevel.COMPLETE,
            meals = optimized,
            fingerprint = optimized.hashCode()
        )
        if (!candidate.isStructurallyValid()) return null
        return candidate.takeIf {
            CertifiedDayWitnessEvaluator.isComplete(
                it, rules, foodsById, dishesById, recommendation, mealShares
            )
        }
    }

    private fun score(
        witness: CertifiedDayWitness,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        portionContext: PortionContext
    ): Double {
        val culinary = CulinarySatisfactionEvaluator.evaluateDay(
            witness.day,
            witness.meals,
            foodsById,
            dishesById,
            recommendation,
            mealShares,
            portionContext
        )
        val issueCost = culinary.issues.sumOf { issue ->
            when (issue.kind) {
                CulinarySatisfactionIssueKind.HARD_ROLE_ASSIGNMENT_INVALID -> 1_000_000.0
                CulinarySatisfactionIssueKind.ROLE_UNRESOLVED -> 500_000.0
                CulinarySatisfactionIssueKind.SOFT_RELATION_UNSATISFIED -> 100_000.0
                CulinarySatisfactionIssueKind.QUANTITY_OUTSIDE_SATISFACTORY_RANGE -> 10_000.0
            }
        }
        val assessment = MealPlanEvaluator.assessDay(
            witness.day, witness.meals, foodsById, dishesById, recommendation
        )
        val macroCost = assessment.evaluations.sumOf { evaluation ->
            abs(evaluation.difference) / evaluation.target.coerceAtLeast(1.0)
        } * 100.0
        return issueCost + macroCost
    }

    private fun materialize(meal: PlannedMeal, day: es.david.rumbo.model.WeekDay): PlannedMeal =
        meal.copy(
            items = meal.items.map { item -> item.copy(grams = meal.resolvedGrams(item, day)) },
            dishes = meal.dishes.map { item -> item.copy(grams = meal.resolvedGrams(item, day)) },
            dayAmounts = emptyList()
        ).sanitizedDayAmounts()

    private fun replaceMeal(
        witness: CertifiedDayWitness,
        index: Int,
        meal: PlannedMeal
    ): CertifiedDayWitness {
        val meals = witness.meals.toMutableList().also { it[index] = meal.copy(dayAmounts = emptyList()) }
        return witness.copy(meals = meals, fingerprint = meals.hashCode())
    }

    private fun satisfactoryItem(foodId: Long, policy: ResolvedPortionPolicy): PlannedFood =
        PlannedFood(
            foodId = foodId,
            grams = policy.effectivePreferred.coerceIn(
                policy.satisfactoryMinimum, policy.satisfactoryMaximum
            ),
            adjustable = true,
            minimumGrams = policy.satisfactoryMinimum,
            maximumGrams = policy.satisfactoryMaximum
        )

    private fun isMandatory(
        foodId: Long,
        mealType: MealType,
        activeRules: List<PlanningRule>
    ): Boolean = activeRules.any {
        it.itemId == foodId && it.frequency == PlanningFrequency.ALWAYS && mealType in it.allowedMealTypes
    }

    private fun maximumItems(mealType: MealType): Int = when (mealType) {
        MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK -> 3
        else -> 4
    }

    private fun stateKey(witness: CertifiedDayWitness): String = witness.meals
        .sortedBy { it.type.ordinal }
        .joinToString("|") { meal ->
            val foods = meal.items.sortedBy { it.foodId }.joinToString(",") { item ->
                val grams = meal.resolvedGrams(item, witness.day)
                "${item.foodId}@${round(grams * 10.0) / 10.0}:${round(item.minimumGrams * 10.0) / 10.0}-${round(item.maximumGrams * 10.0) / 10.0}"
            }
            val dishes = meal.dishes.sortedBy { it.dishId }.joinToString(",") { item ->
                "${item.dishId}@${round(meal.resolvedGrams(item, witness.day) * 10.0) / 10.0}"
            }
            "${meal.type.name}:f[$foods]:d[$dishes]"
        }
}
