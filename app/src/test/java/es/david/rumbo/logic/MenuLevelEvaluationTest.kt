package es.david.rumbo.logic

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Test

class MenuLevelEvaluationTest {
    private val viableWitness = MenuWitness(seed = 11L, meals = emptyList())

    @Test
    fun feasibleSearchCertifiesOnlyViableAndCarriesItsWitness() {
        val result = MenuLevelEvaluator.fromSearchResult(
            ConstraintSearchStatus.FEASIBLE,
            viableWitness
        )

        assertEquals(
            MenuLevelStatus.CERTIFIED,
            result.result(MenuQualityLevel.VIABLE).status
        )
        assertSame(viableWitness, result.witnessFor(MenuQualityLevel.VIABLE))
        assertEquals(
            MenuLevelStatus.POLICY_UNAVAILABLE,
            result.result(MenuQualityLevel.COMPLETE).status
        )
        assertNull(result.witnessFor(MenuQualityLevel.COMPLETE))
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
    fun inconclusiveViabilityBlocksEveryLaterLevelAndHasNoWitness() {
        val result = MenuLevelEvaluator.fromSearchResult(
            ConstraintSearchStatus.SEARCH_INCONCLUSIVE
        )

        assertEquals(
            MenuLevelStatus.SEARCH_INCONCLUSIVE,
            result.result(MenuQualityLevel.VIABLE).status
        )
        assertNull(result.witnessFor(MenuQualityLevel.VIABLE))
        assertNull(result.highestCertifiedLevel)
        assertEquals(MenuQualityLevel.VIABLE, result.nextPendingLevel)
        MenuQualityLevel.entries.drop(1).forEach { level ->
            assertEquals(
                MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL,
                result.result(level).status
            )
            assertNull(result.witnessFor(level))
        }
    }

    @Test
    fun provedInsufficiencyIsNotAnInconclusiveSearchAndHasNoWitness() {
        val result = MenuLevelEvaluator.fromSearchResult(ConstraintSearchStatus.INSUFFICIENT)

        assertEquals(
            MenuLevelStatus.NOT_CERTIFIED,
            result.result(MenuQualityLevel.VIABLE).status
        )
        assertNull(result.witnessFor(MenuQualityLevel.VIABLE))
        assertNull(result.highestCertifiedLevel)
        MenuQualityLevel.entries.drop(1).forEach { level ->
            assertEquals(
                MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL,
                result.result(level).status
            )
        }
    }

    @Test(expected = IllegalArgumentException::class)
    fun feasibleResultWithoutWitnessIsRejected() {
        MenuLevelEvaluator.fromSearchResult(ConstraintSearchStatus.FEASIBLE)
    }

    @Test(expected = IllegalArgumentException::class)
    fun uncertifiedLevelCannotExposeAWitness() {
        MenuLevelResult(
            MenuQualityLevel.VIABLE,
            MenuLevelStatus.SEARCH_INCONCLUSIVE,
            viableWitness
        )
    }

    @Test
    fun everyCertifiedLevelCanCarryItsOwnWitness() {
        val completeWitness = MenuWitness(seed = 37L, meals = emptyList())
        val result = CumulativeMenuEvaluation(
            listOf(
                MenuLevelResult(
                    MenuQualityLevel.VIABLE,
                    MenuLevelStatus.CERTIFIED,
                    viableWitness
                ),
                MenuLevelResult(
                    MenuQualityLevel.COMPLETE,
                    MenuLevelStatus.CERTIFIED,
                    completeWitness
                ),
                MenuLevelResult(
                    MenuQualityLevel.CULINARILY_SATISFACTORY,
                    MenuLevelStatus.POLICY_UNAVAILABLE
                ),
                MenuLevelResult(
                    MenuQualityLevel.VARIED,
                    MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL
                )
            )
        )

        assertSame(viableWitness, result.witnessFor(MenuQualityLevel.VIABLE))
        assertSame(completeWitness, result.witnessFor(MenuQualityLevel.COMPLETE))
        assertEquals(MenuQualityLevel.COMPLETE, result.highestCertifiedLevel)
        assertEquals(MenuQualityLevel.CULINARILY_SATISFACTORY, result.nextPendingLevel)
    }

    @Test(expected = IllegalArgumentException::class)
    fun cumulativeResultRejectsCertificationAfterAnUncertifiedLevel() {
        val completeWitness = MenuWitness(seed = 37L, meals = emptyList())
        CumulativeMenuEvaluation(
            listOf(
                MenuLevelResult(
                    MenuQualityLevel.VIABLE,
                    MenuLevelStatus.CERTIFIED,
                    viableWitness
                ),
                MenuLevelResult(MenuQualityLevel.COMPLETE, MenuLevelStatus.NOT_CERTIFIED),
                MenuLevelResult(
                    MenuQualityLevel.CULINARILY_SATISFACTORY,
                    MenuLevelStatus.CERTIFIED,
                    completeWitness
                ),
                MenuLevelResult(MenuQualityLevel.VARIED, MenuLevelStatus.BLOCKED_BY_PREVIOUS_LEVEL)
            )
        )
    }
}
