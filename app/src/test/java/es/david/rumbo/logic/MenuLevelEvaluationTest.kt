package es.david.rumbo.logic

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class MenuLevelEvaluationTest {
    @Test
    fun feasibleSearchCertifiesOnlyViableUntilNextPolicyExists() {
        val result = MenuLevelEvaluator.fromSearchStatus(ConstraintSearchStatus.FEASIBLE)

        assertEquals(
            MenuLevelStatus.CERTIFIED,
            result.result(MenuQualityLevel.VIABLE).status
        )
        assertEquals(
            MenuLevelStatus.POLICY_UNAVAILABLE,
            result.result(MenuQualityLevel.COMPLETE).status
        )
        assertEquals(
            MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL,
            result.result(MenuQualityLevel.CULINARILY_SATISFACTORY).status
        )
        assertEquals(
            MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL,
            result.result(MenuQualityLevel.VARIED).status
        )
        assertEquals(MenuQualityLevel.VIABLE, result.highestCertifiedLevel)
        assertEquals(MenuQualityLevel.COMPLETE, result.nextPendingLevel)
    }

    @Test
    fun inconclusiveViabilityBlocksEveryLaterLevel() {
        val result = MenuLevelEvaluator.fromSearchStatus(
            ConstraintSearchStatus.SEARCH_INCONCLUSIVE
        )

        assertEquals(
            MenuLevelStatus.SEARCH_INCONCLUSIVE,
            result.result(MenuQualityLevel.VIABLE).status
        )
        assertNull(result.highestCertifiedLevel)
        assertEquals(MenuQualityLevel.VIABLE, result.nextPendingLevel)
        MenuQualityLevel.entries.drop(1).forEach { level ->
            assertEquals(
                MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL,
                result.result(level).status
            )
        }
    }

    @Test
    fun provedInsufficiencyIsNotAnInconclusiveSearch() {
        val result = MenuLevelEvaluator.fromSearchStatus(ConstraintSearchStatus.INSUFFICIENT)

        assertEquals(
            MenuLevelStatus.NOT_CERTIFIED,
            result.result(MenuQualityLevel.VIABLE).status
        )
        assertNull(result.highestCertifiedLevel)
        MenuQualityLevel.entries.drop(1).forEach { level ->
            assertEquals(
                MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL,
                result.result(level).status
            )
        }
    }

    @Test(expected = IllegalArgumentException::class)
    fun cumulativeResultRejectsCertificationAfterAnUncertifiedLevel() {
        CumulativeMenuEvaluation(
            listOf(
                MenuLevelResult(MenuQualityLevel.VIABLE, MenuLevelStatus.CERTIFIED),
                MenuLevelResult(MenuQualityLevel.COMPLETE, MenuLevelStatus.NOT_CERTIFIED),
                MenuLevelResult(
                    MenuQualityLevel.CULINARILY_SATISFACTORY,
                    MenuLevelStatus.CERTIFIED
                ),
                MenuLevelResult(MenuQualityLevel.VARIED, MenuLevelStatus.CERTIFIED)
            )
        )
    }
}
