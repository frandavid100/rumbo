package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import kotlin.math.pow

/**
 * Deterministic food-composition fallback for level 3.
 *
 * The normal path still repairs the persisted COMPLETE witness. This search is
 * deliberately independent of the weekly generator: it enumerates small,
 * structurally satisfactory meal compositions, gives every selected occurrence
 * satisfactory quantity bounds, combines the best meal candidates with a
 * bounded beam and only then invokes the real quantity optimiser. Candidate
 * ranking uses the whole attainable nutrient interval, not just preferred grams:
 * a composition is retained when the target can be reached anywhere inside its
 * satisfactory ranges.
 *
 * Dishes are not expanded here yet. That makes failure SEARCH_INCONCLUSIVE; it
 * never becomes evidence that the repertoire is insufficient.
 */
object CulinaryLevel3CompositionSearch {
    private const val MAX_MEAL_CANDIDATES_PER_BUCKET = 24
    private const val MAX_ROLE_ASSIGNMENTS_PER_COMBINATION = 4
    private const val BEAM_PER_COVERAGE_BUCKET = 24
    private const val MAX_FINAL_OPTIMIZATIONS = 64

    private data class Vector(
        val calories: Double = 0.0,
        val protein: Double = 0.0,
        val carbohydrates: Double = 0.0,
        val fat: Double = 0.0,
        val fiber: Double = 0.0
    ) {
        operator fun plus(other: Vector) = Vector(
            calories + other.calories,
            protein + other.protein,
            carbohydrates + other.carbohydrates,
            fat + other.fat,
            fiber + other.fiber
        )
    }

    private data class VectorRange(
        val minimum: Vector = Vector(),
        val maximum: Vector = Vector()
    ) {
        operator fun plus(other: VectorRange) = VectorRange(
            minimum = minimum + other.minimum,
            maximum = maximum + other.maximum
        )
    }

    private data class MealCandidate(
        val meal: PlannedMeal,
        val preferredVector: Vector,
        val attainable: VectorRange,
        val fruit: Boolean,
        val vegetable: Boolean,
        val rolesByFood: Map<Long, List<CulinaryRole>>
    )

    private data class DayState(
        val meals: List<PlannedMeal> = emptyList(),
        val preferredVector: Vector = Vector(),
        val attainable: VectorRange = VectorRange(),
        val fruitMeals: Int = 0,
        val vegetableMeals: Int = 0,
        val processedShare: Double = 0.0,
        val rolesByFood: Map<Long, List<CulinaryRole>> = emptyMap()
    )

    fun find(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        portionContext: PortionContext = PortionContext.GENERAL_ADULT
    ): CertifiedDayWitness? {
        val constraints = MenuConstraintModel.fromLegacyData(rules, foodsById, mealShares)
        if (constraints.structuralViolations.isNotEmpty()) return null

        val activeFoodRules = constraints.activeRules.filter {
            it.itemKind == PlannedItemKind.FOOD &&
                it.isActive &&
                it.frequency != PlanningFrequency.NEVER &&
                foodsById[it.itemId]?.hasComparableNutrition() == true
        }
        val mealTypes = MealType.entries.filter { it in constraints.activeMealTypes }
        if (mealTypes.isEmpty()) return null

        val candidatesByMeal = mealTypes.associateWith { mealType ->
            mealCandidates(
                mealType,
                activeFoodRules,
                foodsById,
                recommendation,
                mealShares,
                portionContext
            )
        }
        if (candidatesByMeal.values.any { it.isEmpty() }) return null

        var beam = listOf(DayState())
        mealTypes.forEach { mealType ->
            val share = mealShares[mealType] ?: 0.0
            val expanded = buildList {
                beam.forEach { state ->
                    candidatesByMeal.getValue(mealType).forEach candidateLoop@ { candidate ->
                        val combinedRoles = mergeRoles(state.rolesByFood, candidate.rolesByFood)
                        if (combinedRoles.any { (_, roles) ->
                                CulinarySoftPolicy.maximumDailyOccurrences(roles)
                                    ?.let { roles.size > it } == true
                            }
                        ) return@candidateLoop
                        add(
                            DayState(
                                meals = state.meals + candidate.meal,
                                preferredVector = state.preferredVector + candidate.preferredVector,
                                attainable = state.attainable + candidate.attainable,
                                fruitMeals = state.fruitMeals + if (candidate.fruit) 1 else 0,
                                vegetableMeals = state.vegetableMeals + if (candidate.vegetable) 1 else 0,
                                processedShare = state.processedShare + share,
                                rolesByFood = combinedRoles
                            )
                        )
                    }
                }
            }
            beam = expanded
                .groupBy { it.fruitMeals.coerceAtMost(2) to it.vegetableMeals.coerceAtMost(2) }
                .values
                .flatMap { bucket ->
                    bucket.sortedWith(
                        compareBy<DayState> { partialRangeScore(it, recommendation) }
                            .thenBy { preferredScore(it.preferredVector, recommendation, it.processedShare) }
                    ).take(BEAM_PER_COVERAGE_BUCKET)
                }
                .sortedBy { partialRangeScore(it, recommendation) }
        }

        val finals = beam.sortedWith(
            compareBy<DayState> { finalPreScore(it, recommendation) }
                .thenBy { preferredScore(it.preferredVector, recommendation, 1.0) }
        ).take(MAX_FINAL_OPTIMIZATIONS)

        finals.forEachIndexed { index, state ->
            if (state.fruitMeals < 2 || state.vegetableMeals < 2) return@forEachIndexed
            val optimized = runCatching {
                MealQuantityOptimizer.optimize(
                    meals = state.meals,
                    foodsById = foodsById,
                    dishesById = dishesById,
                    recommendation = recommendation,
                    days = setOf(WeekDay.MONDAY),
                    mealShares = mealShares
                ).meals
            }.getOrNull() ?: return@forEachIndexed
            val complete = CertifiedDayWitness(
                level = CertifiedDayLevel.COMPLETE,
                seed = 30_001L + index,
                day = WeekDay.MONDAY,
                meals = optimized,
                fingerprint = optimized.hashCode()
            )
            if (!CertifiedDayWitnessEvaluator.isComplete(
                    complete, rules, foodsById, dishesById, recommendation, mealShares
                )
            ) return@forEachIndexed
            val level3 = complete.copy(level = CertifiedDayLevel.CULINARILY_SATISFACTORY)
            if (CulinarySatisfactionEvaluator.isCulinarilySatisfactory(
                    level3,
                    rules,
                    foodsById,
                    dishesById,
                    recommendation,
                    mealShares,
                    portionContext
                )
            ) return level3
        }
        return null
    }

    private fun mealCandidates(
        mealType: MealType,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        portionContext: PortionContext
    ): List<MealCandidate> {
        val ruleByFood = rules.filter { mealType in it.allowedMealTypes }
            .groupBy { it.itemId }
        val foods = ruleByFood.keys.mapNotNull(foodsById::get)
            .distinctBy { it.id }
            .sortedBy { it.id }
        val mandatory = ruleByFood.filterValues { entries ->
            entries.any { it.frequency == PlanningFrequency.ALWAYS }
        }.keys
        val maximumItems = when (mealType) {
            MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK -> 3
            else -> 4
        }
        if (mandatory.size > maximumItems) return emptyList()

        val optional = foods.filterNot { it.id in mandatory }
        val mandatoryFoods = foods.filter { it.id in mandatory }
        val raw = mutableListOf<MealCandidate>()
        for (targetSize in maxOf(1, mandatoryFoods.size)..maximumItems) {
            val optionalCount = targetSize - mandatoryFoods.size
            if (optionalCount < 0 || optionalCount > optional.size) continue
            combinations(optional, optionalCount).forEach { chosenOptional ->
                val chosen = (mandatoryFoods + chosenOptional).sortedBy { it.id }
                roleAssignments(chosen, mealType).take(MAX_ROLE_ASSIGNMENTS_PER_COMBINATION)
                    .forEach { roles ->
                        val items = chosen.indices.map { index ->
                            val food = chosen[index]
                            val role = roles[index]
                            val policy = PortionPolicyResolver.resolve(
                                food,
                                role,
                                mealType,
                                recommendation,
                                mealShares,
                                portionContext
                            )
                            PlannedFood(
                                foodId = food.id,
                                grams = policy.effectivePreferred,
                                adjustable = true,
                                minimumGrams = policy.satisfactoryMinimum,
                                maximumGrams = policy.satisfactoryMaximum
                            )
                        }
                        val meal = PlannedMeal(
                            id = 31_000L + mealType.ordinal * 1_000L + raw.size,
                            type = mealType,
                            days = setOf(WeekDay.MONDAY),
                            items = items
                        )
                        raw += MealCandidate(
                            meal = meal,
                            preferredVector = vector(chosen, items) { it.grams },
                            attainable = VectorRange(
                                minimum = vector(chosen, items) { it.minimumGrams },
                                maximum = vector(chosen, items) { it.maximumGrams }
                            ),
                            fruit = chosen.any { it.category == FoodCategory.FRUIT },
                            vegetable = chosen.any { it.category == FoodCategory.VEGETABLE },
                            rolesByFood = chosen.indices.groupBy(
                                keySelector = { chosen[it].id },
                                valueTransform = { roles[it] }
                            )
                        )
                    }
            }
        }

        val share = mealShares[mealType] ?: 0.0
        return raw
            .distinctBy { candidate ->
                candidate.meal.items.joinToString(",") { "${it.foodId}@${it.minimumGrams}-${it.maximumGrams}" }
            }
            .groupBy { it.fruit to it.vegetable }
            .values
            .flatMap { bucket ->
                bucket.sortedWith(
                    compareBy<MealCandidate> { rangeScore(it.attainable, recommendation, share) }
                        .thenBy { preferredScore(it.preferredVector, recommendation, share) }
                ).take(MAX_MEAL_CANDIDATES_PER_BUCKET)
            }
            .sortedBy { rangeScore(it.attainable, recommendation, share) }
    }

    private fun roleAssignments(
        foods: List<Food>,
        mealType: MealType
    ): Sequence<List<CulinaryRole>> = sequence {
        val choices = foods.map { food ->
            CulinaryPolicy.roles(food).filter { CulinaryPolicy.isAllowedForMeal(it, mealType) }.sortedWith(
                compareByDescending<CulinaryRole> {
                    mealType in CulinaryPolicy.policy(it).suggestedMealTypes
                }.thenBy { it.ordinal }
            )
        }
        if (choices.any { it.isEmpty() }) return@sequence
        val chosen = ArrayList<CulinaryRole>(foods.size)

        suspend fun SequenceScope<List<CulinaryRole>>.visit(index: Int) {
            if (index == choices.size) {
                val snapshot = chosen.toList()
                if (!CulinaryPolicy.hasValidRoleAssignment(snapshot.map { setOf(it) })) return
                if (CulinarySoftPolicy.missingPreferences(snapshot).isNotEmpty()) return
                yield(snapshot)
                return
            }
            choices[index].forEach { role ->
                val max = CulinaryPolicy.policy(role).maxPerMeal
                if (max != null && chosen.count { it == role } >= max) return@forEach
                chosen += role
                visit(index + 1)
                chosen.removeAt(chosen.lastIndex)
            }
        }
        visit(0)
    }

    private fun mergeRoles(
        first: Map<Long, List<CulinaryRole>>,
        second: Map<Long, List<CulinaryRole>>
    ): Map<Long, List<CulinaryRole>> = buildMap {
        first.forEach { (foodId, roles) -> put(foodId, roles) }
        second.forEach { (foodId, roles) -> put(foodId, get(foodId).orEmpty() + roles) }
    }

    private fun combinations(values: List<Food>, count: Int): Sequence<List<Food>> = sequence {
        if (count == 0) {
            yield(emptyList())
            return@sequence
        }
        val chosen = ArrayList<Food>(count)
        suspend fun SequenceScope<List<Food>>.visit(start: Int) {
            if (chosen.size == count) {
                yield(chosen.toList())
                return
            }
            val remaining = count - chosen.size
            val lastStart = values.size - remaining
            for (index in start..lastStart) {
                chosen += values[index]
                visit(index + 1)
                chosen.removeAt(chosen.lastIndex)
            }
        }
        if (count <= values.size) visit(0)
    }

    private fun vector(
        foods: List<Food>,
        items: List<PlannedFood>,
        grams: (PlannedFood) -> Double
    ): Vector = foods.indices.fold(Vector()) { total, index ->
        val food = foods[index]
        val factor = grams(items[index]) / 100.0
        total + Vector(
            calories = (food.calories ?: 0.0) * factor,
            protein = (food.proteinGrams ?: 0.0) * factor,
            carbohydrates = (food.carbohydrateGrams ?: 0.0) * factor,
            fat = (food.fatGrams ?: 0.0) * factor,
            fiber = (food.fiberGrams ?: 0.0) * factor
        )
    }

    private fun preferredScore(
        vector: Vector,
        recommendation: Recommendation,
        share: Double
    ): Double =
        relativeSquare(vector.calories, recommendation.calories * share) * 1.25 +
            relativeSquare(vector.protein, recommendation.proteinGrams * share) * 1.15 +
            relativeSquare(vector.carbohydrates, recommendation.carbohydrateGrams * share) +
            relativeSquare(vector.fat, recommendation.fatGrams * share)

    private fun rangeScore(
        range: VectorRange,
        recommendation: Recommendation,
        share: Double
    ): Double =
        intervalSquare(range.minimum.calories, range.maximum.calories, recommendation.calories * share) * 1.25 +
            intervalSquare(range.minimum.protein, range.maximum.protein, recommendation.proteinGrams * share) * 1.15 +
            intervalSquare(range.minimum.carbohydrates, range.maximum.carbohydrates, recommendation.carbohydrateGrams * share) +
            intervalSquare(range.minimum.fat, range.maximum.fat, recommendation.fatGrams * share)

    private fun partialRangeScore(state: DayState, recommendation: Recommendation): Double {
        val share = state.processedShare.coerceAtLeast(0.01)
        return rangeScore(state.attainable, recommendation, share) +
            (2 - state.fruitMeals.coerceAtMost(2)) * 0.04 +
            (2 - state.vegetableMeals.coerceAtMost(2)) * 0.04
    }

    private fun finalPreScore(state: DayState, recommendation: Recommendation): Double {
        val coveragePenalty = (2 - state.fruitMeals.coerceAtMost(2)) * 100.0 +
            (2 - state.vegetableMeals.coerceAtMost(2)) * 100.0
        val fiberPenalty = if (state.attainable.maximum.fiber >= 25.0) 0.0
            else ((25.0 - state.attainable.maximum.fiber) / 25.0) * 10.0
        return rangeScore(state.attainable, recommendation, 1.0) + coveragePenalty + fiberPenalty
    }

    private fun intervalSquare(minimum: Double, maximum: Double, target: Double): Double {
        if (target <= 0.0) return if (minimum <= 0.0) 0.0 else minimum.pow(2)
        val distance = when {
            target < minimum -> minimum - target
            target > maximum -> target - maximum
            else -> 0.0
        }
        return (distance / target).pow(2)
    }

    private fun relativeSquare(actual: Double, target: Double): Double {
        if (target <= 0.0) return if (actual == 0.0) 0.0 else actual.pow(2)
        return ((actual - target) / target).pow(2)
    }
}
