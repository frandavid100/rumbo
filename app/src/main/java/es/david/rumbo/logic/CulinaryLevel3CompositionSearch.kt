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
import kotlin.math.floor
import kotlin.math.pow

/**
 * Deterministic food-composition fallback for level 3.
 *
 * Whole-day nutrition is the acceptance criterion. Meal shares contextualize
 * sensible portion ranges, but they must not prune a composition merely because
 * one meal carries more protein/carbohydrate/fat than its nominal share.
 *
 * We therefore preserve candidates by culinary role structure and by nutrient
 * capability (especially fibre/protein), then rank partial days by what the
 * complete remaining day can still reach. This avoids the false negative seen
 * when Ara's high-fibre tomato/rice/protein composition was displaced by many
 * locally prettier lunch combinations.
 *
 * Dishes are not expanded here yet. Failure remains SEARCH_INCONCLUSIVE and is
 * never evidence that the repertoire is insufficient.
 */
object CulinaryLevel3CompositionSearch {
    private const val MAX_PER_ROLE_SIGNATURE = 12
    private const val MAX_PER_COVERAGE_BUCKET = 96
    private const val MAX_ROLE_ASSIGNMENTS_PER_COMBINATION = 6
    private const val BEAM_PER_STATE_BUCKET = 28
    private const val MAX_FINAL_OPTIMIZATIONS = 72

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
        val roleSignature: String
    )

    private data class DayState(
        val meals: List<PlannedMeal> = emptyList(),
        val preferredVector: Vector = Vector(),
        val attainable: VectorRange = VectorRange(),
        val fruitMeals: Int = 0,
        val vegetableMeals: Int = 0
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

        val suffixEnvelope = Array(mealTypes.size + 1) { VectorRange() }
        val suffixFruitPossible = IntArray(mealTypes.size + 1)
        val suffixVegetablePossible = IntArray(mealTypes.size + 1)
        for (index in mealTypes.lastIndex downTo 0) {
            val candidates = candidatesByMeal.getValue(mealTypes[index])
            suffixEnvelope[index] = envelope(candidates) + suffixEnvelope[index + 1]
            suffixFruitPossible[index] = suffixFruitPossible[index + 1] +
                if (candidates.any { it.fruit }) 1 else 0
            suffixVegetablePossible[index] = suffixVegetablePossible[index + 1] +
                if (candidates.any { it.vegetable }) 1 else 0
        }

        var beam = listOf(DayState())
        mealTypes.forEachIndexed { mealIndex, mealType ->
            val expanded = buildList {
                beam.forEach { state ->
                    candidatesByMeal.getValue(mealType).forEach { candidate ->
                        add(
                            DayState(
                                meals = state.meals + candidate.meal,
                                preferredVector = state.preferredVector + candidate.preferredVector,
                                attainable = state.attainable + candidate.attainable,
                                fruitMeals = state.fruitMeals + if (candidate.fruit) 1 else 0,
                                vegetableMeals = state.vegetableMeals + if (candidate.vegetable) 1 else 0
                            )
                        )
                    }
                }
            }
            val remaining = suffixEnvelope[mealIndex + 1]
            val fruitRemaining = suffixFruitPossible[mealIndex + 1]
            val vegetableRemaining = suffixVegetablePossible[mealIndex + 1]
            beam = expanded
                .filter { state ->
                    state.fruitMeals + fruitRemaining >= 2 &&
                        state.vegetableMeals + vegetableRemaining >= 2 &&
                        state.attainable.maximum.fiber + remaining.maximum.fiber >= 25.0
                }
                .groupBy { stateBucket(it, remaining, recommendation) }
                .values
                .flatMap { bucket ->
                    bucket.sortedWith(
                        compareBy<DayState> { projectedRangeScore(it, remaining, recommendation) }
                            .thenByDescending { it.attainable.maximum.fiber }
                            .thenByDescending { it.attainable.maximum.protein }
                    ).take(BEAM_PER_STATE_BUCKET)
                }
                .sortedBy { projectedRangeScore(it, remaining, recommendation) }
        }

        val finals = beam
            .filter { it.fruitMeals >= 2 && it.vegetableMeals >= 2 && it.attainable.maximum.fiber >= 25.0 }
            .sortedWith(
                compareBy<DayState> { rangeScore(it.attainable, recommendation, 1.0) }
                    .thenByDescending { it.attainable.maximum.fiber }
                    .thenBy { preferredScore(it.preferredVector, recommendation, 1.0) }
            )
            .take(MAX_FINAL_OPTIMIZATIONS)

        finals.forEachIndexed { index, state ->
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
        val ruleByFood = rules.filter { mealType in it.allowedMealTypes }.groupBy { it.itemId }
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
                roleAssignments(chosen, mealType)
                    .take(MAX_ROLE_ASSIGNMENTS_PER_COMBINATION)
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
                            id = 31_000L + mealType.ordinal * 10_000L + raw.size,
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
                            roleSignature = roles.sortedBy { it.ordinal }
                                .joinToString("+") { it.name }
                        )
                    }
            }
        }

        val share = mealShares[mealType] ?: 0.0
        val unique = raw.distinctBy { candidate ->
            candidate.meal.items.joinToString(",") {
                "${it.foodId}@${it.minimumGrams}-${it.maximumGrams}"
            }
        }

        // First preserve culinary structures. Inside each structure keep both
        // nutrition-near and nutrient-capability extremes, so a high-fibre
        // ingredient cannot disappear merely because its preferred grams are
        // locally caloric.
        val structurallyDiverse = unique.groupBy {
            Triple(it.fruit, it.vegetable, it.roleSignature)
        }.values.flatMap { group ->
            val selected = linkedSetOf<MealCandidate>()
            fun take(comparator: Comparator<MealCandidate>, count: Int) {
                group.sortedWith(comparator).take(count).forEach(selected::add)
            }
            take(compareBy { rangeScore(it.attainable, recommendation, share) }, 4)
            take(compareByDescending { it.attainable.maximum.fiber }, 2)
            take(compareByDescending { it.attainable.maximum.protein }, 2)
            take(compareByDescending { it.attainable.maximum.carbohydrates }, 2)
            take(compareByDescending { it.attainable.maximum.fat }, 1)
            take(compareBy { it.attainable.minimum.calories }, 1)
            selected.take(MAX_PER_ROLE_SIGNATURE)
        }

        return structurallyDiverse.groupBy { it.fruit to it.vegetable }.values.flatMap { bucket ->
            if (bucket.size <= MAX_PER_COVERAGE_BUCKET) return@flatMap bucket
            val selected = linkedSetOf<MealCandidate>()
            fun take(comparator: Comparator<MealCandidate>, count: Int) {
                bucket.sortedWith(comparator).take(count).forEach(selected::add)
            }
            // Guarantee one representative per role structure before filling
            // the remaining capacity with different nutritional extremes.
            bucket.groupBy { it.roleSignature }.values.forEach { group ->
                group.minByOrNull { rangeScore(it.attainable, recommendation, share) }
                    ?.let(selected::add)
            }
            take(compareBy { rangeScore(it.attainable, recommendation, share) }, 24)
            take(compareByDescending { it.attainable.maximum.fiber }, 18)
            take(compareByDescending { it.attainable.maximum.protein }, 18)
            take(compareByDescending { it.attainable.maximum.carbohydrates }, 12)
            take(compareByDescending { it.attainable.maximum.fat }, 12)
            take(compareBy { it.attainable.minimum.calories }, 12)
            selected.take(MAX_PER_COVERAGE_BUCKET)
        }
    }

    private fun roleAssignments(
        foods: List<Food>,
        mealType: MealType
    ): Sequence<List<CulinaryRole>> = sequence {
        val choices = foods.map { food ->
            CulinaryPolicy.roles(food).sortedWith(
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

    private fun envelope(candidates: List<MealCandidate>): VectorRange = VectorRange(
        minimum = Vector(
            calories = candidates.minOf { it.attainable.minimum.calories },
            protein = candidates.minOf { it.attainable.minimum.protein },
            carbohydrates = candidates.minOf { it.attainable.minimum.carbohydrates },
            fat = candidates.minOf { it.attainable.minimum.fat },
            fiber = candidates.minOf { it.attainable.minimum.fiber }
        ),
        maximum = Vector(
            calories = candidates.maxOf { it.attainable.maximum.calories },
            protein = candidates.maxOf { it.attainable.maximum.protein },
            carbohydrates = candidates.maxOf { it.attainable.maximum.carbohydrates },
            fat = candidates.maxOf { it.attainable.maximum.fat },
            fiber = candidates.maxOf { it.attainable.maximum.fiber }
        )
    )

    private fun stateBucket(
        state: DayState,
        remaining: VectorRange,
        recommendation: Recommendation
    ): String {
        val projected = state.attainable + remaining
        fun relation(minimum: Double, maximum: Double, target: Double): Int = when {
            maximum < target -> 0
            minimum > target -> 2
            else -> 1
        }
        val fiberBucket = floor(state.attainable.maximum.fiber / 5.0)
            .toInt().coerceIn(0, 7)
        return listOf(
            state.fruitMeals.coerceAtMost(2),
            state.vegetableMeals.coerceAtMost(2),
            fiberBucket,
            relation(projected.minimum.calories, projected.maximum.calories, recommendation.calories.toDouble()),
            relation(projected.minimum.protein, projected.maximum.protein, recommendation.proteinGrams.toDouble()),
            relation(projected.minimum.carbohydrates, projected.maximum.carbohydrates, recommendation.carbohydrateGrams.toDouble()),
            relation(projected.minimum.fat, projected.maximum.fat, recommendation.fatGrams.toDouble())
        ).joinToString(":")
    }

    private fun projectedRangeScore(
        state: DayState,
        remaining: VectorRange,
        recommendation: Recommendation
    ): Double {
        val projected = state.attainable + remaining
        val fiberPenalty = if (projected.maximum.fiber >= 25.0) 0.0
            else ((25.0 - projected.maximum.fiber) / 25.0) * 10.0
        return rangeScore(projected, recommendation, 1.0) + fiberPenalty
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
