package es.david.rumbo.logic

import es.david.rumbo.model.ActivityLevel
import es.david.rumbo.model.Measurement
import es.david.rumbo.model.Sex
import es.david.rumbo.model.UserProfile
import es.david.rumbo.model.WeightGoal
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class RecommendationEngineTest {
    private val profile = UserProfile(id = 1, name = "David", heightCm = 177.0, birthYear = 1979, sex = Sex.MALE)

    @Test
    fun firstRecommendationMatchesSpreadsheetReferenceCase() {
        val recommendation = RecommendationEngine.recommend(
            profile,
            emptyList(),
            Measurement(
                id = 1,
                date = LocalDate.of(2026, 8, 7),
                weightKg = 83.1,
                waistCm = 91.0,
                activity = ActivityLevel.LIGHT,
                goal = WeightGoal.LOSE_SLOWLY
            )
        )

        assertNotNull(recommendation)
        assertEquals(2125, recommendation!!.calories)
        assertEquals(158, recommendation.proteinGrams)
        assertEquals(241, recommendation.carbohydrateGrams)
        assertEquals(59, recommendation.fatGrams)
        assertNotNull(recommendation.calculation)
        val calculation = recommendation.calculation
        assertEquals(1707.25, calculation!!.restingCalories, 0.01)
        assertEquals(2347.47, calculation.maintenanceCalories, 0.01)
        assertEquals(-0.20775, calculation.appliedWeeklyRateKg, 0.00001)
        assertEquals(-228.53, calculation.goalAdjustmentCalories, 0.01)
        assertTrue(recommendation.reason.startsWith("Estimación inicial"))
        assertTrue(!recommendation.reason.startsWith("2125"))
    }

    @Test
    fun bodyAssessmentClassifiesBmiAndWaist() {
        val history = listOf(
            Measurement(
                id = 1,
                date = LocalDate.of(2026, 8, 8),
                weightKg = 83.4,
                waistCm = 89.5,
                activity = ActivityLevel.LIGHT,
                goal = WeightGoal.LOSE_SLOWLY
            )
        )

        val assessment = RecommendationEngine.assessBody(profile, history)

        assertNotNull(assessment)
        assertEquals(26.62, assessment!!.bmi!!, 0.01)
        assertEquals("Sobrepeso", assessment.bmiInterpretation)
        assertEquals(0.506, assessment.waistToHeightRatio!!, 0.001)
        assertEquals("Adiposidad central aumentada", assessment.waistInterpretation)
    }

    @Test
    fun goalAssessmentExplainsWhyGradualLossIsCoherent() {
        val history = listOf(
            Measurement(
                id = 1,
                date = LocalDate.of(2026, 8, 8),
                weightKg = 83.4,
                waistCm = 89.5,
                activity = ActivityLevel.LIGHT,
                goal = WeightGoal.LOSE_SLOWLY
            )
        )

        val assessment = RecommendationEngine.assessGoal(profile, history)

        assertTrue(assessment.headline.contains("coherente"))
        assertTrue(assessment.explanation.contains("IMC"))
        assertTrue(assessment.explanation.contains("historial"))
        assertTrue(!assessment.isGoalLimited)
    }

    @Test
    fun recommendedGoalUsesBothCurrentIndicators() {
        val history = listOf(
            Measurement(
                id = 1,
                date = LocalDate.of(2026, 8, 8),
                weightKg = 83.4,
                waistCm = 89.5
            )
        )

        val result = RecommendationEngine.recommendGoal(profile, history)

        assertEquals(WeightGoal.LOSE_SLOWLY, result.goal)
        assertTrue(result.explanation.contains("IMC"))
        assertTrue(result.explanation.contains("cintura/altura"))
    }

    @Test
    fun recommendedGoalMaintainsWhenIndicatorsAreInReference() {
        val result = RecommendationEngine.recommendGoal(
            profile,
            listOf(Measurement(id = 1, date = LocalDate.of(2026, 8, 8), weightKg = 72.0, waistCm = 82.0))
        )

        assertEquals(WeightGoal.MAINTAIN, result.goal)
    }

    @Test
    fun recommendedGoalSuggestsGradualGainBelowReferenceBmi() {
        val result = RecommendationEngine.recommendGoal(
            profile,
            listOf(Measurement(id = 1, date = LocalDate.of(2026, 8, 8), weightKg = 55.0, waistCm = 70.0))
        )

        assertEquals(WeightGoal.GAIN_SLOWLY, result.goal)
    }

    @Test
    fun recommendedGoalUsesHigherSafeLossPaceOnlyForHighRisk() {
        val result = RecommendationEngine.recommendGoal(
            profile,
            listOf(Measurement(id = 1, date = LocalDate.of(2026, 8, 8), weightKg = 105.0, waistCm = 110.0))
        )

        assertEquals(WeightGoal.LOSE_FASTER, result.goal)
    }

    @Test
    fun waistOnlyFirstEntryIsStoredWithoutInventingCalories() {
        val recommendation = RecommendationEngine.recommend(
            profile,
            emptyList(),
            Measurement(id = 1, date = LocalDate.of(2026, 8, 7), waistCm = 91.0)
        )

        assertNull(recommendation)
    }

    @Test
    fun lowBmiBlocksRequestedWeightLoss() {
        val recommendation = RecommendationEngine.recommend(
            profile,
            emptyList(),
            Measurement(
                id = 1,
                date = LocalDate.of(2026, 8, 7),
                weightKg = 40.0,
                activity = ActivityLevel.LIGHT,
                goal = WeightGoal.LOSE_FASTER
            )
        )

        assertNotNull(recommendation)
        assertTrue(recommendation!!.isSafetyLimited)
        assertTrue(recommendation.reason.contains("no aplica un déficit"))
    }

    @Test
    fun highWaistRatioBlocksRequestedSurplus() {
        val recommendation = RecommendationEngine.recommend(
            profile,
            emptyList(),
            Measurement(
                id = 1,
                date = LocalDate.of(2026, 8, 7),
                weightKg = 110.0,
                waistCm = 105.0,
                activity = ActivityLevel.LIGHT,
                goal = WeightGoal.GAIN_FASTER
            )
        )

        assertNotNull(recommendation)
        assertTrue(recommendation!!.isSafetyLimited)
        assertTrue(recommendation.reason.contains("no aplica un superávit"))
    }

    @Test
    fun manualWeeklyRateIsPreservedButEnergySafetyLimitIsReported() {
        val recommendation = RecommendationEngine.recommend(
            profile,
            emptyList(),
            Measurement(
                id = 1,
                date = LocalDate.of(2026, 8, 9),
                weightKg = 83.0,
                waistCm = 91.0,
                activity = ActivityLevel.LIGHT,
                goal = WeightGoal.LOSE_SLOWLY,
                weeklyRateKg = -10.0
            )
        )

        assertNotNull(recommendation)
        assertTrue(recommendation!!.isSafetyLimited)
        assertTrue(recommendation.calculation!!.appliedWeeklyRateKg > -10.0)
        assertEquals(
            -10.0,
            RecommendationEngine.effectiveValues(
                listOf(Measurement(id = 1, date = LocalDate.of(2026, 8, 9), goal = WeightGoal.LOSE_SLOWLY, weeklyRateKg = -10.0))
            ).weeklyRateKg!!,
            0.0
        )
    }

    @Test
    fun regressionUsesActualMeasurementDates() {
        val points = listOf(
            LocalDate.of(2026, 7, 1) to 83.0,
            LocalDate.of(2026, 7, 4) to 82.9,
            LocalDate.of(2026, 7, 11) to 82.7,
            LocalDate.of(2026, 7, 22) to 82.4
        )

        val weeklyRate = RecommendationEngine.regressionWeeklyRate(points)
        assertEquals(-0.2, weeklyRate, 0.04)
    }

    @Test
    fun publicWeeklyRateMatchesTheGoalLimits() {
        assertEquals(-0.2075, RecommendationEngine.weeklyRateFor(WeightGoal.LOSE_SLOWLY, 83.0)!!, 0.001)
        assertEquals(0.0, RecommendationEngine.weeklyRateFor(WeightGoal.MAINTAIN, 83.0)!!, 0.001)
        assertNull(RecommendationEngine.weeklyRateFor(WeightGoal.AUTOMATIC, 83.0))
        assertNull(RecommendationEngine.weeklyRateFor(WeightGoal.GAIN_SLOWLY, null))
    }

    @Test
    fun automaticGoalAppliesTheCurrentRecommendedGoal() {
        val recommendation = RecommendationEngine.recommend(
            profile,
            emptyList(),
            Measurement(
                id = 1,
                date = LocalDate.of(2026, 8, 7),
                weightKg = 83.1,
                waistCm = 91.0,
                activity = ActivityLevel.LIGHT,
                goal = WeightGoal.AUTOMATIC
            )
        )

        assertNotNull(recommendation)
        assertEquals(2125, recommendation!!.calories)
        assertEquals(-0.20775, recommendation.calculation!!.appliedWeeklyRateKg, 0.00001)
    }
}
