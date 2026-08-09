package es.david.rumbo.logic

import es.david.rumbo.model.Food
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
