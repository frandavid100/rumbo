package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation

/** A diagnostic describes the best proven day we inspected; it is not a proof of impossibility. */
data class CulinarilySatisfactoryDayDiagnostic(
    val issues: List<CulinarySatisfactionIssue>,
    val compatibleCompanionAlreadyAvailable: Boolean,
    val unavailablePreferredRoles: Set<CulinaryRole>,
    val searchStatus: ConstraintSearchStatus
)

data class CulinarilySatisfactoryDaySearchResult(
    val witness: CertifiedDayWitness?,
    val diagnostic: CulinarilySatisfactoryDayDiagnostic?,
    val progressWitness: CertifiedDayWitness? = null
)

/**
 * Certified level-3 search.
 *
 * Revalidation is always first. A directed deterministic shortlist search then
 * tests nearby/representative compositions without touching the persisted
 * COMPLETE witness. Expensive deep repair and broad generation are fallbacks.
 * Exhausting bounded searches is SEARCH_INCONCLUSIVE, never evidence that the
 * repertoire lacks a level-3 day.
 */
object CulinarilySatisfactoryDaySearch {
    fun find(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        baselineCompleteWitness: CertifiedDayWitness? = null,
        portionContext: PortionContext = PortionContext.GENERAL_ADULT
    ): CulinarilySatisfactoryDaySearchResult {
        val constraints = MenuConstraintModel.fromLegacyData(rules, foodsById, mealShares)
        if (constraints.structuralViolations.isNotEmpty()) {
            return CulinarilySatisfactoryDaySearchResult(null, null)
        }

        var bestWitness: CertifiedDayWitness? = null
        var bestEvaluation: CulinaryDaySatisfaction? = null
        var bestScore = Double.POSITIVE_INFINITY

        fun registerComplete(candidate: CertifiedDayWitness): CertifiedDayWitness? {
            val complete = candidate.copy(
                level = CertifiedDayLevel.COMPLETE,
                fingerprint = candidate.meals.hashCode()
            )
            if (!CertifiedDayWitnessEvaluator.isComplete(
                    complete, rules, foodsById, dishesById, recommendation, mealShares
                )
            ) return null

            val level3 = complete.copy(level = CertifiedDayLevel.CULINARILY_SATISFACTORY)
            if (CulinarySatisfactionEvaluator.isCulinarilySatisfactory(
                    level3, rules, foodsById, dishesById, recommendation, mealShares, portionContext
                )
            ) return level3

            val evaluation = CulinarySatisfactionEvaluator.evaluateDay(
                complete.day,
                complete.meals,
                foodsById,
                dishesById,
                recommendation,
                mealShares,
                portionContext
            )
            val score = diagnosticScore(evaluation)
            if (score < bestScore) {
                bestScore = score
                bestWitness = complete
                bestEvaluation = evaluation
            }
            return null
        }

        val baseline = baselineCompleteWitness?.takeIf { it.isStructurallyValid() }
        baseline?.let { registerComplete(it)?.let { witness -> return success(witness) } }

        // First search small deterministic subsets. This does not mutate or
        // replace the saved COMPLETE witness. Any candidate is immediately
        // revalidated against the full rules before certification.
        CulinaryLevel3ShortlistSearch.find(
            rules = rules,
            foodsById = foodsById,
            dishesById = dishesById,
            recommendation = recommendation,
            mealShares = mealShares,
            baselineCompleteWitness = baseline,
            portionContext = portionContext
        )?.let { shortlisted ->
            registerComplete(shortlisted)?.let { return success(it) }
        }

        // This method runs automatically from the main screen. Deep repair,
        // exhaustive composition search and seeded generation previously ran
        // here in sequence and could occupy a phone for minutes. Exhausting the
        // directed shortlist is enough for this automatic check; failure stays
        // SEARCH_INCONCLUSIVE instead of blocking the interface.

        return CulinarilySatisfactoryDaySearchResult(
            witness = null,
            diagnostic = bestEvaluation?.let {
                diagnose(
                    it,
                    rules,
                    foodsById,
                    ConstraintSearchStatus.SEARCH_INCONCLUSIVE
                )
            },
            progressWitness = bestWitness
        )
    }

    fun diagnose(
        evaluation: CulinaryDaySatisfaction,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        status: ConstraintSearchStatus = ConstraintSearchStatus.SEARCH_INCONCLUSIVE
    ): CulinarilySatisfactoryDayDiagnostic {
        val activeRules = rules.filter {
            it.itemKind == PlannedItemKind.FOOD && it.isActive &&
                it.frequency != PlanningFrequency.NEVER &&
                foodsById[it.itemId]?.hasComparableNutrition() == true
        }
        var availableCompanion = false
        val unavailable = linkedSetOf<CulinaryRole>()

        evaluation.issues
            .filter { it.kind == CulinarySatisfactionIssueKind.SOFT_RELATION_UNSATISFIED }
            .forEach { issue ->
                val issueRole = issue.roles.singleOrNull() ?: return@forEach
                val targets = CulinarySoftPolicy.preferredCompanions(issueRole)
                if (targets.isEmpty()) return@forEach

                val hasAny = activeRules.any { rule ->
                    issue.mealType in rule.allowedMealTypes &&
                        foodsById[rule.itemId]?.let(CulinaryPolicy::roles)
                            ?.any(targets::contains) == true
                }
                if (hasAny) {
                    availableCompanion = true
                    return@forEach
                }

                // A failed bounded search is not proof that the repertoire lacks
                // a companion. We only expose an unavailable role as actionable
                // when the source occurrence itself is unavoidable in this meal
                // and every culinary role it can perform has a non-empty soft
                // companion requirement. Optional or multi-purpose foods can be
                // omitted/reassigned by another valid composition, so asking the
                // user to add food would be a false inference.
                val sourceId = issue.foodId ?: return@forEach
                val sourceFood = foodsById[sourceId] ?: return@forEach
                val sourceMandatory = activeRules.any { rule ->
                    rule.itemId == sourceId &&
                        rule.frequency == PlanningFrequency.ALWAYS &&
                        issue.mealType in rule.allowedMealTypes
                }
                if (!sourceMandatory) return@forEach

                val sourceRoles = CulinaryPolicy.roles(sourceFood)
                if (sourceRoles.isEmpty()) return@forEach
                val requiredTargetSets = sourceRoles.map(CulinarySoftPolicy::preferredCompanions)
                if (requiredTargetSets.any { it.isEmpty() }) return@forEach
                val union = requiredTargetSets.flatten().toSet()
                val anySourceRoleCanBeSatisfied = requiredTargetSets.any { roleTargets ->
                    activeRules.any { rule ->
                        issue.mealType in rule.allowedMealTypes && rule.itemId != sourceId &&
                            foodsById[rule.itemId]?.let(CulinaryPolicy::roles)
                                ?.any(roleTargets::contains) == true
                    }
                }
                if (!anySourceRoleCanBeSatisfied) unavailable += union
            }

        return CulinarilySatisfactoryDayDiagnostic(
            issues = evaluation.issues,
            compatibleCompanionAlreadyAvailable = availableCompanion,
            unavailablePreferredRoles = unavailable,
            searchStatus = status
        )
    }

    private fun success(witness: CertifiedDayWitness): CulinarilySatisfactoryDaySearchResult =
        CulinarilySatisfactoryDaySearchResult(
            witness = witness,
            diagnostic = CulinarilySatisfactoryDayDiagnostic(
                issues = emptyList(),
                compatibleCompanionAlreadyAvailable = false,
                unavailablePreferredRoles = emptySet(),
                searchStatus = ConstraintSearchStatus.FEASIBLE
            ),
            progressWitness = witness.copy(level = CertifiedDayLevel.COMPLETE)
        )

    private fun diagnosticScore(evaluation: CulinaryDaySatisfaction): Double =
        evaluation.issues.sumOf { issue ->
            when (issue.kind) {
                CulinarySatisfactionIssueKind.HARD_ROLE_ASSIGNMENT_INVALID -> 1_000_000.0
                CulinarySatisfactionIssueKind.ROLE_UNRESOLVED -> 500_000.0
                CulinarySatisfactionIssueKind.SOFT_RELATION_UNSATISFIED -> 100_000.0
                CulinarySatisfactionIssueKind.QUANTITY_OUTSIDE_SATISFACTORY_RANGE -> 10_000.0
            }
        } + evaluation.issues.size
}
