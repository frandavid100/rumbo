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
import es.david.rumbo.model.WeekDay

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
 * Order is contractually important: revalidate/promote the persisted COMPLETE
 * witness, repair it deterministically, then search a few relevant shortlists,
 * and only afterwards widen to the whole repertoire and seeded generation.
 * Exhausting these bounded searches is SEARCH_INCONCLUSIVE, never a proof that
 * the repertoire lacks a level-3 day.
 */
object CulinarilySatisfactoryDaySearch {
    private val fallbackSeeds = listOf(
        11L, 37L, 89L, 131L, 197L, 251L, 313L, 401L
    )

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

        baselineCompleteWitness
            ?.takeIf { it.isStructurallyValid() }
            ?.let { baseline ->
                registerComplete(baseline)?.let { return success(it) }
                CulinarilySatisfactoryWitnessRepair.find(
                    baseline.copy(level = CertifiedDayLevel.COMPLETE),
                    rules,
                    foodsById,
                    dishesById,
                    recommendation,
                    mealShares,
                    portionContext
                )?.let { repaired ->
                    registerComplete(repaired)?.let { return success(it) }
                }
            }

        // The small-repertoire composition search is demonstrably more reliable
        // when a large repertoire contains many interchangeable alternatives.
        // Shortlisting never weakens the result: the returned day is immediately
        // revalidated here against the complete rules before it can be certified.
        CulinaryLevel3ShortlistSearch.find(
            rules = rules,
            foodsById = foodsById,
            dishesById = dishesById,
            recommendation = recommendation,
            mealShares = mealShares,
            baselineCompleteWitness = baselineCompleteWitness,
            portionContext = portionContext
        )?.let { shortlisted ->
            registerComplete(shortlisted)?.let { return success(it) }
        }

        // Widen to all optional foods only after the targeted searches. This path
        // can still discover solutions that require an unusual combination not
        // represented in a shortlist.
        CulinaryLevel3CompositionSearch.find(
            rules = rules,
            foodsById = foodsById,
            dishesById = dishesById,
            recommendation = recommendation,
            mealShares = mealShares,
            portionContext = portionContext
        )?.let { candidate ->
            registerComplete(candidate)?.let { return success(it) }
        }

        // Fallback generation only widens composition coverage. Do not run the
        // expensive repair for every seed: keep the best complete candidate and
        // repair it once at the end.
        for (seed in fallbackSeeds) {
            val generated = runCatching {
                WeeklyMenuGenerator.generate(
                    currentMeals = emptyList(),
                    rules = rules,
                    history = emptyList(),
                    foodsById = foodsById,
                    dishesById = dishesById,
                    recommendation = recommendation,
                    mealShares = mealShares,
                    seed = seed,
                    days = setOf(WeekDay.MONDAY),
                    objective = MenuGenerationObjective.COMPLETE
                )
            }.getOrNull() ?: continue

            val candidate = CertifiedDayWitness(
                level = CertifiedDayLevel.COMPLETE,
                seed = seed,
                day = WeekDay.MONDAY,
                meals = generated.meals,
                fingerprint = generated.meals.hashCode()
            )
            registerComplete(candidate)?.let { return success(it) }
        }

        bestWitness?.let { best ->
            CulinarilySatisfactoryWitnessRepair.find(
                best,
                rules,
                foodsById,
                dishesById,
                recommendation,
                mealShares,
                portionContext
            )?.let { repaired ->
                registerComplete(repaired)?.let { return success(it) }
            }
        }

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
                val targetSets = issue.roles
                    .map(CulinarySoftPolicy::preferredCompanions)
                    .filter { it.isNotEmpty() }
                targetSets.forEach { targets ->
                    val hasAny = activeRules.any { rule ->
                        issue.mealType in rule.allowedMealTypes &&
                            foodsById[rule.itemId]?.let(CulinaryPolicy::roles)
                                ?.any(targets::contains) == true
                    }
                    if (hasAny) availableCompanion = true else unavailable += targets
                }
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
