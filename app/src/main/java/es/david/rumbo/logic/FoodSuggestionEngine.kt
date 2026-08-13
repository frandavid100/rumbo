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
    fun suggest(
        foods: List<Food>,
        repertoireFoodIds: Set<Long>,
        planningRules: List<PlanningRule>,
        plannedMeals: List<PlannedMeal>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation?,
        excludedFoodIds: Set<Long> = emptySet(),
        limit: Int = 3
    ): List<FoodSuggestion> {
        if (limit <= 0 || repertoireFoodIds.isEmpty()) return emptyList()

        val foodsById = foods.associateBy { it.id }
        val activeFoodIds = planningRules.asSequence()
            .filter { it.isActive && it.itemKind == PlannedItemKind.FOOD }
            .map { it.itemId }
            .filter(foodsById::containsKey)
            .toSet()
            .ifEmpty { repertoireFoodIds }
        val activeFoods = activeFoodIds.mapNotNull(foodsById::get)
        val activeRetailers = activeFoods.mapNotNull { it.retailer.normalized() }.toSet()
        val categoryCounts = activeFoods.groupingBy { it.category }.eachCount()
        val totals = weeklyTotals(
            plannedMeals.filter { it.planWeek == PlanWeek.CURRENT }, foodsById, dishesById
        )
        val deficits = Deficits.from(recommendation, totals)

        return foods.asSequence()
            .filter {
                it.id !in repertoireFoodIds && it.id !in excludedFoodIds &&
                    it.hasComparableNutrition()
            }
            .filter { activeRetailers.isEmpty() || it.retailer.normalized() in activeRetailers }
            .map { candidate ->
                val categoryNovelty = when {
                    candidate.category == FoodCategory.OTHER -> 0.0
                    categoryCounts[candidate.category] == null -> 0.35
                    else -> 0.10 / max(1, categoryCounts.getValue(candidate.category))
                }
                FoodSuggestion(
                    food = candidate,
                    reason = reason(candidate, activeFoods, categoryCounts, deficits),
                    score = nutritionalUtility(candidate, recommendation, deficits) +
                        categoryNovelty + affinity(candidate, activeFoods) +
                        if (candidate.unitAmount != null && candidate.unitName != null) 0.05 else 0.0
                )
            }
            .filter { it.score >= 0.18 }
            .sortedWith(compareByDescending<FoodSuggestion> { it.score }.thenBy { it.food.name.lowercase() })
            .distinctBy { equivalenceKey(it.food) }
            .take(limit)
            .toList()
    }

    private fun nutritionalUtility(
        food: Food, recommendation: Recommendation?, deficits: Deficits
    ): Double {
        if (recommendation == null) return if ((food.fiberGrams ?: 0.0) >= 3.0) 0.08 else 0.0
        val servingFactor = (food.unitAmount ?: 100.0).coerceIn(30.0, 250.0) / 100.0
        fun contribution(value: Double?, target: Int): Double =
            ((value ?: 0.0) * servingFactor / target.coerceAtLeast(1)).coerceIn(0.0, 0.35) / 0.35
        return deficits.calories * contribution(food.calories, recommendation.calories) * 0.05 +
            deficits.protein * contribution(food.proteinGrams, recommendation.proteinGrams) * 0.55 +
            deficits.carbohydrate * contribution(food.carbohydrateGrams, recommendation.carbohydrateGrams) * 0.10 +
            deficits.fat * contribution(food.fatGrams, recommendation.fatGrams) * 0.10 +
            deficits.fiber * (((food.fiberGrams ?: 0.0) * servingFactor / 25.0)
                .coerceIn(0.0, 0.35) / 0.35) * 0.20
    }

    private fun affinity(candidate: Food, activeFoods: List<Food>): Double {
        val sameSubcategory = candidate.subcategory.normalized()?.let { value ->
            activeFoods.any { it.subcategory.normalized() == value }
        } == true
        val sameFamily = candidate.family.normalized()?.let { value ->
            activeFoods.any { it.family.normalized() == value }
        } == true
        return when { sameSubcategory -> 0.20; sameFamily -> 0.10; else -> 0.0 }
    }

    private fun reason(
        food: Food,
        activeFoods: List<Food>,
        categoryCounts: Map<FoodCategory, Int>,
        deficits: Deficits
    ): String {
        val nutrientReasons = listOf(
            Triple(deficits.protein, food.proteinGrams ?: 0.0, "Puede ayudarte a cubrir la proteína del menú."),
            Triple(deficits.fiber, food.fiberGrams ?: 0.0, "Puede ayudarte a aumentar la fibra del menú."),
            Triple(deficits.carbohydrate, food.carbohydrateGrams ?: 0.0, "Puede ayudarte a completar los hidratos del menú."),
            Triple(deficits.fat, food.fatGrams ?: 0.0, "Puede ayudarte a completar las grasas del menú.")
        )
        nutrientReasons.filter { it.second >= 3.0 }
            .maxByOrNull { it.first * it.second }
            ?.takeIf { it.first >= 0.12 }
            ?.let { return it.third }
        if (food.category != FoodCategory.OTHER && categoryCounts[food.category] == null) {
            return "Aporta más variedad con " + food.category.label.lowercase() + "."
        }
        val sharedSubcategory = food.subcategory.normalized()?.let { subcategory ->
            activeFoods.any { it.subcategory.normalized() == subcategory }
        } == true
        if (sharedSubcategory) {
            return "Ya utilizas otros productos de la subcategoría " +
                food.subcategory.orEmpty().lowercase() + "."
        }
        val sharedFamily = food.family.normalized()?.let { family ->
            activeFoods.any { it.family.normalized() == family }
        } == true
        if (sharedFamily) {
            return "Ya utilizas otros productos de la familia " +
                food.family.orEmpty().lowercase() + "."
        }
        return "Puede aportar más variedad a tu repertorio habitual."
    }

    private fun equivalenceKey(food: Food): String = listOf(
        food.retailer.normalized().orEmpty(),
        food.subcategory.normalized() ?: food.family.normalized().orEmpty(),
        food.category.name,
        food.name.lowercase()
            .replace(Regex("\\b\\d+(?:[.,]\\d+)?\\s*(?:g|kg|ml|l)\\b"), "")
            .replace(Regex("\\s+"), " ").trim()
    ).joinToString("|")

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

    private data class Deficits(
        val calories: Double, val protein: Double, val carbohydrate: Double,
        val fat: Double, val fiber: Double
    ) {
        companion object {
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
