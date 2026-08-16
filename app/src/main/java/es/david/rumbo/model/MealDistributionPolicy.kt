package es.david.rumbo.model

/** Single source of truth for the default daily energy distribution. */
object MealDistributionPolicy {
    val defaults: Map<MealType, Double> = mapOf(
        MealType.BREAKFAST to 0.25,
        MealType.MORNING_SNACK to 0.10,
        MealType.LUNCH to 0.35,
        MealType.AFTERNOON_SNACK to 0.10,
        MealType.DINNER to 0.20
    )
}
