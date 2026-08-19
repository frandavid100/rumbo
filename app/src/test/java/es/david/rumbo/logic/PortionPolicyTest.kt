package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
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
    fun referenceEnergyKeepsRoleDefaultWhenProductBasisIsUnavailable() {
        CulinaryRole.entries.forEach { role ->
            val base = CulinaryPolicy.defaultPolicy(role)
            val resolved = PortionPolicyResolver.resolve(
                role,
                MealType.LUNCH,
                referenceRecommendation,
                MealDistributionPolicy.defaults
            )
            assertEquals(base.preferredGrams!!, resolved.effectivePreferred, 0.001)
            assertEquals(PortionReferenceSource.ROLE_DEFAULT, resolved.referenceSource)
            assertEquals(1.0, resolved.contextScale, 0.001)
        }
    }

    @Test
    fun dryRiceAndFreshPotatoSharePlateBaseRoleButKeepDifferentNormalGramScales() {
        val rice = food(1, 80.0, setOf("PLATE_BASE"))
        val potato = food(2, 250.0, setOf("PLATE_BASE"))
        val ricePolicy = PortionPolicyResolver.resolve(
            rice,
            CulinaryRole.PLATE_BASE,
            MealType.LUNCH,
            referenceRecommendation,
            MealDistributionPolicy.defaults
        )
        val potatoPolicy = PortionPolicyResolver.resolve(
            potato,
            CulinaryRole.PLATE_BASE,
            MealType.LUNCH,
            referenceRecommendation,
            MealDistributionPolicy.defaults
        )

        assertEquals(80.0, ricePolicy.effectivePreferred, 0.001)
        assertTrue(80.0 in ricePolicy.satisfactoryMinimum..ricePolicy.satisfactoryMaximum)
        assertEquals(250.0, potatoPolicy.effectivePreferred, 0.001)
        assertTrue(250.0 in potatoPolicy.satisfactoryMinimum..potatoPolicy.satisfactoryMaximum)
        assertEquals(PortionReferenceSource.PRODUCT_BASIS, ricePolicy.referenceSource)
        assertEquals(PortionReferenceSource.PRODUCT_BASIS, potatoPolicy.referenceSource)
    }

    @Test
    fun energeticMealMovesElasticProductBasisButNeverLegacyHardLimits() {
        val highEnergy = Recommendation(3000, 130, 380, 90, "test")
        val rice = food(3, 80.0, setOf("PLATE_BASE"))
        val hard = CulinaryPolicy.defaultPolicy(CulinaryRole.PLATE_BASE)
        val resolved = PortionPolicyResolver.resolve(
            rice,
            CulinaryRole.PLATE_BASE,
            MealType.LUNCH,
            highEnergy,
            MealDistributionPolicy.defaults
        )
        assertTrue(resolved.effectivePreferred > 80.0)
        assertEquals(hard.minimumGrams!!, resolved.minimum, 0.001)
        assertEquals(hard.maximumGrams!!, resolved.maximum, 0.001)
        assertTrue(resolved.satisfactoryMinimum >= resolved.minimum)
        assertTrue(resolved.satisfactoryMaximum <= resolved.maximum)
    }

    @Test
    fun cookingMediumDoesNotScaleWithEnergyOrProductBasis() {
        val oil = food(4, 100.0, setOf("COOKING_MEDIUM"))
        val low = Recommendation(1400, 90, 150, 45, "test")
        val high = Recommendation(3200, 180, 420, 100, "test")
        val lowResolved = PortionPolicyResolver.resolve(
            oil,
            CulinaryRole.COOKING_MEDIUM,
            MealType.DINNER,
            low,
            MealDistributionPolicy.defaults
        )
        val highResolved = PortionPolicyResolver.resolve(
            oil,
            CulinaryRole.COOKING_MEDIUM,
            MealType.DINNER,
            high,
            MealDistributionPolicy.defaults
        )
        assertEquals(lowResolved, highResolved)
        assertEquals(10.0, lowResolved.effectivePreferred, 0.001)
        assertEquals(PortionReferenceSource.ROLE_DEFAULT, lowResolved.referenceSource)
    }

    @Test
    fun customMealShareChangesContextWithoutPhysicalProfileInputs() {
        val rice = food(5, 80.0, setOf("PLATE_BASE"))
        val shares = MealDistributionPolicy.defaults.toMutableMap().apply {
            this[MealType.LUNCH] = 0.45
            this[MealType.DINNER] = 0.10
            this[MealType.BREAKFAST] = 0.20
            this[MealType.MORNING_SNACK] = 0.125
            this[MealType.AFTERNOON_SNACK] = 0.125
        }
        val largerLunch = PortionPolicyResolver.resolve(
            rice,
            CulinaryRole.PLATE_BASE,
            MealType.LUNCH,
            referenceRecommendation,
            shares
        )
        val defaultLunch = PortionPolicyResolver.resolve(
            rice,
            CulinaryRole.PLATE_BASE,
            MealType.LUNCH,
            referenceRecommendation,
            MealDistributionPolicy.defaults
        )
        assertTrue(largerLunch.effectivePreferred > defaultLunch.effectivePreferred)
    }

    @Test
    fun standaloneUsesProductServingScaleInsteadOfUniversalGramInterval() {
        val cheese = food(6, 40.0, setOf("STANDALONE"))
        val fruit = food(7, 150.0, setOf("STANDALONE"))
        val cheesePolicy = PortionPolicyResolver.resolve(
            cheese,
            CulinaryRole.STANDALONE,
            MealType.MORNING_SNACK,
            referenceRecommendation,
            MealDistributionPolicy.defaults
        )
        val fruitPolicy = PortionPolicyResolver.resolve(
            fruit,
            CulinaryRole.STANDALONE,
            MealType.MORNING_SNACK,
            referenceRecommendation,
            MealDistributionPolicy.defaults
        )
        assertTrue(40.0 in cheesePolicy.satisfactoryMinimum..cheesePolicy.satisfactoryMaximum)
        assertTrue(150.0 in fruitPolicy.satisfactoryMinimum..fruitPolicy.satisfactoryMaximum)
        assertTrue(cheesePolicy.satisfactoryMaximum < fruitPolicy.satisfactoryMaximum)
    }

    private fun food(id: Long, basis: Double, roles: Set<String>) = Food(
        id = id,
        name = "F$id",
        category = FoodCategory.OTHER,
        calories = 100.0,
        fatGrams = 2.0,
        carbohydrateGrams = 10.0,
        proteinGrams = 5.0,
        fiberGrams = 1.0,
        portionBasisGrams = basis,
        culinaryRoles = roles
    )
}
