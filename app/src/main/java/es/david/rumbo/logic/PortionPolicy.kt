package es.david.rumbo.logic

import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealDistributionPolicy
import es.david.rumbo.model.MealType
import es.david.rumbo.model.Recommendation
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.pow
import kotlin.math.round

internal fun Food.practicalUnitStep(): Double? = unitAmount?.takeIf { it > 0.0 }?.let { amount ->
    when {
        wholeUnitsOnly -> amount
        unitDivisions > 1 -> amount / unitDivisions
        else -> null
    }
}

internal fun Dish.practicalUnitStep(): Double? = unitAmount?.takeIf { it > 0.0 }?.let { amount ->
    when {
        wholeUnitsOnly -> amount
        unitDivisions > 1 -> amount / unitDivisions
        else -> null
    }
}

internal fun usesPracticalUnits(grams: Double, step: Double?): Boolean {
    if (step == null) return true
    val units = grams / step
    return abs(units - round(units)) < 0.000_001
}

internal fun practicalGramAmount(grams: Double): Double = when {
    grams < 10.0 -> round(grams).coerceAtLeast(1.0)
    grams <= 100.0 -> round(grams / 5.0) * 5.0
    else -> round(grams / 10.0) * 10.0
}

internal fun usesComfortableGramAmount(grams: Double): Boolean =
    abs(grams - practicalGramAmount(grams)) < 0.000_001

enum class PortionContext {
    GENERAL_ADULT
}

enum class PortionReferenceSource {
    PRODUCT_BASIS,
    ROLE_DEFAULT
}

data class ResolvedPortionPolicy(
    val minimum: Double,
    val satisfactoryMinimum: Double,
    val effectivePreferred: Double,
    val satisfactoryMaximum: Double,
    val maximum: Double,
    val contextScale: Double,
    val referenceGrams: Double,
    val referenceSource: PortionReferenceSource
) {
    fun isHardValid(grams: Double): Boolean = grams in minimum..maximum
    fun isSatisfactory(grams: Double): Boolean {
        // Catalogue portions and optimized menu amounts are commonly rounded.
        // A small boundary discrepancy is not a culinary defect. Keep the
        // tolerance proportional to the product/role reference and bounded so
        // genuinely disproportionate quantities remain invalid.
        val tolerance = (referenceGrams * 0.05).coerceIn(5.0, 15.0)
        return grams >= satisfactoryMinimum - tolerance &&
            grams <= satisfactoryMaximum + tolerance
    }
}

/**
 * Version 2 calibration for the GENERAL_ADULT context.
 *
 * Culinary roles describe function, not physical serving scale. Substantial
 * roles therefore use Food.portionBasisGrams when it exists: 80 g of dry rice
 * and 250 g of fresh potato can both be ordinary PLATE_BASE occurrences without
 * creating separate culinary roles. Modifier roles whose amount is defined by
 * their function (oil, topping, seasoning...) keep a role-level reference.
 *
 * The existing hard role domains are deliberately preserved during this first
 * level-3 migration so previously certified level-1/2 witnesses remain valid.
 */
object PortionPolicyResolver {
    const val POLICY_VERSION = 2
    const val REFERENCE_DAILY_CALORIES = 2000.0

    private enum class ReferenceMode { PRODUCT_BASIS, ROLE_DEFAULT }

    private data class Calibration(
        val referenceMode: ReferenceMode,
        val satisfactoryMinimumFactor: Double,
        val satisfactoryMaximumFactor: Double,
        val energyElasticity: Double,
        val minimumContextScale: Double,
        val maximumContextScale: Double
    )

    private val generalAdult = mapOf(
        CulinaryRole.PLATE_CENTER to Calibration(ReferenceMode.PRODUCT_BASIS, 0.50, 1.50, 0.35, 0.75, 1.35),
        CulinaryRole.PLATE_BASE to Calibration(ReferenceMode.PRODUCT_BASIS, 0.625, 1.50, 0.50, 0.70, 1.50),
        CulinaryRole.SIDE to Calibration(ReferenceMode.PRODUCT_BASIS, 0.50, 1.25, 0.15, 0.85, 1.25),
        CulinaryRole.SALAD_BASE to Calibration(ReferenceMode.PRODUCT_BASIS, 0.50, 1.25, 0.15, 0.85, 1.25),
        CulinaryRole.TOPPING to Calibration(ReferenceMode.ROLE_DEFAULT, 0.25, 2.00, 0.00, 1.00, 1.00),
        CulinaryRole.SAUCE_DRESSING to Calibration(ReferenceMode.ROLE_DEFAULT, 1.0 / 3.0, 2.00, 0.10, 0.85, 1.15),
        CulinaryRole.CEREAL_BASE to Calibration(ReferenceMode.PRODUCT_BASIS, 0.75, 1.50, 0.15, 0.85, 1.20),
        CulinaryRole.CEREAL_MIX_IN to Calibration(ReferenceMode.ROLE_DEFAULT, 0.50, 1.40, 0.35, 0.75, 1.35),
        CulinaryRole.POWDER_BASE to Calibration(ReferenceMode.PRODUCT_BASIS, 0.72, 1.40, 0.10, 0.90, 1.15),
        CulinaryRole.POWDER_MIX_IN to Calibration(ReferenceMode.ROLE_DEFAULT, 2.0 / 3.0, 4.0 / 3.0, 0.10, 0.90, 1.15),
        CulinaryRole.SANDWICH_BASE to Calibration(ReferenceMode.PRODUCT_BASIS, 0.60, 1.50, 0.35, 0.75, 1.35),
        CulinaryRole.SANDWICH_FILLING to Calibration(ReferenceMode.ROLE_DEFAULT, 0.50, 5.0 / 3.0, 0.25, 0.80, 1.25),
        CulinaryRole.SPREAD to Calibration(ReferenceMode.ROLE_DEFAULT, 0.20, 1.60, 0.05, 0.90, 1.10),
        CulinaryRole.COOKING_MEDIUM to Calibration(ReferenceMode.ROLE_DEFAULT, 0.50, 1.50, 0.00, 1.00, 1.00),
        CulinaryRole.BINDER to Calibration(ReferenceMode.ROLE_DEFAULT, 0.50, 2.00, 0.00, 1.00, 1.00),
        CulinaryRole.COATING to Calibration(ReferenceMode.ROLE_DEFAULT, 0.50, 5.0 / 3.0, 0.10, 0.90, 1.15),
        CulinaryRole.SEASONING to Calibration(ReferenceMode.ROLE_DEFAULT, 1.0 / 6.0, 10.0 / 3.0, 0.00, 1.00, 1.00),
        CulinaryRole.STANDALONE to Calibration(ReferenceMode.PRODUCT_BASIS, 0.50, 1.50, 0.10, 0.85, 1.20),
        CulinaryRole.BEVERAGE to Calibration(ReferenceMode.PRODUCT_BASIS, 0.60, 1.60, 0.10, 0.90, 1.15),
        CulinaryRole.DESSERT to Calibration(ReferenceMode.PRODUCT_BASIS, 0.50, 1.50, 0.10, 0.90, 1.15)
    )

    fun resolve(
        food: Food?,
        role: CulinaryRole,
        mealType: MealType,
        mealEnergyTargetCalories: Double,
        context: PortionContext = PortionContext.GENERAL_ADULT
    ): ResolvedPortionPolicy {
        require(context == PortionContext.GENERAL_ADULT) { "Contexto de ración no implementado: $context" }
        val hard = CulinaryPolicy.policy(role)
        val minimum = requireNotNull(hard.minimumGrams) { "Falta mínimo para $role" }
        val maximum = requireNotNull(hard.maximumGrams) { "Falta máximo para $role" }
        val roleReference = requireNotNull(hard.preferredGrams) { "Falta preferencia para $role" }
        val calibration = requireNotNull(generalAdult[role]) { "Falta calibración para $role" }

        val productBasis = food?.portionBasisGrams?.takeIf { it > 0.0 }
        val usesProductBasis = calibration.referenceMode == ReferenceMode.PRODUCT_BASIS && productBasis != null
        val reference = if (usesProductBasis) productBasis!! else roleReference
        val referenceSource = if (usesProductBasis) {
            PortionReferenceSource.PRODUCT_BASIS
        } else {
            PortionReferenceSource.ROLE_DEFAULT
        }

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

        var satisfactoryMinimum = (reference * calibration.satisfactoryMinimumFactor * scale)
            .coerceIn(minimum, maximum)
        var satisfactoryMaximum = (reference * calibration.satisfactoryMaximumFactor * scale)
            .coerceIn(minimum, maximum)
        if (satisfactoryMinimum > satisfactoryMaximum) {
            val center = (satisfactoryMinimum + satisfactoryMaximum) / 2.0
            satisfactoryMinimum = center
            satisfactoryMaximum = center
        }

        // A theoretical edge can fall just beside a practical unit. Admit only
        // the closest adjacent unit, and only within a small unit-relative
        // tolerance; never widen both ends of the interval.
        food?.practicalUnitStep()?.let { step ->
            val lower = (floor(satisfactoryMinimum / step) * step)
                .takeIf { it >= minimum && it > 0.0 }
                ?.let { amount -> amount to (satisfactoryMinimum - amount) }
            val upper = (ceil(satisfactoryMaximum / step) * step)
                .takeIf { it <= maximum }
                ?.let { amount -> amount to (amount - satisfactoryMaximum) }
            val nearest = listOfNotNull(lower?.let { false to it }, upper?.let { true to it })
                .minWithOrNull(compareBy<Pair<Boolean, Pair<Double, Double>>> { it.second.second }
                    .thenBy { it.first })
            val tolerance = (step * 0.10).coerceIn(1.0, 10.0)
            nearest?.takeIf { it.second.second <= tolerance }?.let { (isUpper, candidate) ->
                if (isUpper) satisfactoryMaximum = candidate.first
                else satisfactoryMinimum = candidate.first
            }
        }
        val effectivePreferred = (reference * scale)
            .coerceIn(satisfactoryMinimum, satisfactoryMaximum)

        return ResolvedPortionPolicy(
            minimum = minimum,
            satisfactoryMinimum = satisfactoryMinimum,
            effectivePreferred = effectivePreferred,
            satisfactoryMaximum = satisfactoryMaximum,
            maximum = maximum,
            contextScale = scale,
            referenceGrams = reference,
            referenceSource = referenceSource
        )
    }

    fun resolve(
        role: CulinaryRole,
        mealType: MealType,
        mealEnergyTargetCalories: Double,
        context: PortionContext = PortionContext.GENERAL_ADULT
    ): ResolvedPortionPolicy = resolve(
        food = null,
        role = role,
        mealType = mealType,
        mealEnergyTargetCalories = mealEnergyTargetCalories,
        context = context
    )

    fun resolve(
        food: Food?,
        role: CulinaryRole,
        mealType: MealType,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        context: PortionContext = PortionContext.GENERAL_ADULT
    ): ResolvedPortionPolicy = resolve(
        food = food,
        role = role,
        mealType = mealType,
        mealEnergyTargetCalories = recommendation.calories *
            (mealShares[mealType] ?: MealDistributionPolicy.defaults.getValue(mealType)),
        context = context
    )

    fun resolve(
        role: CulinaryRole,
        mealType: MealType,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        context: PortionContext = PortionContext.GENERAL_ADULT
    ): ResolvedPortionPolicy = resolve(
        food = null,
        role = role,
        mealType = mealType,
        recommendation = recommendation,
        mealShares = mealShares,
        context = context
    )

    fun calibrationIsComplete(): Boolean = generalAdult.keys == CulinaryRole.entries.toSet()
}
