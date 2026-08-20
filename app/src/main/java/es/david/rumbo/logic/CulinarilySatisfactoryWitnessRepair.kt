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
 * The initial and returned witnesses are COMPLETE. Intermediate states may be
 * nutritionally incomplete: fixing a culinary quantity can temporarily move a
 * macro outside tolerance, and a later substitution can restore it. Requiring
 * every intermediate step to remain COMPLETE makes those valid multi-step
 * repairs unreachable. Broad generation remains a later fallback and is never
 * evidence of insufficiency.
 */
object CulinarilySatisfactoryWitnessRepair {
    private const val BEAM_WIDTH = 48
    private const val MAX_DEPTH = 8
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
            if (!CertifiedDayWitnessEvaluator.isComplete(
                    candidate.copy(level = CertifiedDayLevel.COMPLETE),
                    rules,
                    foodsById,
                    dishesById,
                    recommendation,
                    mealShares
                )
            ) return null
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
                    val accepted = optimizeCandidate(
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
            normalizeQuantityIssues(
                witness,
                evaluation,
                foodsById,
                recommendation,
                mealShares,
                portionContext
            )?.let(::add)

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

                        sourceIndex?.let { index ->
                            val sourceId = originalMeal.items[index].foodId
                            if (!isMandatory(sourceId, originalMeal.type, activeRules)) {
                                val items = originalMeal.items.toMutableList().also { it.removeAt(index) }
                                if (items.isNotEmpty() || originalMeal.dishes.isNotEmpty()) {
                                    add(replaceMeal(witness, mealIndex, originalMeal.copy(items = items)))
                                }

                                // Preserve the contribution of an optional modifier by
                                // relocating it to a meal that already has a valid vehicle.
                                // If the same food is already there, merge the two
                                // occurrences and rebind its bounds to a satisfactory role
                                // (e.g. oil can become SAUCE_DRESSING instead of exceeding
                                // the 15 g COOKING_MEDIUM interval).
                                val sourceItem = originalMeal.items[index]
                                val sourceFood = foodsById[sourceId]
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
                                        val presentRoles = rolesPresent(
                                            destination, sourceId, foodsById, dishesById
                                        )
                                        if (targetRoles.none(presentRoles::contains)) return@destinationLoop

                                        val sourceWithout = originalMeal.copy(
                                            items = originalMeal.items.toMutableList().also {
                                                it.removeAt(index)
                                            }
                                        )
                                        val existingIndex = destination.items.indexOfFirst {
                                            it.foodId == sourceId
                                        }
                                        if (existingIndex >= 0 && sourceFood != null) {
                                            val existing = destination.items[existingIndex]
                                            val combinedGrams = existing.grams + sourceItem.grams
                                            val merged = satisfactoryItemForExactGrams(
                                                food = sourceFood,
                                                grams = combinedGrams,
                                                mealType = destination.type,
                                                presentRoles = presentRoles,
                                                recommendation = recommendation,
                                                mealShares = mealShares,
                                                portionContext = portionContext
                                            )
                                            if (merged != null) {
                                                val destinationItems = destination.items.toMutableList().also {
                                                    it[existingIndex] = merged
                                                }
                                                val meals = witness.meals.toMutableList()
                                                meals[mealIndex] = sourceWithout
                                                meals[destinationIndex] = destination.copy(
                                                    items = destinationItems
                                                )
                                                add(witness.copy(
                                                    meals = meals,
                                                    fingerprint = meals.hashCode()
                                                ))
                                            }
                                            return@destinationLoop
                                        }

                                        val relocated = sourceFood?.let {
                                            satisfactoryItemForExactGrams(
                                                food = it,
                                                grams = sourceItem.grams,
                                                mealType = destination.type,
                                                presentRoles = presentRoles,
                                                recommendation = recommendation,
                                                mealShares = mealShares,
                                                portionContext = portionContext
                                            )
                                        } ?: sourceItem
                                        val maximum = maximumItems(destination.type)
                                        if (destination.items.size + destination.dishes.size < maximum) {
                                            val meals = witness.meals.toMutableList()
                                            meals[mealIndex] = sourceWithout
                                            meals[destinationIndex] = destination.copy(
                                                items = destination.items + relocated
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
                                                    it[replaceIndex] = relocated
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
                                originalMeal.items.indices.forEach replacementLoop@ { replaceIndex ->
                                    val replaced = originalMeal.items[replaceIndex].foodId
                                    if (replaced == issue.foodId || isMandatory(
                                            replaced, originalMeal.type, activeRules
                                        )
                                    ) return@replacementLoop
                                    val items = originalMeal.items.toMutableList().also {
                                        it[replaceIndex] = added
                                    }
                                    add(replaceMeal(witness, mealIndex, originalMeal.copy(items = items)))
                                }
                            }
                        }
                    }
                    CulinarySatisfactionIssueKind.DAILY_REPETITION_DISCOURAGED -> {
                        val index = sourceIndex ?: return@forEach
                        val sourceId = originalMeal.items[index].foodId
                        val sourceFood = foodsById[sourceId] ?: return@forEach
                        val sourceRoles = CulinaryPolicy.roles(sourceFood)
                        val occupiedConcepts = witness.meals.flatMap { meal ->
                            materialize(meal, witness.day).items.mapNotNull { item ->
                                if (meal.type == originalMeal.type && item.foodId == sourceId) null
                                else foodsById[item.foodId]?.let(::repetitionConcept)
                            }
                        }.toSet()

                        // Removing an optional repeated occurrence is the smallest
                        // valid repair when the meal still has another component.
                        if (!isMandatory(sourceId, originalMeal.type, activeRules) &&
                            (originalMeal.items.size > 1 || originalMeal.dishes.isNotEmpty())
                        ) {
                            val items = originalMeal.items.toMutableList().also { it.removeAt(index) }
                            add(replaceMeal(witness, mealIndex, originalMeal.copy(items = items)))
                        }

                        // Otherwise replace this occurrence with an allowed food
                        // that can perform the same culinary job and whose family
                        // is not already used elsewhere in the day. Names and
                        // brands never participate in this decision.
                        activeRules.asSequence()
                            .filter {
                                originalMeal.type in it.allowedMealTypes &&
                                    it.itemId != sourceId &&
                                    originalMeal.items.none { item -> item.foodId == it.itemId }
                            }
                            .mapNotNull { rule ->
                                val food = foodsById[rule.itemId] ?: return@mapNotNull null
                                if (repetitionConcept(food) in occupiedConcepts) return@mapNotNull null
                                val role = CulinaryPolicy.roles(food)
                                    .intersect(sourceRoles)
                                    .filter { CulinaryPolicy.isAllowedForMeal(it, originalMeal.type) }
                                    .minByOrNull { it.ordinal } ?: return@mapNotNull null
                                Triple(rule, food, role)
                            }
                            .distinctBy { it.first.itemId }
                            .sortedWith(
                                compareByDescending<Triple<PlanningRule, Food, CulinaryRole>> {
                                    it.second.category == sourceFood.category
                                }.thenByDescending {
                                    it.third in issue.roles
                                }.thenBy { it.first.itemId }
                            )
                            .take(MAX_COMPANIONS_PER_ISSUE)
                            .forEach { (_, food, role) ->
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

                    CulinarySatisfactionIssueKind.ROLE_UNRESOLVED -> {
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

    private fun normalizeQuantityIssues(
        witness: CertifiedDayWitness,
        evaluation: CulinaryDaySatisfaction,
        foodsById: Map<Long, Food>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        portionContext: PortionContext
    ): CertifiedDayWitness? {
        val quantityIssues = evaluation.issues.filter {
            it.kind == CulinarySatisfactionIssueKind.QUANTITY_OUTSIDE_SATISFACTORY_RANGE &&
                it.foodId != null
        }
        if (quantityIssues.size < 2) return null

        val meals = witness.meals.map { materialize(it, witness.day) }.toMutableList()
        var changed = false
        quantityIssues.forEach { issue ->
            val mealIndex = meals.indexOfFirst { it.type == issue.mealType }
            if (mealIndex < 0) return@forEach
            val meal = meals[mealIndex]
            val itemIndex = meal.items.indexOfFirst { it.foodId == issue.foodId }
            if (itemIndex < 0) return@forEach
            val food = foodsById[meal.items[itemIndex].foodId] ?: return@forEach
            val grams = meal.items[itemIndex].grams
            val chosen = issue.roles.map { role ->
                role to PortionPolicyResolver.resolve(
                    food,
                    role,
                    meal.type,
                    recommendation,
                    mealShares,
                    portionContext
                )
            }.minWithOrNull(
                compareBy<Pair<CulinaryRole, ResolvedPortionPolicy>> {
                    distanceFromRange(grams, it.second)
                }.thenByDescending {
                    meal.type in CulinaryPolicy.policy(it.first).suggestedMealTypes
                }.thenBy { it.first.ordinal }
            ) ?: return@forEach
            val items = meal.items.toMutableList()
            items[itemIndex] = satisfactoryItem(food.id, chosen.second)
            meals[mealIndex] = meal.copy(items = items, dayAmounts = emptyList())
            changed = true
        }
        return witness.copy(meals = meals, fingerprint = meals.hashCode()).takeIf { changed }
    }

    private fun distanceFromRange(grams: Double, policy: ResolvedPortionPolicy): Double = when {
        grams < policy.satisfactoryMinimum -> policy.satisfactoryMinimum - grams
        grams > policy.satisfactoryMaximum -> grams - policy.satisfactoryMaximum
        else -> 0.0
    }

    private fun repetitionConcept(food: Food): String =
        food.family?.trim()?.lowercase()?.takeIf { it.isNotEmpty() } ?: "food:${food.id}"

    private fun rolesPresent(
        meal: PlannedMeal,
        excludingFoodId: Long,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): Set<CulinaryRole> = buildSet {
        meal.items.filterNot { it.foodId == excludingFoodId }.forEach { planned ->
            foodsById[planned.foodId]?.let(CulinaryPolicy::roles)?.let(::addAll)
        }
        meal.dishes.forEach { plannedDish ->
            dishesById[plannedDish.dishId]?.ingredients.orEmpty().forEach { ingredient ->
                foodsById[ingredient.foodId]?.let(CulinaryPolicy::roles)?.let(::addAll)
            }
        }
    }

    private fun satisfactoryItemForExactGrams(
        food: Food,
        grams: Double,
        mealType: MealType,
        presentRoles: Set<CulinaryRole>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        portionContext: PortionContext
    ): PlannedFood? = CulinaryPolicy.roles(food)
        .sortedBy { it.ordinal }
        .mapNotNull { role ->
            val companions = CulinarySoftPolicy.preferredCompanions(role)
            if (companions.isNotEmpty() && companions.none(presentRoles::contains)) {
                return@mapNotNull null
            }
            val policy = PortionPolicyResolver.resolve(
                food,
                role,
                mealType,
                recommendation,
                mealShares,
                portionContext
            )
            policy.takeIf { it.isSatisfactory(grams) }
        }
        .firstOrNull()
        ?.let { policy ->
            PlannedFood(
                foodId = food.id,
                grams = grams,
                adjustable = true,
                minimumGrams = policy.satisfactoryMinimum,
                maximumGrams = policy.satisfactoryMaximum
            )
        }

    private fun optimizeCandidate(
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
        return candidate.takeIf { it.isStructurallyValid() }
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
                CulinarySatisfactionIssueKind.DAILY_REPETITION_DISCOURAGED -> 50_000.0
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
