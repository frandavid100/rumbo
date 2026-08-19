package es.david.rumbo.logic

import es.david.rumbo.model.MealDistributionPolicy
import es.david.rumbo.model.MealType
import es.david.rumbo.model.Recommendation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PortionPolicyTest {
    private val referenceRecommendation = Recommendation(2000, 100, 250, 67, "test")

    @Test
    fun everyCanonicalRoleHasGeneralAdultCalibration() {
        assertTrue(PortionPolicyResolver.calibrationIsComplete())
        CulinaryRole.entries.forEach { role ->
            val resolved = PortionPolicyResolver.resolve(
                role,
                MealType.LUNCH,
                referenceRecommendation,
                MealDistributionPolicy.defaults
            )
            assertTrue(resolved.minimum <= resolved.satisfactoryMinimum)
            assertTrue(resolved.satisfactoryMinimum <= resolved.effectivePreferred)
            assertTrue(resolved.effectivePreferred <= resolved.satisfactoryMaximum)
            assertTrue(resolved.satisfactoryMaximum <= resolved.maximum)
        }
    }

    @Test
    fun referenceEnergyKeepsBasePreference() {
        CulinaryRole.entries.forEach { role ->
            val base = CulinaryPolicy.defaultPolicy(role)
            val resolved = PortionPolicyResolver.resolve(
                role,
                MealType.LUNCH,
                referenceRecommendation,
                MealDistributionPolicy.defaults
            )
            assertEquals(base.preferredGrams!!, resolved.effectivePreferred, 0.001)
            assertEquals(1.0, resolved.contextScale, 0.001)
        }
    }

    @Test
    fun energeticMealMovesElasticPlateBaseButNeverHardLimits() {
        val highEnergy = Recommendation(3000, 130, 380, 90, "test")
        val base = CulinaryPolicy.defaultPolicy(CulinaryRole.PLATE_BASE)
        val resolved = PortionPolicyResolver.resolve(
            CulinaryRole.PLATE_BASE,
            MealType.LUNCH,
            highEnergy,
            MealDistributionPolicy.defaults
        )
        assertTrue(resolved.effectivePreferred > base.preferredGrams!!)
        assertEquals(base.minimumGrams!!, resolved.minimum, 0.001)
        assertEquals(base.maximumGrams!!, resolved.maximum, 0.001)
        assertTrue(resolved.satisfactoryMinimum >= resolved.minimum)
        assertTrue(resolved.satisfactoryMaximum <= resolved.maximum)
    }

    @Test
    fun cookingMediumDoesNotScaleWithEnergy() {
        val low = Recommendation(1400, 90, 150, 45, "test")
        val high = Recommendation(3200, 180, 420, 100, "test")
        val lowResolved = PortionPolicyResolver.resolve(
            CulinaryRole.COOKING_MEDIUM,
            MealType.DINNER,
            low,
            MealDistributionPolicy.defaults
        )
        val highResolved = PortionPolicyResolver.resolve(
            CulinaryRole.COOKING_MEDIUM,
            MealType.DINNER,
            high,
            MealDistributionPolicy.defaults
        )
        assertEquals(lowResolved, highResolved)
    }

    @Test
    fun customMealShareChangesContextWithoutPhysicalProfileInputs() {
        val shares = MealDistributionPolicy.defaults.toMutableMap().apply {
            this[MealType.LUNCH] = 0.45
            this[MealType.DINNER] = 0.10
            this[MealType.BREAKFAST] = 0.20
            this[MealType.MORNING_SNACK] = 0.125
            this[MealType.AFTERNOON_SNACK] = 0.125
        }
        val largerLunch = PortionPolicyResolver.resolve(
            CulinaryRole.PLATE_BASE,
            MealType.LUNCH,
            referenceRecommendation,
            shares
        )
        val defaultLunch = PortionPolicyResolver.resolve(
            CulinaryRole.PLATE_BASE,
            MealType.LUNCH,
            referenceRecommendation,
            MealDistributionPolicy.defaults
        )
        assertTrue(largerLunch.effectivePreferred > defaultLunch.effectivePreferred)
    }

    @Test
    fun heterogeneousStandaloneUsesHardDomainAsSatisfactoryDomainForNow() {
        val resolved = PortionPolicyResolver.resolve(
            CulinaryRole.STANDALONE,
            MealType.MORNING_SNACK,
            referenceRecommendation,
            MealDistributionPolicy.defaults
        )
        assertEquals(resolved.minimum, resolved.satisfactoryMinimum, 0.001)
        assertEquals(resolved.maximum, resolved.satisfactoryMaximum, 0.001)
    }
}
