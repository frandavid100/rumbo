package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import kotlin.math.pow
import kotlin.math.sqrt

object FoodSimilarityEngine {
    fun findSimilar(source: Food, catalog: List<Food>, limit: Int = 5): List<Food> = catalog
        .asSequence()
        .filter { source.hasComparableNutrition() && it.hasComparableNutrition() }
        .filter { it.id != source.id && isCulinarilyRelated(source, it) }
        .filter { isCloseEnough(source, it) }
        .sortedBy { distance(source, it) }
        .take(limit)
        .toList()

    fun findMoreEfficient(source: Food, catalog: List<Food>, limit: Int = 5): List<Food> =
        catalog.asSequence()
            .filter { source.hasComparableNutrition() && it.hasComparableNutrition() }
            .filter { it.id != source.id && isCulinarilyRelated(source, it) }
            .map { it to efficiencyGain(source, it) }
            .filter { (candidate, gain) ->
                gain >= 0.10 && hasNoMajorQualityRegression(source, candidate)
            }
            .sortedWith(
                compareByDescending<Pair<Food, Double>> { it.second }
                    .thenBy { distance(source, it.first) }
            )
            .map { it.first }
            .take(limit)
            .toList()

    private fun efficiencyGain(source: Food, candidate: Food): Double {
        val sourceEfficiency = usefulEfficiency(source).coerceAtLeast(0.01)
        return (usefulEfficiency(candidate) - sourceEfficiency) / sourceEfficiency
    }

    private fun usefulEfficiency(food: Food): Double {
        val calories = food.calories!!.coerceAtLeast(1.0)
        val protein = food.proteinGrams!!
        val carbohydrate = food.carbohydrateGrams!!
        val fat = food.fatGrams!!
        val carbohydrateShare = (carbohydrate * 4.0 / calories).coerceIn(0.0, 1.0)
        val fatShare = (fat * 9.0 / calories).coerceIn(0.0, 1.0)
        val unsaturatedFactor = if (food.saturatedFatGrams == null || fat <= 0.0) {
            0.75
        } else {
            1.0 - (food.saturatedFatGrams / fat).coerceIn(0.0, 1.0) * 0.75
        }
        return when (food.category) {
            FoodCategory.PROTEIN -> protein * 100.0 / calories / 15.0
            FoodCategory.CARBOHYDRATE -> carbohydrateShare * (1.0 - fatShare)
            FoodCategory.FAT -> fatShare * (1.0 - carbohydrateShare) * unsaturatedFactor
            FoodCategory.FRUIT, FoodCategory.VEGETABLE ->
                (food.fiberGrams ?: 0.0) * 100.0 / calories / 4.0
            FoodCategory.OTHER -> {
                val proteinShare = protein * 4.0 / calories
                maxOf(
                    proteinShare,
                    carbohydrateShare * (1.0 - fatShare),
                    fatShare * (1.0 - carbohydrateShare) * unsaturatedFactor
                )
            }
        }
    }

    private fun hasNoMajorQualityRegression(source: Food, candidate: Food): Boolean {
        val saturatedLimit = maxOf((source.saturatedFatGrams ?: 0.0) * 1.5, 5.0)
        val saltLimit = maxOf((source.saltGrams ?: 0.0) * 1.5, 2.0)
        val sugarLimit = maxOf((source.sugarGrams ?: 0.0) * 1.5, 15.0)
        return (candidate.saturatedFatGrams ?: 0.0) <= saturatedLimit &&
            (candidate.saltGrams ?: 0.0) <= saltLimit &&
            (candidate.sugarGrams ?: 0.0) <= sugarLimit
    }

    private fun isCulinarilyRelated(first: Food, second: Food): Boolean =
        when {
            first.subcategory != null && second.subcategory != null ->
                first.subcategory.equals(second.subcategory, ignoreCase = true)
            first.family != null && second.family != null ->
                first.family.equals(second.family, ignoreCase = true)
            else -> first.category == second.category
        }

    private fun isCloseEnough(first: Food, second: Food): Boolean =
        difference(first.calories!!, second.calories!!) <= 25.0 &&
            difference(first.proteinGrams!!, second.proteinGrams!!) <= 4.0 &&
            difference(first.carbohydrateGrams!!, second.carbohydrateGrams!!) <= 6.0 &&
            difference(first.fatGrams!!, second.fatGrams!!) <= 3.0 &&
            fiberDifference(first, second) <= 3.0

    private fun distance(first: Food, second: Food): Double {
        val fiber = if (first.fiberGrams != null && second.fiberGrams != null) {
            difference(first.fiberGrams, second.fiberGrams) / 3.0
        } else {
            0.35
        }
        return sqrt(
            (difference(first.calories!!, second.calories!!) / 25.0).pow(2) +
                (difference(first.proteinGrams!!, second.proteinGrams!!) / 4.0).pow(2) +
                (difference(first.carbohydrateGrams!!, second.carbohydrateGrams!!) / 6.0).pow(2) +
                (difference(first.fatGrams!!, second.fatGrams!!) / 3.0).pow(2) + fiber.pow(2)
        )
    }

    private fun fiberDifference(first: Food, second: Food): Double =
        if (first.fiberGrams != null && second.fiberGrams != null) {
            difference(first.fiberGrams, second.fiberGrams)
        } else {
            0.0
        }

    private fun difference(first: Double, second: Double): Double = kotlin.math.abs(first - second)
}
