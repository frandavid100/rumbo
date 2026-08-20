package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation

/** Finds a distinct day, or a distinct single-meal composition, without lowering certification. */
object CertifiedDayVariantGenerator {
    private val offsets = listOf(
        26L, 78L, 120L, 186L, 240L, 300L, 390L, 498L, 600L, 696L,
        810L, 912L, 1020L, 1128L, 1230L, 1338L, 1440L, 1548L, 1650L, 1758L
    )

    fun find(
        current: CertifiedDayWitness,
        mealType: MealType? = null,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): CertifiedDayWitness? {
        val objective = if (current.level == CertifiedDayLevel.VIABLE) {
            MenuGenerationObjective.VIABLE
        } else MenuGenerationObjective.COMPLETE
        offsets.forEach { offset ->
            val seed = current.seed + offset
            val generated = runCatching {
                WeeklyMenuGenerator.generate(
                    currentMeals = emptyList(), rules = rules, history = emptyList(),
                    foodsById = foodsById, dishesById = dishesById,
                    recommendation = recommendation, mealShares = mealShares,
                    seed = seed, days = setOf(current.day), objective = objective
                )
            }.getOrNull() ?: return@forEach
            val rawMeals = if (mealType == null) {
                generated.meals
            } else {
                val replacement = generated.meals.singleOrNull { it.type == mealType }
                    ?: return@forEach
                current.meals.map { if (it.type == mealType) replacement else it }
            }
            if (rawMeals.hashCode() == current.meals.hashCode()) return@forEach
            val optimized = runCatching {
                MealQuantityOptimizer.optimize(
                    rawMeals, foodsById, dishesById, recommendation,
                    days = setOf(current.day), mealShares = mealShares
                ).meals
            }.getOrNull() ?: return@forEach
            val candidate = current.copy(seed = seed, meals = optimized, fingerprint = optimized.hashCode())
            if (candidate.fingerprint == current.fingerprint) return@forEach
            if (keepsLevel(candidate, rules, foodsById, dishesById, recommendation, mealShares)) {
                return candidate
            }
        }
        return null
    }

    private fun keepsLevel(
        candidate: CertifiedDayWitness,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): Boolean = when (candidate.level) {
        CertifiedDayLevel.VIABLE -> CertifiedDayWitnessEvaluator.isViable(
            candidate, rules, foodsById, dishesById, recommendation, mealShares
        )
        CertifiedDayLevel.COMPLETE -> CertifiedDayWitnessEvaluator.isComplete(
            candidate, rules, foodsById, dishesById, recommendation, mealShares
        )
        CertifiedDayLevel.CULINARILY_SATISFACTORY ->
            CulinarySatisfactionEvaluator.isCulinarilySatisfactory(
                candidate, rules, foodsById, dishesById, recommendation, mealShares
            )
    }
}
