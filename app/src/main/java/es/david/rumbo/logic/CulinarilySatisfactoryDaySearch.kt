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
    val searchStatus: ConstraintSearchStatus,
    val dependencyOpportunity: CulinaryDependencyOpportunity? = null
)

data class CulinaryDependencyOpportunity(
    val sourceFoodId: Long,
    val sourceFoodName: String,
    val sourceRole: CulinaryRole,
    val requiredRole: CulinaryRole,
    val mealType: MealType,
    val existingCompatibleFoodName: String? = null,
    val hardRequirement: Boolean
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

        // If the directed composition search did not solve the case, try a deep
        // local repair of the previous COMPLETE witness.
        baseline?.let { source ->
            CulinarilySatisfactoryWitnessRepair.find(
                source.copy(level = CertifiedDayLevel.COMPLETE),
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

        // Widen to all optional foods only after the targeted paths. This can
        // discover unusual combinations absent from the shortlists.
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

        // Seeded generation is the broadest fallback. Keep its best COMPLETE
        // candidate and repair only once rather than once per seed.
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
            if (baseline?.fingerprint != best.fingerprint) {
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
            searchStatus = status,
            dependencyOpportunity = findDependencyOpportunity(activeRules, foodsById)
        )
    }

    private data class DependencyCandidate(
        val opportunity: CulinaryDependencyOpportunity,
        val sourceMealCount: Int,
        val hasExistingFood: Boolean
    )

    /**
     * Finds a general role dependency that the current meal permissions cannot satisfy.
     * Food names never participate in the decision: they are carried only for the UI.
     */
    private fun findDependencyOpportunity(
        activeRules: List<PlanningRule>,
        foodsById: Map<Long, Food>
    ): CulinaryDependencyOpportunity? {
        val candidates = buildList {
            activeRules.forEach { sourceRule ->
                val sourceFood = foodsById[sourceRule.itemId] ?: return@forEach
                val sourceRoles = CulinaryPolicy.roles(sourceFood)
                sourceRule.allowedMealTypes.forEach { mealType ->
                    val allowedSourceRoles = sourceRoles.filter {
                        CulinaryPolicy.isAllowedForMeal(it, mealType)
                    }
                    val hasDependencyFreeEscape = allowedSourceRoles.any { role ->
                        val policy = CulinaryPolicy.policy(role)
                        policy.requiredRoles.isEmpty() &&
                            policy.requiredAnyOfRoles.isEmpty() &&
                            CulinarySoftPolicy.preferredCompanions(role).isEmpty()
                    }
                    if (hasDependencyFreeEscape) return@forEach

                    allowedSourceRoles.forEach { sourceRole ->
                        val policy = CulinaryPolicy.policy(sourceRole)
                        val groups = buildList {
                            policy.requiredRoles.forEach { add(true to setOf(it)) }
                            if (policy.requiredAnyOfRoles.isNotEmpty()) {
                                add(true to policy.requiredAnyOfRoles)
                            }
                            val preferred = CulinarySoftPolicy.preferredCompanions(sourceRole)
                            if (preferred.isNotEmpty()) add(false to preferred)
                        }
                        groups.forEach { (hard, targetRoles) ->
                            val enabled = activeRules.any { candidateRule ->
                                candidateRule.itemId != sourceRule.itemId &&
                                    mealType in candidateRule.allowedMealTypes &&
                                    foodsById[candidateRule.itemId]?.let(CulinaryPolicy::roles)
                                        ?.any(targetRoles::contains) == true
                            }
                            if (enabled) return@forEach

                            val existing = activeRules.asSequence()
                                .filter { it.itemId != sourceRule.itemId }
                                .mapNotNull { rule -> foodsById[rule.itemId] }
                                .firstOrNull { food ->
                                    CulinaryPolicy.roles(food).any(targetRoles::contains)
                                }
                            val requiredRole = existing?.let(CulinaryPolicy::roles)
                                ?.firstOrNull(targetRoles::contains)
                                ?: targetRoles.minByOrNull { it.ordinal }
                                ?: return@forEach
                            add(
                                DependencyCandidate(
                                    opportunity = CulinaryDependencyOpportunity(
                                        sourceFoodId = sourceFood.id,
                                        sourceFoodName = sourceFood.name,
                                        sourceRole = sourceRole,
                                        requiredRole = requiredRole,
                                        mealType = mealType,
                                        existingCompatibleFoodName = existing?.name,
                                        hardRequirement = hard
                                    ),
                                    sourceMealCount = sourceRule.allowedMealTypes.size,
                                    hasExistingFood = existing != null
                                )
                            )
                        }
                    }
                }
            }
        }
        return candidates.sortedWith(
            compareByDescending<DependencyCandidate> { it.opportunity.hardRequirement }
                .thenByDescending { it.hasExistingFood }
                .thenBy { it.sourceMealCount }
                .thenBy { it.opportunity.mealType.ordinal }
                .thenBy { it.opportunity.sourceFoodId }
        ).firstOrNull()?.opportunity
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
                CulinarySatisfactionIssueKind.DAILY_REPETITION_DISCOURAGED -> 50_000.0
                CulinarySatisfactionIssueKind.QUANTITY_OUTSIDE_SATISFACTORY_RANGE -> 10_000.0
            }
        } + evaluation.issues.size
}
