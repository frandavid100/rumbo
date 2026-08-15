package es.david.rumbo.logic

import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.PlanWeek
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.resolvedGrams
import kotlin.math.abs
import kotlin.math.max

data class FoodSuggestion(val food: Food, val reason: String, val score: Double)

enum class EfficientNutrient { PROTEIN, CARBOHYDRATES, FAT, FIBER }

/** Ranks foods outside the repertoire using only data already stored by Rumbo. */
object FoodSuggestionEngine {
    private const val MINIMUM_ACTIVE_REPERTOIRE_SIZE = 15
    private const val MINIMUM_MACRO_EFFICIENCY = 0.50

    fun suggest(
        foods: List<Food>,
        repertoireFoodIds: Set<Long>,
        planningRules: List<PlanningRule>,
        plannedMeals: List<PlannedMeal>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation?,
        excludedFoodIds: Set<Long> = emptySet(),
        repertoireAssessment: RepertoireAssessment? = null,
        candidateAssessments: Map<Long, RepertoireAssessment>? = null,
        limit: Int = 3,
        diversifyResults: Boolean = true
    ): List<FoodSuggestion> {
        if (limit <= 0) return emptyList()

        val foodsById = foods.associateBy { it.id }
        val activeFoodIds = planningRules.asSequence()
            .filter { it.isActive && it.itemKind == PlannedItemKind.FOOD }
            .map { it.itemId }
            .filter(foodsById::containsKey)
            .toSet()
            .ifEmpty { repertoireFoodIds }
        val activeFoods = activeFoodIds.mapNotNull(foodsById::get)
        val repertoireNeedsExpansion = activeFoods.size < MINIMUM_ACTIVE_REPERTOIRE_SIZE
        val activeRetailers = activeFoods.mapNotNull { it.retailer.normalized() }.toSet()
        val categoryCounts = activeFoods.groupingBy { it.category }.eachCount()
        val totals = weeklyTotals(
            plannedMeals.filter { it.planWeek == PlanWeek.CURRENT }, foodsById, dishesById
        )
        val deficits = repertoireAssessment?.let(Deficits::from) ?:
            Deficits.from(recommendation, totals)
        val underTargetKinds = repertoireAssessment?.nutrition
            ?.filterValues { it.deviation < 0.0 && it.fit != TargetFit.ON_TARGET }
            ?.keys.orEmpty().ifEmpty {
            recommendation?.let {
            listOf(
                NutrientKind.CALORIES to (totals.calories to it.calories * 7.0),
                NutrientKind.PROTEIN to (totals.protein to it.proteinGrams * 7.0),
                NutrientKind.CARBOHYDRATES to
                    (totals.carbohydrate to it.carbohydrateGrams * 7.0),
                NutrientKind.FAT to (totals.fat to it.fatGrams * 7.0)
            ).filterTo(mutableSetOf()) { (kind, values) ->
                values.first < values.second &&
                    NutritionTolerancePolicy.evaluate(
                        kind, values.first, values.second
                    ).fit != TargetFit.ON_TARGET
            }.mapTo(mutableSetOf()) { it.first }
        }.orEmpty()
        }
        val macroCorrectionNeeded = underTargetKinds.any {
            it == NutrientKind.PROTEIN ||
                it == NutrientKind.CARBOHYDRATES ||
                it == NutrientKind.FAT
        }
        val mealCoverageNeed = repertoireAssessment?.coverage
            ?.filter { it.alternatives <= 1 }
            ?.minByOrNull { it.alternatives }
        val coverageCorrectionNeeded = mealCoverageNeed != null
        val coverageReason = mealCoverageNeed?.let {
            if (it.alternatives == 0) {
                "Te falta una opción para " + it.mealType.label.lowercase() + "."
            } else {
                "Te falta variedad para " + it.mealType.label.lowercase() + "."
            }
        }
        val assessmentStillNeedsHelp = repertoireAssessment?.status?.let {
            it == RepertoireStatus.INSUFFICIENT || it == RepertoireStatus.LIMITED
        } ?: false

        val ranked = foods.asSequence()
            .filter {
                it.id !in repertoireFoodIds && it.id !in excludedFoodIds &&
                    it.hasComparableNutrition() && it.isRecommendableCandidate() &&
                    efficientNutrients(it).isNotEmpty()
            }
            .filter { activeRetailers.isEmpty() || it.retailer.normalized() in activeRetailers }
            .map { candidate ->
                val categoryNovelty = when {
                    candidate.category == FoodCategory.OTHER -> 0.0
                    repertoireNeedsExpansion ->
                        0.60 / (1 + (categoryCounts[candidate.category] ?: 0))
                    categoryCounts[candidate.category] == null -> 0.20
                    else -> 0.05 / max(1, categoryCounts.getValue(candidate.category))
                }
                val measuredImpact = if (
                    repertoireAssessment != null && candidateAssessments != null
                ) {
                    candidateAssessments[candidate.id]?.let {
                        assessmentImprovement(repertoireAssessment, it)
                    }
                } else null
                FoodSuggestion(
                    food = candidate,
                    reason = if (
                        coverageReason != null && !candidate.addresses(deficits)
                    ) {
                        coverageReason
                    } else {
                        reason(
                            candidate, activeFoods, categoryCounts, deficits,
                            repertoireNeedsExpansion, macroCorrectionNeeded
                        )
                    },
                    score = nutritionalUtility(
                        candidate, recommendation, deficits, macroCorrectionNeeded
                    ) +
                        categoryNovelty +
                        (measuredImpact ?: 0.0) * 3.0 -
                        redundancyPenalty(candidate, activeFoods) +
                        if (repertoireNeedsExpansion) 0.0 else affinity(candidate, activeFoods) +
                        if (candidate.unitAmount != null && candidate.unitName != null) 0.05 else 0.0
                )
            }
            .filter {
                val nutritionallyRelevant = if (macroCorrectionNeeded) {
                    it.food.addresses(deficits)
                } else {
                    coverageCorrectionNeeded || repertoireNeedsExpansion ||
                        efficientNutrients(it.food).isNotEmpty()
                }
                val producesMeasuredImprovement =
                    if (repertoireAssessment != null && candidateAssessments != null) {
                        candidateAssessments[it.food.id]?.let { candidate ->
                            assessmentImprovement(repertoireAssessment, candidate) > 0.01
                        } == true
                    } else {
                        true
                    }
                val passesMeasuredCheck = if (candidateAssessments != null) {
                    producesMeasuredImprovement
                } else {
                    assessmentStillNeedsHelp || producesMeasuredImprovement
                }
                nutritionallyRelevant && passesMeasuredCheck
            }
            .sortedWith(compareByDescending<FoodSuggestion> { it.score }.thenBy { it.food.name.lowercase() })
            .distinctBy { equivalenceKey(it.food) }
            .toList()
        return if (diversifyResults) diversify(ranked, limit) else ranked.take(limit)
    }

    /**
     * Uses the recommender's complete ranking to find foods that would be preferred
     * to [source]. Foods already in the user's menu or explicitly dismissed remain
     * ineligible, exactly as they are in the main recommender.
     */
    fun moreEfficientAlternatives(
        source: Food,
        foods: List<Food>,
        repertoireFoodIds: Set<Long>,
        planningRules: List<PlanningRule>,
        plannedMeals: List<PlannedMeal>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation?,
        excludedFoodIds: Set<Long> = emptySet(),
        repertoireAssessment: RepertoireAssessment? = null,
        limit: Int = 3
    ): List<FoodSuggestion> {
        if (limit <= 0) return emptyList()
        val common = suggest(
            foods = foods,
            repertoireFoodIds = repertoireFoodIds,
            planningRules = planningRules,
            plannedMeals = plannedMeals,
            dishesById = dishesById,
            recommendation = recommendation,
            excludedFoodIds = excludedFoodIds,
            repertoireAssessment = repertoireAssessment,
            limit = foods.size,
            diversifyResults = false
        )
        val sourceScore = common.firstOrNull { it.food.id == source.id }?.score
            ?: suggest(
                foods = foods,
                repertoireFoodIds = repertoireFoodIds - source.id,
                planningRules = planningRules,
                plannedMeals = plannedMeals,
                dishesById = dishesById,
                recommendation = recommendation,
                excludedFoodIds = excludedFoodIds - source.id,
                repertoireAssessment = repertoireAssessment,
                limit = foods.size,
                diversifyResults = false
            ).firstOrNull { it.food.id == source.id }?.score
            ?: Double.NEGATIVE_INFINITY
        return common.asSequence()
            .filter { it.food.id != source.id && it.score > sourceScore }
            .take(limit)
            .toList()
    }

    private fun assessmentImprovement(
        before: RepertoireAssessment,
        after: RepertoireAssessment
    ): Double = assessmentDistance(before) - assessmentDistance(after)

    private fun assessmentDistance(assessment: RepertoireAssessment): Double {
        val nutrientDistance = assessment.nutrition.entries.sumOf { (kind, capacity) ->
            val weight = when (kind) {
                NutrientKind.PROTEIN -> 3.0
                NutrientKind.CALORIES -> 2.0
                NutrientKind.CARBOHYDRATES, NutrientKind.FAT -> 1.5
            }
            weight * (abs(capacity.deviation) / capacity.target.coerceAtLeast(1.0))
                .coerceAtMost(2.0)
        }
        val missingMealCoverage = assessment.coverage.count { it.alternatives == 0 } * 0.75
        val limitedMealCoverage = assessment.coverage.count { it.alternatives == 1 } * 0.20
        val solverPenalty = assessment.metrics.worstPenalty
            .takeIf { it.isFinite() }
            ?.coerceAtMost(4.0)
            ?.times(0.20)
            ?: 0.80
        return nutrientDistance + missingMealCoverage + limitedMealCoverage + solverPenalty
    }

    private fun diversify(
        ranked: List<FoodSuggestion>,
        limit: Int
    ): List<FoodSuggestion> {
        val selected = mutableListOf<FoodSuggestion>()
        val usedReasons = mutableSetOf<String>()
        ranked.forEach { suggestion ->
            if (selected.size < limit && suggestion.reason !in usedReasons) {
                selected += suggestion
                usedReasons += suggestion.reason
            }
        }
        ranked.forEach { suggestion ->
            if (selected.size < limit && selected.none { it.food.id == suggestion.food.id }) {
                selected += suggestion
            }
        }
        return selected
    }

    private fun nutritionalUtility(
        food: Food,
        recommendation: Recommendation?,
        deficits: Deficits,
        prioritizeMacros: Boolean
    ): Double {
        val efficiency = MacroEfficiency.from(food)
        val proteinQuality = if (food.isCleanProteinSource()) 1.0 else 0.0
        if (recommendation == null) return efficiency.fiber * 0.12
        val servingFactor = (food.unitAmount ?: 100.0).coerceIn(30.0, 250.0) / 100.0
        fun contribution(value: Double?, target: Int): Double =
            ((value ?: 0.0) * servingFactor / target.coerceAtLeast(1))
                .coerceIn(0.0, 0.35) / 0.35
        return deficits.calories * contribution(food.calories, recommendation.calories) * 0.03 +
            deficits.protein * proteinQuality *
                (contribution(food.proteinGrams, recommendation.proteinGrams) * 0.30 +
                    efficiency.protein * 0.40) +
            deficits.carbohydrate * (contribution(food.carbohydrateGrams, recommendation.carbohydrateGrams) * 0.08 +
                efficiency.carbohydrate * 0.16) +
            deficits.fat * (contribution(food.fatGrams, recommendation.fatGrams) * 0.08 +
                efficiency.fat * 0.16) +
            if (prioritizeMacros) 0.0 else
                deficits.fiber * (((food.fiberGrams ?: 0.0) * servingFactor / 25.0)
                    .coerceIn(0.0, 0.35) / 0.35 * 0.12 + efficiency.fiber * 0.22)
    }

    private fun Food.addresses(deficits: Deficits): Boolean =
        deficits.protein > 0.0 && isEfficientSourceOf(NutrientKind.PROTEIN) ||
            deficits.carbohydrate > 0.0 && isEfficientSourceOf(NutrientKind.CARBOHYDRATES) ||
            deficits.fat > 0.0 && isEfficientSourceOf(NutrientKind.FAT)

    private fun Food.isEfficientSourceOf(kind: NutrientKind): Boolean {
        val efficiency = MacroEfficiency.from(this)
        return when (kind) {
            NutrientKind.PROTEIN ->
                isCleanProteinSource() && (proteinGrams ?: 0.0) >= 3.0 &&
                    efficiency.protein >= MINIMUM_MACRO_EFFICIENCY
            NutrientKind.CARBOHYDRATES ->
                (carbohydrateGrams ?: 0.0) >= 5.0 &&
                    efficiency.carbohydrate >= MINIMUM_MACRO_EFFICIENCY
            NutrientKind.FAT ->
                (fatGrams ?: 0.0) >= 3.0 &&
                    efficiency.fat >= MINIMUM_MACRO_EFFICIENCY
            NutrientKind.CALORIES -> false
        }
    }

    private fun redundancyPenalty(candidate: Food, activeFoods: List<Food>): Double {
        if (activeFoods.isEmpty()) return 0.0
        val candidateEfficiency = MacroEfficiency.from(candidate)
        val nearestDistance = activeFoods.minOf { existing ->
            val existingEfficiency = MacroEfficiency.from(existing)
            (
                abs(candidateEfficiency.protein - existingEfficiency.protein) +
                    abs(candidateEfficiency.carbohydrate - existingEfficiency.carbohydrate) +
                    abs(candidateEfficiency.fat - existingEfficiency.fat) +
                    abs(candidateEfficiency.fiber - existingEfficiency.fiber)
                ) / 4.0
        }
        return when {
            nearestDistance < 0.06 -> 0.35
            nearestDistance < 0.12 -> 0.18
            else -> 0.0
        }
    }

    private fun affinity(candidate: Food, activeFoods: List<Food>): Double {
        val sameSubcategory = candidate.subcategory.normalized()?.let { value ->
            activeFoods.any { it.subcategory.normalized() == value }
        } == true
        val sameFamily = candidate.family.normalized()?.let { value ->
            activeFoods.any { it.family.normalized() == value }
        } == true
        return when { sameSubcategory -> 0.05; sameFamily -> 0.02; else -> 0.0 }
    }

    fun efficientNutrients(food: Food): Set<EfficientNutrient> {
        if (!food.hasComparableNutrition() || !food.isRecommendableCandidate()) return emptySet()
        val efficiency = MacroEfficiency.from(food)
        return buildSet {
            if (food.isCleanProteinSource() &&
                food.isEfficientSourceOf(NutrientKind.PROTEIN)
            ) add(EfficientNutrient.PROTEIN)
            if (food.isEfficientSourceOf(NutrientKind.CARBOHYDRATES)) {
                add(EfficientNutrient.CARBOHYDRATES)
            }
            if (food.isEfficientSourceOf(NutrientKind.FAT)) add(EfficientNutrient.FAT)
            if ((food.fiberGrams ?: 0.0) >= 2.0 &&
                efficiency.fiber >= MINIMUM_MACRO_EFFICIENCY
            ) add(EfficientNutrient.FIBER)
        }
    }

    /**
     * Lightweight query-time score. It lets an actively searched food compete on
     * its usefulness without running the full menu generator for every catalogue item.
     */
    fun personalizedSearchScore(
        food: Food,
        repertoireAssessment: RepertoireAssessment?,
        recommendation: Recommendation?
    ): Double {
        if (!food.hasComparableNutrition() || !food.isRecommendableCandidate()) {
            return Double.NEGATIVE_INFINITY
        }
        val available = efficientNutrients(food)
        if (available.isEmpty()) return Double.NEGATIVE_INFINITY
        val efficiency = MacroEfficiency.from(food)
        if (repertoireAssessment == null) {
            return maxOf(
                efficiency.protein,
                efficiency.carbohydrate,
                efficiency.fat,
                efficiency.fiber * 0.75
            )
        }
        val deficits = Deficits.from(repertoireAssessment)
        val macroCorrectionNeeded = repertoireAssessment.nutrition.any { (kind, capacity) ->
            kind != NutrientKind.CALORIES &&
                capacity.deviation < 0.0 && capacity.fit != TargetFit.ON_TARGET
        }
        val deficitFit = maxOf(
            if (EfficientNutrient.PROTEIN in available) deficits.protein * efficiency.protein else 0.0,
            if (EfficientNutrient.CARBOHYDRATES in available) {
                deficits.carbohydrate * efficiency.carbohydrate
            } else 0.0,
            if (EfficientNutrient.FAT in available) deficits.fat * efficiency.fat else 0.0,
            if (!macroCorrectionNeeded && EfficientNutrient.FIBER in available) {
                efficiency.fiber * 0.25
            } else 0.0
        )
        return deficitFit * 2.0 +
            nutritionalUtility(food, recommendation, deficits, macroCorrectionNeeded)
    }

    private fun reason(
        food: Food,
        activeFoods: List<Food>,
        categoryCounts: Map<FoodCategory, Int>,
        deficits: Deficits,
        repertoireNeedsExpansion: Boolean,
        prioritizeMacros: Boolean
    ): String {
        val efficiency = MacroEfficiency.from(food)
        val available = efficientNutrients(food)
        val weighted = buildList {
            if (EfficientNutrient.PROTEIN in available) {
                add(EfficientNutrient.PROTEIN to deficits.protein * efficiency.protein)
            }
            if (EfficientNutrient.CARBOHYDRATES in available) {
                add(EfficientNutrient.CARBOHYDRATES to
                    deficits.carbohydrate * efficiency.carbohydrate)
            }
            if (EfficientNutrient.FAT in available) {
                add(EfficientNutrient.FAT to deficits.fat * efficiency.fat)
            }
            if (!prioritizeMacros && EfficientNutrient.FIBER in available) {
                add(EfficientNutrient.FIBER to deficits.fiber * efficiency.fiber)
            }
        }
        val selected = weighted.maxByOrNull { it.second }
            ?.takeIf { it.second > 0.0 }
            ?.first
            ?: available.maxByOrNull {
                when (it) {
                    EfficientNutrient.PROTEIN -> efficiency.protein
                    EfficientNutrient.CARBOHYDRATES -> efficiency.carbohydrate
                    EfficientNutrient.FAT -> efficiency.fat
                    EfficientNutrient.FIBER -> if (prioritizeMacros) -1.0 else efficiency.fiber
                }
            }
            ?: error("Solo se solicita un motivo para candidatos eficientes")
        return when (selected) {
            EfficientNutrient.PROTEIN -> "Es una fuente eficiente de proteína."
            EfficientNutrient.CARBOHYDRATES -> "Es una fuente eficiente de hidratos."
            EfficientNutrient.FAT -> "Es una fuente eficiente de grasas."
            EfficientNutrient.FIBER -> "Es una fuente eficiente de fibra."
        }
    }

    /**
     * Prevents a carbohydrate deficit from promoting energy-dense processed foods.
     * Fruit is allowed more naturally occurring sugar, but still has to be low in fat.
     */
    private fun Food.isRecommendableCandidate(): Boolean {
        if ((saturatedFatGrams ?: 0.0) > 8.0 || (saltGrams ?: 0.0) > 3.0) return false

        val carbohydrate = carbohydrateGrams ?: 0.0
        val proteinEnergy = (proteinGrams ?: 0.0) * 4.0
        val fat = fatGrams ?: 0.0
        val concentratedCarbohydrateAndFat = carbohydrate >= 20.0 && fat > 8.0
        if (concentratedCarbohydrateAndFat) return false

        val carbohydrateDominant = carbohydrate * 4.0 >= max(proteinEnergy, fat * 9.0)
        if (!carbohydrateDominant) return true

        val sugarLimit = if (category == FoodCategory.FRUIT) 20.0 else 15.0
        return fat <= 8.0 &&
            (saturatedFatGrams ?: 0.0) <= 3.0 &&
            (sugarGrams ?: 0.0) <= sugarLimit &&
            (saltGrams ?: 0.0) <= 1.5
    }

    private fun Food.isCleanProteinSource(): Boolean {
        val protein = proteinGrams ?: 0.0
        val calories = calories ?: return false
        if (protein < 5.0 || calories <= 0.0) return false
        return protein * 100.0 / calories >= 8.0 &&
            (saturatedFatGrams ?: 0.0) <= 5.0 &&
            (saltGrams ?: 0.0) <= 2.0
    }

    private fun equivalenceKey(food: Food): String {
        val group = food.subcategory.normalized() ?: food.family.normalized()
        val fallbackName = food.name.lowercase()
            .replace(Regex("\\b\\d+(?:[.,]\\d+)?\\s*(?:g|kg|ml|l)\\b"), "")
            .replace(Regex("\\s+"), " ").trim()
        return listOf(
            food.retailer.normalized().orEmpty(),
            food.category.name,
            group ?: fallbackName
        ).joinToString("|")
    }

    private fun weeklyTotals(
        meals: List<PlannedMeal>, foodsById: Map<Long, Food>, dishesById: Map<Long, Dish>
    ): Totals {
        var result = Totals()
        meals.forEach { meal ->
            meal.days.forEach { day ->
                meal.items.forEach { item ->
                    result += foodsById[item.foodId].totals(meal.resolvedGrams(item, day))
                }
                meal.dishes.forEach dishLoop@{ plannedDish ->
                    val dish = dishesById[plannedDish.dishId] ?: return@dishLoop
                    val recipeWeight = dish.ingredients.sumOf { it.grams }
                    if (recipeWeight > 0.0) {
                        val scale = meal.resolvedGrams(plannedDish, day) / recipeWeight
                        dish.ingredients.forEach { ingredient ->
                            result += foodsById[ingredient.foodId].totals(ingredient.grams * scale)
                        }
                    }
                }
            }
        }
        return result
    }

    private data class MacroEfficiency(
        val protein: Double,
        val carbohydrate: Double,
        val fat: Double,
        val fiber: Double
    ) {
        companion object {
            fun from(food: Food): MacroEfficiency {
                val calories = (food.calories ?: 0.0).coerceAtLeast(1.0)
                val protein = food.proteinGrams ?: 0.0
                val carbohydrate = food.carbohydrateGrams ?: 0.0
                val fat = food.fatGrams ?: 0.0
                val saturated = food.saturatedFatGrams
                val proteinPer100Calories = protein * 100.0 / calories
                val carbohydrateEnergyShare = (carbohydrate * 4.0 / calories).coerceIn(0.0, 1.0)
                val fatEnergyShare = (fat * 9.0 / calories).coerceIn(0.0, 1.0)
                val unsaturatedFactor = if (saturated == null || fat <= 0.0) 0.75 else
                    1.0 - (saturated / fat).coerceIn(0.0, 1.0) * 0.75
                val fiberPer100Calories = (food.fiberGrams ?: 0.0) * 100.0 / calories
                return MacroEfficiency(
                    protein = (proteinPer100Calories / 15.0).coerceIn(0.0, 1.0) *
                        secondaryNutrientPenalty(food),
                    carbohydrate = carbohydrateEnergyShare * (1.0 - fatEnergyShare),
                    fat = fatEnergyShare * (1.0 - carbohydrateEnergyShare) * unsaturatedFactor,
                    fiber = (fiberPer100Calories / 4.0).coerceIn(0.0, 1.0)
                )
            }

            private fun secondaryNutrientPenalty(food: Food): Double {
                val saturatedPenalty = food.saturatedFatGrams?.let {
                    1.0 - (it / 10.0).coerceIn(0.0, 0.5)
                } ?: 0.90
                val saltPenalty = food.saltGrams?.let {
                    1.0 - (it / 5.0).coerceIn(0.0, 0.4)
                } ?: 0.95
                return saturatedPenalty * saltPenalty
            }
        }
    }

    private data class Deficits(
        val calories: Double, val protein: Double, val carbohydrate: Double,
        val fat: Double, val fiber: Double
    ) {
        companion object {
            fun from(assessment: RepertoireAssessment): Deficits {
                fun deficit(kind: NutrientKind): Double {
                    val capacity = assessment.nutrition[kind] ?: return 0.0
                    return if (capacity.deviation >= 0.0 ||
                        capacity.fit == TargetFit.ON_TARGET
                    ) 0.0 else {
                        (-capacity.deviation / capacity.target.coerceAtLeast(1.0))
                            .coerceIn(0.0, 1.0)
                    }
                }
                return Deficits(
                    calories = deficit(NutrientKind.CALORIES),
                    protein = deficit(NutrientKind.PROTEIN),
                    carbohydrate = deficit(NutrientKind.CARBOHYDRATES),
                    fat = deficit(NutrientKind.FAT),
                    fiber = 0.0
                )
            }

            fun from(recommendation: Recommendation?, totals: Totals): Deficits {
                if (recommendation == null) return Deficits(0.0, 0.0, 0.0, 0.0, 0.0)
                fun deficit(actual: Double, target: Double): Double =
                    ((target - actual) / target.coerceAtLeast(1.0)).coerceIn(0.0, 1.0)
                return Deficits(
                    deficit(totals.calories, recommendation.calories * 7.0),
                    deficit(totals.protein, recommendation.proteinGrams * 7.0),
                    deficit(totals.carbohydrate, recommendation.carbohydrateGrams * 7.0),
                    deficit(totals.fat, recommendation.fatGrams * 7.0),
                    deficit(totals.fiber, 25.0 * 7.0)
                )
            }
        }
    }

    private data class Totals(
        val calories: Double = 0.0, val protein: Double = 0.0,
        val carbohydrate: Double = 0.0, val fat: Double = 0.0, val fiber: Double = 0.0
    )

    private operator fun Totals.plus(other: Totals) = Totals(
        calories + other.calories, protein + other.protein,
        carbohydrate + other.carbohydrate, fat + other.fat, fiber + other.fiber
    )

    private fun Food?.totals(grams: Double): Totals {
        val factor = grams / 100.0
        return Totals(
            (this?.calories ?: 0.0) * factor,
            (this?.proteinGrams ?: 0.0) * factor,
            (this?.carbohydrateGrams ?: 0.0) * factor,
            (this?.fatGrams ?: 0.0) * factor,
            (this?.fiberGrams ?: 0.0) * factor
        )
    }

    private fun String?.normalized(): String? = this?.trim()?.lowercase()?.takeIf { it.isNotEmpty() }
}
