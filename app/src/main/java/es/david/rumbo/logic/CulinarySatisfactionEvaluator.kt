package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import es.david.rumbo.model.resolvedGrams
import es.david.rumbo.model.totalWeightGrams

enum class CulinarySatisfactionIssueKind {
    ROLE_UNRESOLVED,
    QUANTITY_OUTSIDE_SATISFACTORY_RANGE,
    SOFT_RELATION_UNSATISFIED,
    DAILY_REPETITION_DISCOURAGED,
    HARD_ROLE_ASSIGNMENT_INVALID
}

data class CulinarySatisfactionIssue(
    val kind: CulinarySatisfactionIssueKind,
    val mealType: MealType,
    val foodId: Long? = null,
    val foodName: String? = null,
    val grams: Double? = null,
    val roles: Set<CulinaryRole> = emptySet(),
    val message: String
)

data class CulinaryMealSatisfaction(
    val mealType: MealType,
    val satisfactory: Boolean,
    val assignedRoles: List<Pair<Long, CulinaryRole>> = emptyList(),
    val issues: List<CulinarySatisfactionIssue> = emptyList()
)

data class CulinaryDaySatisfaction(
    val satisfactory: Boolean,
    val meals: List<CulinaryMealSatisfaction>,
    val issues: List<CulinarySatisfactionIssue> = meals.flatMap { it.issues }
)

/**
 * Level-3 culinary evaluator.
 *
 * It does not alter level 1/2 validity. It asks whether one concrete role can be
 * assigned to every food occurrence so that the existing hard role rules hold,
 * every v1 PREFER relation is satisfied and every quantity lies inside the
 * contextual satisfactory interval of the role actually performed.
 */
object CulinarySatisfactionEvaluator {
    private data class Occurrence(
        val food: Food,
        val grams: Double,
        val roles: Set<CulinaryRole>
    )

    private data class Assignment(
        val occurrence: Occurrence,
        val role: CulinaryRole
    )

    fun isCulinarilySatisfactory(
        witness: CertifiedDayWitness,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        portionContext: PortionContext = PortionContext.GENERAL_ADULT
    ): Boolean {
        if (witness.level != CertifiedDayLevel.CULINARILY_SATISFACTORY) return false
        val complete = witness.copy(level = CertifiedDayLevel.COMPLETE)
        if (!CertifiedDayWitnessEvaluator.isComplete(
                complete, rules, foodsById, dishesById, recommendation, mealShares
            )
        ) return false
        return evaluateDay(
            witness.day,
            witness.meals,
            foodsById,
            dishesById,
            recommendation,
            mealShares,
            portionContext
        ).satisfactory
    }

    fun evaluateDay(
        day: WeekDay,
        meals: List<PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        portionContext: PortionContext = PortionContext.GENERAL_ADULT
    ): CulinaryDaySatisfaction {
        val results = meals.filter { day in it.days }.map { meal ->
            evaluateMeal(
                day,
                meal,
                foodsById,
                dishesById,
                recommendation,
                mealShares,
                portionContext
            )
        }
        val repetitions = results
            .flatMap { meal -> meal.assignedRoles.map { (foodId, role) -> Triple(foodId, role, meal.mealType) } }
            .groupBy { it.first }
            .mapNotNull { (foodId, occurrences) ->
                val maximum = CulinarySoftPolicy.maximumDailyOccurrences(occurrences.map { it.second })
                    ?: return@mapNotNull null
                if (occurrences.size <= maximum) return@mapNotNull null
                val food = foodsById[foodId]
                CulinarySatisfactionIssue(
                    kind = CulinarySatisfactionIssueKind.DAILY_REPETITION_DISCOURAGED,
                    mealType = occurrences[maximum].third,
                    foodId = foodId,
                    foodName = food?.name,
                    roles = occurrences.mapTo(linkedSetOf()) { it.second },
                    message = "${food?.name ?: "El alimento"} se repite demasiado dentro del mismo día."
                )
            }
        val finalResults = if (repetitions.isEmpty() || results.isEmpty()) results else {
            val issuesByMeal = repetitions.groupBy { it.mealType }
            results.map { result ->
                val extra = issuesByMeal[result.mealType].orEmpty()
                if (extra.isEmpty()) result else result.copy(
                    satisfactory = false,
                    issues = result.issues + extra
                )
            }
        }
        return CulinaryDaySatisfaction(
            satisfactory = finalResults.isNotEmpty() && finalResults.all { it.satisfactory },
            meals = finalResults
        )
    }

    fun evaluateMeal(
        day: WeekDay,
        meal: PlannedMeal,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        portionContext: PortionContext = PortionContext.GENERAL_ADULT
    ): CulinaryMealSatisfaction {
        val occurrences = occurrences(day, meal, foodsById, dishesById)
        if (occurrences.isEmpty()) {
            return CulinaryMealSatisfaction(
                meal.type,
                false,
                issues = listOf(
                    CulinarySatisfactionIssue(
                        CulinarySatisfactionIssueKind.ROLE_UNRESOLVED,
                        meal.type,
                        message = "La comida no contiene ocurrencias culinarias evaluables."
                    )
                )
            )
        }

        val roleless = occurrences.filter { it.roles.isEmpty() }
        if (roleless.isNotEmpty()) {
            return CulinaryMealSatisfaction(
                meal.type,
                false,
                issues = roleless.map { occurrence ->
                    CulinarySatisfactionIssue(
                        kind = CulinarySatisfactionIssueKind.ROLE_UNRESOLVED,
                        mealType = meal.type,
                        foodId = occurrence.food.id,
                        foodName = occurrence.food.name,
                        grams = occurrence.grams,
                        message = "${occurrence.food.name} no tiene un rol culinario resoluble para certificar el nivel 3."
                    )
                }
            )
        }

        val eligibleRoles = occurrences.map { occurrence ->
            occurrence.roles.filterTo(linkedSetOf()) { role ->
                meal.type in CulinaryPolicy.policy(role).suggestedMealTypes &&
                PortionPolicyResolver.resolve(
                    occurrence.food,
                    role,
                    meal.type,
                    recommendation,
                    mealShares,
                    portionContext
                ).isSatisfactory(occurrence.grams)
            }
        }
        if (eligibleRoles.any { it.isEmpty() }) {
            val issues = occurrences.indices.filter { eligibleRoles[it].isEmpty() }.map { index ->
                val occurrence = occurrences[index]
                CulinarySatisfactionIssue(
                    kind = CulinarySatisfactionIssueKind.QUANTITY_OUTSIDE_SATISFACTORY_RANGE,
                    mealType = meal.type,
                    foodId = occurrence.food.id,
                    foodName = occurrence.food.name,
                    grams = occurrence.grams,
                    roles = occurrence.roles,
                    message = "La cantidad de ${occurrence.food.name} (${formatGrams(occurrence.grams)}) no entra en la zona satisfactoria de ninguno de sus usos culinarios posibles."
                )
            }
            return CulinaryMealSatisfaction(meal.type, false, issues = issues)
        }

        val chosen = ArrayList<Assignment>(occurrences.size)
        var firstSoftInvalid: List<Assignment>? = null

        fun visit(index: Int): List<Assignment>? {
            if (index == occurrences.size) {
                val snapshot = chosen.toList()
                val singletonChoices = snapshot.map { setOf(it.role) }
                if (!CulinaryPolicy.hasValidRoleAssignment(singletonChoices)) return null
                if (!softRelationsSatisfied(snapshot)) {
                    if (firstSoftInvalid == null) firstSoftInvalid = snapshot
                    return null
                }
                return snapshot
            }

            for (role in eligibleRoles[index]) {
                val max = CulinaryPolicy.policy(role).maxPerMeal
                if (max != null && chosen.count { it.role == role } >= max) continue
                chosen += Assignment(occurrences[index], role)
                val result = visit(index + 1)
                if (result != null) return result
                chosen.removeAt(chosen.lastIndex)
            }
            return null
        }

        val satisfying = visit(0)
        if (satisfying != null) {
            return CulinaryMealSatisfaction(
                mealType = meal.type,
                satisfactory = true,
                assignedRoles = satisfying.map { it.occurrence.food.id to it.role }
            )
        }

        val softCandidate = firstSoftInvalid
        if (softCandidate != null) {
            val missing = missingSoftRelations(softCandidate)
            return CulinaryMealSatisfaction(
                meal.type,
                false,
                assignedRoles = softCandidate.map { it.occurrence.food.id to it.role },
                issues = missing.map { (assignment, targets) ->
                    CulinarySatisfactionIssue(
                        kind = CulinarySatisfactionIssueKind.SOFT_RELATION_UNSATISFIED,
                        mealType = meal.type,
                        foodId = assignment.occurrence.food.id,
                        foodName = assignment.occurrence.food.name,
                        grams = assignment.occurrence.grams,
                        roles = setOf(assignment.role),
                        message = "${assignment.role.label} prefiere acompañarse de ${targets.joinToString(" o ") { it.label.lowercase() }}."
                    )
                }
            )
        }

        return CulinaryMealSatisfaction(
            meal.type,
            false,
            issues = listOf(
                CulinarySatisfactionIssue(
                    CulinarySatisfactionIssueKind.HARD_ROLE_ASSIGNMENT_INVALID,
                    meal.type,
                    message = "No existe una asignación de roles que mantenga válidas las reglas culinarias duras de la comida."
                )
            )
        )
    }

    private fun occurrences(
        day: WeekDay,
        meal: PlannedMeal,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): List<Occurrence> = buildList {
        meal.items.forEach foodLoop@ { item ->
            val food = foodsById[item.foodId] ?: return@foodLoop
            add(
                Occurrence(
                    food = food,
                    grams = meal.resolvedGrams(item, day),
                    roles = CulinaryPolicy.roles(food)
                )
            )
        }
        meal.dishes.forEach dishLoop@ { plannedDish ->
            val dish = dishesById[plannedDish.dishId] ?: return@dishLoop
            val total = dish.totalWeightGrams()
            if (total <= 0.0) return@dishLoop
            val factor = meal.resolvedGrams(plannedDish, day) / total
            dish.ingredients.forEach ingredientLoop@ { ingredient ->
                val food = foodsById[ingredient.foodId] ?: return@ingredientLoop
                add(
                    Occurrence(
                        food = food,
                        grams = ingredient.grams * factor,
                        roles = CulinaryPolicy.roles(food)
                    )
                )
            }
        }
    }

    private fun softRelationsSatisfied(assignments: List<Assignment>): Boolean =
        missingSoftRelations(assignments).isEmpty()

    private fun missingSoftRelations(
        assignments: List<Assignment>
    ): List<Pair<Assignment, Set<CulinaryRole>>> {
        val present = assignments.mapTo(mutableSetOf()) { it.role }
        return assignments.mapNotNull { assignment ->
            val targets = CulinarySoftPolicy.preferredCompanions(assignment.role)
            (assignment to targets).takeIf { targets.isNotEmpty() && targets.none(present::contains) }
        }
    }

    private fun formatGrams(value: Double): String =
        if (value % 1.0 == 0.0) "${value.toInt()} g" else "%.1f g".format(value)
}
