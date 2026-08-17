package es.david.rumbo.logic

/** Public quality ladder defined by the menu specification. */
enum class MenuQualityLevel {
    VIABLE,
    COMPLETE,
    CULINARILY_SATISFACTORY,
    VARIED
}

/**
 * Result of evaluating one level of the cumulative ladder.
 *
 * POLICY_UNAVAILABLE is different from failure: the current compatibility
 * catalogue does not yet contain, or Rumbo has not yet calibrated, enough
 * policy to certify that level without inventing a proxy.
 */
enum class MenuLevelStatus {
    CERTIFIED,
    NOT_CERTIFIED,
    SEARCH_INCONCLUSIVE,
    POLICY_UNAVAILABLE,
    BLOCKED_BY_PREVIOUS_LEVEL
}

data class MenuLevelResult(
    val level: MenuQualityLevel,
    val status: MenuLevelStatus
) {
    val isCertified: Boolean get() = status == MenuLevelStatus.CERTIFIED
}

data class CumulativeMenuEvaluation(
    val results: List<MenuLevelResult>
) {
    init {
        require(results.map { it.level } == MenuQualityLevel.entries) {
            "Los niveles deben aparecer exactamente en el orden acumulativo definido."
        }
        var previousCertified = true
        results.forEach { result ->
            if (!previousCertified) {
                require(result.status == MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL) {
                    "Un nivel posterior no puede evaluarse ni certificarse si falla el anterior."
                }
            }
            previousCertified = previousCertified && result.isCertified
        }
    }

    /** Maximum consecutive level reached; null means that VIABLE is not certified. */
    val highestCertifiedLevel: MenuQualityLevel?
        get() = results.takeWhile { it.isCertified }.lastOrNull()?.level

    /** First level that still prevents progress. */
    val nextPendingLevel: MenuQualityLevel?
        get() = results.firstOrNull { !it.isCertified }?.level

    fun result(level: MenuQualityLevel): MenuLevelResult =
        results.single { it.level == level }
}

object MenuLevelEvaluator {
    /**
     * Builds the strict cumulative ladder from the authoritative feasibility
     * state. Later levels intentionally remain unavailable until their actual
     * policies can be evaluated; legacy variety or category heuristics are not
     * promoted into certification criteria.
     */
    fun fromSearchStatus(searchStatus: ConstraintSearchStatus): CumulativeMenuEvaluation {
        val viableStatus = when (searchStatus) {
            ConstraintSearchStatus.FEASIBLE -> MenuLevelStatus.CERTIFIED
            ConstraintSearchStatus.SEARCH_INCONCLUSIVE -> MenuLevelStatus.SEARCH_INCONCLUSIVE
            ConstraintSearchStatus.INSUFFICIENT -> MenuLevelStatus.NOT_CERTIFIED
        }
        if (viableStatus != MenuLevelStatus.CERTIFIED) {
            return CumulativeMenuEvaluation(
                listOf(
                    MenuLevelResult(MenuQualityLevel.VIABLE, viableStatus),
                    MenuLevelResult(
                        MenuQualityLevel.COMPLETE,
                        MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL
                    ),
                    MenuLevelResult(
                        MenuQualityLevel.CULINARILY_SATISFACTORY,
                        MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL
                    ),
                    MenuLevelResult(
                        MenuQualityLevel.VARIED,
                        MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL
                    )
                )
            )
        }

        return CumulativeMenuEvaluation(
            listOf(
                MenuLevelResult(MenuQualityLevel.VIABLE, MenuLevelStatus.CERTIFIED),
                MenuLevelResult(MenuQualityLevel.COMPLETE, MenuLevelStatus.POLICY_UNAVAILABLE),
                MenuLevelResult(
                    MenuQualityLevel.CULINARILY_SATISFACTORY,
                    MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL
                ),
                MenuLevelResult(
                    MenuQualityLevel.VARIED,
                    MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL
                )
            )
        )
    }

    fun evaluate(assessment: RepertoireAssessment): CumulativeMenuEvaluation =
        fromSearchStatus(assessment.searchStatus)
}

/** Compatibility access point for callers while the legacy assessment remains. */
val RepertoireAssessment.levelEvaluation: CumulativeMenuEvaluation
    get() = MenuLevelEvaluator.evaluate(this)
