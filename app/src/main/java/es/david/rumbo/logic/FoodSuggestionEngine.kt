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
import kotlin.math.max

data class FoodSuggestion(val food: Food, val reason: String, val score: Double)

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
        limit: Int = 3
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

        val ranked = foods.asSequence()
            .filter {
                it.id !in repertoireFoodIds && it.id !in excludedFoodIds &&
                    it.hasComparableNutrition() && it.isRecommendableCandidate()
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
                FoodSuggestion(
                    food = candidate,
                    reason = reason(
                        candidate, activeFoods, categoryCounts, deficits,
                        repertoireNeedsExpansion, macroCorrectionNeeded
                    ),
                    score = nutritionalUtility(
                        candidate, recommendation, deficits, macroCorrectionNeeded
                    ) +
                        categoryNovelty +
                        if (repertoireNeedsExpansion) 0.0 else affinity(candidate, activeFoods) +
                        if (candidate.unitAmount != null && candidate.unitName != null) 0.05 else 0.0
                )
            }
            .filter {
                if (macroCorrectionNeeded) it.food.addresses(deficits)
                else repertoireNeedsExpansion
            }
            .sortedWith(compareByDescending<FoodSuggestion> { it.score }.thenBy { it.food.name.lowercase() })
            .distinctBy { equivalenceKey(it.food) }
            .toList()
        return diversify(ranked, limit)
    }

    private fun diversify(
        ranked: List<FoodSuggestion>,
        limit: Int
    ): List<FoodSuggestion> {
        val selected = mutableListOf<FoodSuggestion>()
        val usedReasons = mutableSetOf<String>()
        val usedCategories = mutableSetOf<FoodCategory>()
        ranked.forEach { suggestion ->
            if (selected.size >= limit) return@forEach
            if (suggestion.reason !in usedReasons &&
                suggestion.food.category !in usedCategories
            ) {
                selected += suggestion
                usedReasons += suggestion.reason
                usedCategories += suggestion.food.category
            }
        }
        ranked.forEach { suggestion ->
            if (selected.size >= limit) return@forEach
            if (selected.none { it.food.id == suggestion.food.id } &&
                suggestion.food.category !in usedCategories
            ) {
                selected += suggestion.copy(reason = varietyReason(suggestion.food))
                usedCategories += suggestion.food.category
            }
        }
        ranked.forEach { suggestion ->
            if (selected.size >= limit) return@forEach
            if (selected.none { it.food.id == suggestion.food.id }) {
                selected += suggestion.copy(reason = varietyReason(suggestion.food))
            }
        }
        return selected
    }

    private fun varietyReason(food: Food): String =
        if (food.category != FoodCategory.OTHER) {
            "Aporta más variedad con " + food.category.label.lowercase() + "."
        } else {
            "Puede darte más variedad."
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

    private fun affinity(candidate: Food, activeFoods: List<Food>): Double {
        val sameSubcategory = candidate.subcategory.normalized()?.let { value ->
            activeFoods.any { it.subcategory.normalized() == value }
        } == true
        val sameFamily = candidate.family.normalized()?.let { value ->
            activeFoods.any { it.family.normalized() == value }
        } == true
        return when { sameSubcategory -> 0.05; sameFamily -> 0.02; else -> 0.0 }
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
        val efficientSources = listOf(
            Triple(
                if (food.isCleanProteinSource()) deficits.protein * efficiency.protein else 0.0,
                if (food.isCleanProteinSource()) efficiency.protein else 0.0,
                "Aporta proteína con pocas calorías."
            ),
            Triple(deficits.carbohydrate * efficiency.carbohydrate, efficiency.carbohydrate,
                "Aporta hidratos con poca grasa."),
            Triple(deficits.fat * efficiency.fat, efficiency.fat,
                if (food.saturatedFatGrams != null) "Aporta grasa con poca grasa saturada."
                else "Aporta grasa con pocos hidratos."),
            Triple(
                if (prioritizeMacros) 0.0 else deficits.fiber * efficiency.fiber,
                if (prioritizeMacros) 0.0 else efficiency.fiber,
                "Aporta fibra con pocas calorías."
            )
        )
        efficientSources.filter { it.second >= MINIMUM_MACRO_EFFICIENCY }
            .maxByOrNull { it.first }
            ?.takeIf { it.first >= 0.10 }
            ?.let { return it.third }

        val nutrientReasons = listOf(
            Triple(
                deficits.protein,
                food.isEfficientSourceOf(NutrientKind.PROTEIN),
                "Porque falta proteína en tu repertorio."
            ),
            Triple(
                deficits.carbohydrate,
                food.isEfficientSourceOf(NutrientKind.CARBOHYDRATES),
                "Porque faltan hidratos en tu repertorio."
            ),
            Triple(
                deficits.fat,
                food.isEfficientSourceOf(NutrientKind.FAT),
                "Porque faltan grasas en tu repertorio."
            )
        )
        nutrientReasons.filter { it.second }
            .maxByOrNull { it.first }
            ?.takeIf { it.first >= 0.12 }
            ?.let { return it.third }
        if (food.category != FoodCategory.OTHER && categoryCounts[food.category] == null) {
            return "Aporta más variedad con " + food.category.label.lowercase() + "."
        }
        if (repertoireNeedsExpansion) return "Puede darte más variedad."

        val sharedSubcategory = food.subcategory.normalized()?.let { subcategory ->
            activeFoods.any { it.subcategory.normalized() == subcategory }
        } == true
        if (sharedSubcategory) {
            return "Ya comes otros productos de " +
                food.subcategory.orEmpty().lowercase() + "."
        }
        val sharedFamily = food.family.normalized()?.let { family ->
            activeFoods.any { it.family.normalized() == family }
        } == true
        if (sharedFamily) {
            return "Ya comes otros productos de " +
                food.family.orEmpty().lowercase() + "."
        }
        return "Puede darte más variedad."
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
