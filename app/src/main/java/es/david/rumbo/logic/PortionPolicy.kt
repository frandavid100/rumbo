package es.david.rumbo.logic

import es.david.rumbo.model.MealDistributionPolicy
import es.david.rumbo.model.MealType
import es.david.rumbo.model.Recommendation
import kotlin.math.pow

enum class PortionContext {
    GENERAL_ADULT
}

data class ResolvedPortionPolicy(
    val minimum: Double,
    val satisfactoryMinimum: Double,
    val effectivePreferred: Double,
    val satisfactoryMaximum: Double,
    val maximum: Double,
    val contextScale: Double
) {
    fun isHardValid(grams: Double): Boolean = grams in minimum..maximum
    fun isSatisfactory(grams: Double): Boolean = grams in satisfactoryMinimum..satisfactoryMaximum
}

/**
 * Version 1 calibration for the GENERAL_ADULT context.
 *
 * Hard minimum/preferred/maximum values remain owned by CulinaryPolicy. This
 * calibration only defines the inner satisfactory zone and how much that zone
 * may move with the energy budget of the concrete meal.
 */
object PortionPolicyResolver {
    const val POLICY_VERSION = 1
    const val REFERENCE_DAILY_CALORIES = 2000.0

    private data class Calibration(
        val satisfactoryMinimum: Double,
        val satisfactoryMaximum: Double,
        val energyElasticity: Double,
        val minimumContextScale: Double,
        val maximumContextScale: Double
    )

    private val generalAdult = mapOf(
        CulinaryRole.PLATE_CENTER to Calibration(75.0, 225.0, 0.35, 0.75, 1.35),
        CulinaryRole.PLATE_BASE to Calibration(75.0, 220.0, 0.50, 0.70, 1.50),
        CulinaryRole.SIDE to Calibration(75.0, 250.0, 0.15, 0.85, 1.25),
        CulinaryRole.TOPPING to Calibration(5.0, 40.0, 0.00, 1.00, 1.00),
        CulinaryRole.SAUCE_DRESSING to Calibration(10.0, 60.0, 0.10, 0.85, 1.15),
        CulinaryRole.CEREAL_BASE to Calibration(150.0, 300.0, 0.15, 0.85, 1.20),
        CulinaryRole.CEREAL_MIX_IN to Calibration(25.0, 70.0, 0.35, 0.75, 1.35),
        CulinaryRole.POWDER_BASE to Calibration(180.0, 350.0, 0.10, 0.90, 1.15),
        CulinaryRole.POWDER_MIX_IN to Calibration(20.0, 40.0, 0.10, 0.90, 1.15),
        CulinaryRole.SANDWICH_BASE to Calibration(40.0, 120.0, 0.35, 0.75, 1.35),
        CulinaryRole.SANDWICH_FILLING to Calibration(30.0, 100.0, 0.25, 0.80, 1.25),
        CulinaryRole.SPREAD to Calibration(5.0, 40.0, 0.05, 0.90, 1.10),
        CulinaryRole.COOKING_MEDIUM to Calibration(5.0, 15.0, 0.00, 1.00, 1.00),
        CulinaryRole.BINDER to Calibration(10.0, 40.0, 0.00, 1.00, 1.00),
        CulinaryRole.COATING to Calibration(15.0, 50.0, 0.10, 0.90, 1.15),
        CulinaryRole.SEASONING to Calibration(0.5, 10.0, 0.00, 1.00, 1.00),
        // STANDALONE contains fruit, yoghurt, nuts and many other foods whose
        // sensible gram weights differ greatly. Until a narrower portion class
        // exists, level 3 must not invent an arbitrary inner gram interval.
        CulinaryRole.STANDALONE to Calibration(20.0, 300.0, 0.00, 1.00, 1.00),
        CulinaryRole.BEVERAGE to Calibration(150.0, 400.0, 0.10, 0.90, 1.15),
        CulinaryRole.DESSERT to Calibration(80.0, 200.0, 0.10, 0.90, 1.15)
    )

    fun resolve(
        role: CulinaryRole,
        mealType: MealType,
        mealEnergyTargetCalories: Double,
        context: PortionContext = PortionContext.GENERAL_ADULT
    ): ResolvedPortionPolicy {
        require(context == PortionContext.GENERAL_ADULT) { "Contexto de ración no implementado: $context" }
        val hard = CulinaryPolicy.policy(role)
        val minimum = requireNotNull(hard.minimumGrams) { "Falta mínimo para $role" }
        val maximum = requireNotNull(hard.maximumGrams) { "Falta máximo para $role" }
        val preferred = requireNotNull(hard.preferredGrams) { "Falta preferencia para $role" }
        val calibration = requireNotNull(generalAdult[role]) { "Falta calibración para $role" }

        val referenceShare = MealDistributionPolicy.defaults.getValue(mealType)
        val referenceMealCalories = REFERENCE_DAILY_CALORIES * referenceShare
        val ratio = if (referenceMealCalories > 0.0) {
            (mealEnergyTargetCalories / referenceMealCalories).coerceIn(0.25, 4.0)
        } else 1.0
        val rawScale = if (calibration.energyElasticity == 0.0) 1.0
            else ratio.pow(calibration.energyElasticity)
        val scale = rawScale.coerceIn(
            calibration.minimumContextScale,
            calibration.maximumContextScale
        )

        var satisfactoryMinimum = (calibration.satisfactoryMinimum * scale)
            .coerceIn(minimum, maximum)
        var satisfactoryMaximum = (calibration.satisfactoryMaximum * scale)
            .coerceIn(minimum, maximum)
        if (satisfactoryMinimum > satisfactoryMaximum) {
            val center = (satisfactoryMinimum + satisfactoryMaximum) / 2.0
            satisfactoryMinimum = center
            satisfactoryMaximum = center
        }
        val effectivePreferred = (preferred * scale)
            .coerceIn(satisfactoryMinimum, satisfactoryMaximum)

        return ResolvedPortionPolicy(
            minimum = minimum,
            satisfactoryMinimum = satisfactoryMinimum,
            effectivePreferred = effectivePreferred,
            satisfactoryMaximum = satisfactoryMaximum,
            maximum = maximum,
            contextScale = scale
        )
    }

    fun resolve(
        role: CulinaryRole,
        mealType: MealType,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        context: PortionContext = PortionContext.GENERAL_ADULT
    ): ResolvedPortionPolicy = resolve(
        role = role,
        mealType = mealType,
        mealEnergyTargetCalories = recommendation.calories *
            (mealShares[mealType] ?: MealDistributionPolicy.defaults.getValue(mealType)),
        context = context
    )

    fun calibrationIsComplete(): Boolean = generalAdult.keys == CulinaryRole.entries.toSet()
}
