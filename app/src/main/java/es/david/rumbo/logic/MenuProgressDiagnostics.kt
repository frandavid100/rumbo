package es.david.rumbo.logic

import es.david.rumbo.model.MealType

/** Machine-readable reason why the next quality level is not certified. */
enum class MenuDiagnosticKind {
    NO_ACTIVE_RULES,
    MISSING_MEAL_COVERAGE,
    MISSING_REQUIRED_COMPANION,
    SEARCH_INCONCLUSIVE,
    POLICY_UNAVAILABLE
}

data class MenuDiagnostic(
    val targetLevel: MenuQualityLevel,
    val kind: MenuDiagnosticKind,
    val message: String,
    val mealType: MealType? = null,
    val itemIds: Set<Long> = emptySet(),
    val sourceViolation: ConstraintViolationKind? = null
)

enum class RecommendedActionKind {
    ACTIVATE_OR_ADD_FOOD,
    ADD_MEAL_OPTION,
    ADD_COMPATIBLE_COMPANION,
    REVIEW_SEARCH
}

/**
 * One next action only. Its target is always the first level not yet certified.
 * POLICY_UNAVAILABLE deliberately produces no user action: Rumbo must not ask
 * the user to fix a policy that the engine itself cannot yet evaluate.
 */
data class RecommendedAction(
    val targetLevel: MenuQualityLevel,
    val kind: RecommendedActionKind,
    val mealType: MealType? = null,
    val itemIds: Set<Long> = emptySet()
)

data class MenuProgressDiagnosis(
    val highestCertifiedLevel: MenuQualityLevel?,
    val nextPendingLevel: MenuQualityLevel?,
    val diagnostics: List<MenuDiagnostic>,
    val recommendedAction: RecommendedAction?
) {
    init {
        diagnostics.forEach { diagnostic ->
            require(diagnostic.targetLevel == nextPendingLevel) {
                "Los diagnósticos solo pueden referirse al siguiente nivel pendiente."
            }
        }
        recommendedAction?.let { action ->
            require(action.targetLevel == nextPendingLevel) {
                "La recomendación solo puede referirse al siguiente nivel pendiente."
            }
        }
    }
}

object MenuProgressDiagnoser {
    fun diagnose(assessment: RepertoireAssessment): MenuProgressDiagnosis {
        val ladder = assessment.levelEvaluation
        val pending = ladder.nextPendingLevel
        if (pending == null) {
            return MenuProgressDiagnosis(
                highestCertifiedLevel = ladder.highestCertifiedLevel,
                nextPendingLevel = null,
                diagnostics = emptyList(),
                recommendedAction = null
            )
        }

        val result = ladder.result(pending)
        val diagnostics = when (pending) {
            MenuQualityLevel.VIABLE -> viableDiagnostics(assessment)
            MenuQualityLevel.COMPLETE,
            MenuQualityLevel.CULINARILY_SATISFACTORY,
            MenuQualityLevel.VARIED -> when (result.status) {
                MenuLevelStatus.POLICY_UNAVAILABLE -> listOf(
                    MenuDiagnostic(
                        targetLevel = pending,
                        kind = MenuDiagnosticKind.POLICY_UNAVAILABLE,
                        message = "La política necesaria para certificar ${pending.name.lowercase()} todavía no está disponible."
                    )
                )
                else -> emptyList()
            }
        }
        val action = when {
            pending != MenuQualityLevel.VIABLE -> null
            assessment.searchStatus == ConstraintSearchStatus.SEARCH_INCONCLUSIVE ->
                RecommendedAction(
                    targetLevel = pending,
                    kind = RecommendedActionKind.REVIEW_SEARCH
                )
            else -> diagnostics.firstNotNullOfOrNull(::actionFor)
        }

        return MenuProgressDiagnosis(
            highestCertifiedLevel = ladder.highestCertifiedLevel,
            nextPendingLevel = pending,
            diagnostics = diagnostics,
            recommendedAction = action
        )
    }

    private fun viableDiagnostics(assessment: RepertoireAssessment): List<MenuDiagnostic> {
        if (assessment.searchStatus == ConstraintSearchStatus.SEARCH_INCONCLUSIVE) {
            return listOf(
                MenuDiagnostic(
                    targetLevel = MenuQualityLevel.VIABLE,
                    kind = MenuDiagnosticKind.SEARCH_INCONCLUSIVE,
                    message = "La búsqueda no ha certificado un menú viable, pero tampoco ha demostrado que sea imposible."
                )
            )
        }
        return assessment.constraintViolations.map { violation ->
            when (violation.kind) {
                ConstraintViolationKind.NO_ACTIVE_RULES -> MenuDiagnostic(
                    targetLevel = MenuQualityLevel.VIABLE,
                    kind = MenuDiagnosticKind.NO_ACTIVE_RULES,
                    message = violation.message,
                    itemIds = violation.itemIds,
                    sourceViolation = violation.kind
                )
                ConstraintViolationKind.MISSING_MEAL_COVERAGE -> MenuDiagnostic(
                    targetLevel = MenuQualityLevel.VIABLE,
                    kind = MenuDiagnosticKind.MISSING_MEAL_COVERAGE,
                    message = violation.message,
                    mealType = violation.mealType,
                    itemIds = violation.itemIds,
                    sourceViolation = violation.kind
                )
                ConstraintViolationKind.MISSING_REQUIRED_COMPANION -> MenuDiagnostic(
                    targetLevel = MenuQualityLevel.VIABLE,
                    kind = MenuDiagnosticKind.MISSING_REQUIRED_COMPANION,
                    message = violation.message,
                    mealType = violation.mealType,
                    itemIds = violation.itemIds,
                    sourceViolation = violation.kind
                )
            }
        }
    }

    private fun actionFor(diagnostic: MenuDiagnostic): RecommendedAction? = when (diagnostic.kind) {
        MenuDiagnosticKind.NO_ACTIVE_RULES -> RecommendedAction(
            targetLevel = diagnostic.targetLevel,
            kind = RecommendedActionKind.ACTIVATE_OR_ADD_FOOD
        )
        MenuDiagnosticKind.MISSING_MEAL_COVERAGE -> RecommendedAction(
            targetLevel = diagnostic.targetLevel,
            kind = RecommendedActionKind.ADD_MEAL_OPTION,
            mealType = diagnostic.mealType
        )
        MenuDiagnosticKind.MISSING_REQUIRED_COMPANION -> RecommendedAction(
            targetLevel = diagnostic.targetLevel,
            kind = RecommendedActionKind.ADD_COMPATIBLE_COMPANION,
            mealType = diagnostic.mealType,
            itemIds = diagnostic.itemIds
        )
        MenuDiagnosticKind.SEARCH_INCONCLUSIVE -> RecommendedAction(
            targetLevel = diagnostic.targetLevel,
            kind = RecommendedActionKind.REVIEW_SEARCH
        )
        MenuDiagnosticKind.POLICY_UNAVAILABLE -> null
    }
}

val RepertoireAssessment.progressDiagnosis: MenuProgressDiagnosis
    get() = MenuProgressDiagnoser.diagnose(this)
