package es.david.rumbo.logic

import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealDistributionPolicy
import es.david.rumbo.model.MealType
import es.david.rumbo.model.MenuHistoryEntry
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation

/**
 * Result of the feasibility search performed for a repertoire.
 *
 * INSUFFICIENT is reserved for contradictions that are proved without relying on
 * the heuristic generator. SEARCH_INCONCLUSIVE means that the bounded search did
 * not find an acceptable witness and therefore must never be presented as a proof
 * that no witness exists.
 */
enum class ConstraintSearchStatus {
    FEASIBLE,
    SEARCH_INCONCLUSIVE,
    INSUFFICIENT
}

enum class ConstraintViolationKind {
    NO_ACTIVE_RULES,
    MISSING_MEAL_COVERAGE
}

data class ConstraintViolation(
    val kind: ConstraintViolationKind,
    val message: String,
    val mealType: MealType? = null
)

/** Exact generated menu plus the deterministic seed that produced it. */
data class MenuWitness(
    val seed: Long,
    val meals: List<PlannedMeal>,
    val fingerprint: Int = meals.hashCode()
)

/**
 * Compatibility constraint model for the current catalogue schema.
 *
 * This deliberately contains no importer/classifier concepts. It normalises the
 * existing planning rules once and is consumed by both repertoire evaluation and
 * menu generation. Future catalogue roles/policies can be adapted into this model
 * without changing the evaluator/generator contract.
 */
data class MenuConstraintModel(
    val activeRules: List<PlanningRule>,
    val activeMealTypes: Set<MealType>,
    val mealShares: Map<MealType, Double>,
    val structuralViolations: List<ConstraintViolation>
) {
    companion object {
        private val defaultShares = MealDistributionPolicy.defaults

        fun fromLegacyData(
            rules: List<PlanningRule>,
            foodsById: Map<Long, Food>,
            mealShares: Map<MealType, Double> = defaultShares
        ): MenuConstraintModel {
            val activeRules = rules.filter {
                it.itemKind == PlannedItemKind.FOOD &&
                    it.isActive && it.frequency != PlanningFrequency.NEVER && it.isValid() &&
                    foodsById[it.itemId]?.hasComparableNutrition() == true &&
                    foodsById[it.itemId]?.let(CulinaryPolicy::standaloneAllowed) != false
            }
            val activeMealTypes = MealType.entries.filterTo(mutableSetOf()) {
                (mealShares[it] ?: defaultShares.getValue(it)) > 0.0
            }
            val violations = buildList {
                if (activeRules.isEmpty()) {
                    add(ConstraintViolation(
                        ConstraintViolationKind.NO_ACTIVE_RULES,
                        "No hay alimentos activos y correctamente programados."
                    ))
                }
                activeMealTypes.forEach { mealType ->
                    val alternatives = activeRules.count { rule ->
                        mealType in rule.allowedMealTypes ||
                            rule.requiredSlots().any { it.mealType == mealType }
                    }
                    if (alternatives == 0) {
                        add(ConstraintViolation(
                            ConstraintViolationKind.MISSING_MEAL_COVERAGE,
                            "No hay opciones para ${mealType.label.lowercase()}.",
                            mealType
                        ))
                    }
                }
            }
            return MenuConstraintModel(
                activeRules = activeRules,
                activeMealTypes = activeMealTypes,
                mealShares = mealShares,
                structuralViolations = violations
            )
        }
    }
}

/**
 * Shared generator entry point. The old signature remains untouched for source
 * compatibility; new evaluator/generator contract tests use this overload.
 */
fun WeeklyMenuGenerator.generate(
    constraints: MenuConstraintModel,
    currentMeals: List<PlannedMeal>,
    history: List<MenuHistoryEntry>,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    recommendation: Recommendation,
    seed: Long = 11L
): GeneratedWeeklyMenu {
    require(constraints.structuralViolations.isEmpty()) {
        constraints.structuralViolations.joinToString(" ") { it.message }
    }
    return generate(
        currentMeals = currentMeals,
        rules = constraints.activeRules,
        history = history,
        foodsById = foodsById,
        dishesById = dishesById,
        recommendation = recommendation,
        mealShares = constraints.mealShares,
        seed = seed
    )
}

fun MenuWitness.reproduce(
    constraints: MenuConstraintModel,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    recommendation: Recommendation
): GeneratedWeeklyMenu = WeeklyMenuGenerator.generate(
    constraints = constraints,
    currentMeals = emptyList(),
    history = emptyList(),
    foodsById = foodsById,
    dishesById = dishesById,
    recommendation = recommendation,
    seed = seed
)
