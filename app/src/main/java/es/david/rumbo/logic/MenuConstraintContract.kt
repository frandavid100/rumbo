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
import es.david.rumbo.model.WeekDay

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
    MISSING_MEAL_COVERAGE,
    MISSING_REQUIRED_COMPANION
}

data class ConstraintViolation(
    val kind: ConstraintViolationKind,
    val message: String,
    val mealType: MealType? = null,
    val itemIds: Set<Long> = emptySet()
)

/** Exact generated menu plus the deterministic seed that produced it. */
data class MenuWitness(
    val seed: Long,
    val meals: List<PlannedMeal>,
    val fingerprint: Int = meals.hashCode()
)

/**
 * Shared constraint model consumed by both repertoire evaluation and menu generation.
 * Catalogue/importer details are deliberately absent: foods expose canonical culinary
 * roles and the central CulinaryPolicy supplies their hard rules.
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
                    foodsById[it.itemId]?.hasComparableNutrition() == true
            }
            val activeMealTypes = MealType.entries.filterTo(mutableSetOf()) {
                (mealShares[it] ?: defaultShares.getValue(it)) > 0.0
            }
            val violations = buildList {
                if (activeRules.isEmpty()) {
                    add(
                        ConstraintViolation(
                            ConstraintViolationKind.NO_ACTIVE_RULES,
                            "No hay alimentos activos y correctamente programados."
                        )
                    )
                }
                activeMealTypes.forEach { mealType ->
                    val mealRules = activeRules.filter { rule ->
                        mealType in rule.allowedMealTypes ||
                            rule.requiredSlots().any { it.mealType == mealType }
                    }
                    if (mealRules.isEmpty()) {
                        add(
                            ConstraintViolation(
                                ConstraintViolationKind.MISSING_MEAL_COVERAGE,
                                "No hay opciones para ${mealType.label.lowercase()}.",
                                mealType
                            )
                        )
                    }

                    val allChoices = mealRules.mapNotNull { rule ->
                        foodsById[rule.itemId]?.let(CulinaryPolicy::roles)
                    }
                    mealRules.filter { it.frequency == PlanningFrequency.ALWAYS }.forEach { required ->
                        val requiredChoices = foodsById[required.itemId]
                            ?.let(CulinaryPolicy::roles)
                            .orEmpty()
                        if (requiredChoices.isNotEmpty()) {
                            val everyUseImpossible = requiredChoices.all { role ->
                                val requirements = CulinaryPolicy.policy(role).requiredRoles
                                requirements.isNotEmpty() && requirements.any { needed ->
                                    allChoices.none { needed in it }
                                }
                            }
                            if (everyUseImpossible) {
                                add(
                                    ConstraintViolation(
                                        ConstraintViolationKind.MISSING_REQUIRED_COMPANION,
                                        "Hay un alimento obligatorio que necesita un acompañamiento culinario en " +
                                            mealType.label.lowercase() +
                                            ", pero no existe ninguna opción programada.",
                                        mealType,
                                        setOf(required.itemId)
                                    )
                                )
                            }
                        }
                    }
                }
            }
            return MenuConstraintModel(
                activeRules = activeRules,
                activeMealTypes = activeMealTypes,
                mealShares = mealShares,
                structuralViolations = violations.distinct()
            )
        }
    }
}

/** Shared generator entry point used by evaluator and generator contract tests. */
fun WeeklyMenuGenerator.generate(
    constraints: MenuConstraintModel,
    currentMeals: List<PlannedMeal>,
    history: List<MenuHistoryEntry>,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    recommendation: Recommendation,
    seed: Long = 11L,
    days: Set<WeekDay> = WeekDay.entries.toSet()
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
        seed = seed,
        days = days
    )
}

fun MenuWitness.reproduce(
    constraints: MenuConstraintModel,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    recommendation: Recommendation
): GeneratedWeeklyMenu {
    val witnessDays = meals.flatMapTo(mutableSetOf()) { it.days }
    require(witnessDays.isNotEmpty()) { "El testigo no contiene ningún día." }
    return WeeklyMenuGenerator.generate(
        constraints = constraints,
        currentMeals = emptyList(),
        history = emptyList(),
        foodsById = foodsById,
        dishesById = dishesById,
        recommendation = recommendation,
        seed = seed,
        days = witnessDays
    )
}
