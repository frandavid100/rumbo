package es.david.rumbo.model

import java.time.LocalDate

enum class Sex(val label: String) {
    MALE("Hombre"),
    FEMALE("Mujer")
}

enum class ActivityLevel(val label: String, val description: String, val multiplier: Double) {
    SEDENTARY("Sedentaria", "Poco movimiento y sin ejercicio habitual", 1.20),
    LIGHT("Ligera", "Movimiento diario o ejercicio 1–3 días por semana", 1.375),
    MODERATE("Moderada", "Ejercicio 3–5 días por semana", 1.55),
    HIGH("Alta", "Ejercicio exigente 6–7 días por semana", 1.725),
    VERY_HIGH("Muy alta", "Trabajo físico y entrenamiento intenso", 1.90)
}

enum class DietCompliance(val label: String, val score: Int) {
    MUCH_LESS("1 · Mucho menos de lo previsto", 1),
    LESS("2 · Algo menos de lo previsto", 2),
    ON_TARGET("3 · Aproximadamente lo previsto", 3),
    MORE("4 · Algo más de lo previsto", 4),
    MUCH_MORE("5 · Mucho más de lo previsto", 5)
}

enum class WeightGoal(val label: String, val weeklyRateFactor: Double, val maximumRate: Double) {
    LOSE_FASTER("Perder peso más deprisa", -0.005, 0.50),
    LOSE_SLOWLY("Perder peso poco a poco", -0.0025, 0.25),
    MAINTAIN("Mantener el peso", 0.0, 0.0),
    GAIN_SLOWLY("Ganar peso poco a poco", 0.0015, 0.15),
    GAIN_FASTER("Ganar peso algo más deprisa", 0.003, 0.30)
}

data class UserProfile(
    val id: Long,
    val name: String,
    val heightCm: Double,
    val birthYear: Int,
    val sex: Sex
) {
    fun isValid(currentYear: Int = LocalDate.now().year): Boolean =
        id > 0 && name.trim().isNotEmpty() && name.length <= 30 &&
            heightCm in 120.0..230.0 && birthYear in (currentYear - 110)..(currentYear - 16)
}

data class Recommendation(
    val calories: Int,
    val proteinGrams: Int,
    val carbohydrateGrams: Int,
    val fatGrams: Int,
    val reason: String,
    val isSafetyLimited: Boolean = false,
    val calculation: CalculationBreakdown? = null
)

data class CalculationBreakdown(
    val weightKg: Double,
    val heightCm: Double,
    val ageYears: Int,
    val sexAdjustment: Int,
    val restingCalories: Double,
    val activity: ActivityLevel,
    val maintenanceCalories: Double,
    val appliedWeeklyRateKg: Double,
    val goalAdjustmentCalories: Double,
    val goalSafetyExplanation: String?,
    val energyLimitAdjustmentCalories: Double,
    val energyLimitExplanation: String?,
    val historyAdjustmentCalories: Double,
    val historyExplanation: String,
    val previousLimitAdjustmentCalories: Double,
    val previousLimitExplanation: String?,
    val beforeRoundingCalories: Double
)

data class BodyAssessment(
    val bmi: Double?,
    val bmiInterpretation: String?,
    val waistToHeightRatio: Double?,
    val waistInterpretation: String?
)

data class GoalAssessment(
    val headline: String,
    val explanation: String,
    val isGoalLimited: Boolean
)

data class RecommendedGoal(
    val goal: WeightGoal,
    val explanation: String
)

enum class FoodCategory(val label: String) {
    CARBOHYDRATE("Carbohidrato"),
    FRUIT("Fruta"),
    FAT("Grasa"),
    PROTEIN("Proteína"),
    VEGETABLE("Verdura"),
    OTHER("Otros")
}

data class Food(
    val id: Long,
    val name: String,
    val category: FoodCategory,
    val calories: Double?,
    val fatGrams: Double?,
    val carbohydrateGrams: Double?,
    val proteinGrams: Double?,
    val fiberGrams: Double?,
    val links: List<String> = emptyList(),
    val barcode: String? = null,
    val brand: String? = null,
    val family: String? = null,
    val subcategory: String? = null,
    val legalName: String? = null,
    val ingredients: String? = null,
    val saturatedFatGrams: Double? = null,
    val sugarGrams: Double? = null,
    val saltGrams: Double? = null,
    val retailer: String? = null,
    val source: String? = null
) {
    fun isValid(): Boolean = id > 0 && name.trim().isNotEmpty() && name.length <= 160 &&
        validCalories(calories) && validNutrient(fatGrams) &&
        validNutrient(carbohydrateGrams) && validNutrient(proteinGrams) &&
        validNutrient(fiberGrams) && validNutrient(saturatedFatGrams) &&
        validNutrient(sugarGrams) && validNutrient(saltGrams) &&
        (barcode == null || barcode.length in 8..14) && brand.validText(100) && family.validText(180) &&
        subcategory.validText(140) && legalName.validText(600) &&
        ingredients.validText(5000) && retailer.validText(100) && source.validText(100) &&
        links.size <= 10 &&
        links.distinct().size == links.size && links.all {
            it.length <= 500 && (it.startsWith("https://") || it.startsWith("http://"))
        }

    fun hasComparableNutrition(): Boolean = calories != null && fatGrams != null &&
        carbohydrateGrams != null && proteinGrams != null

    private fun validCalories(value: Double?): Boolean = value == null || value in 0.0..1000.0
    private fun validNutrient(value: Double?): Boolean = value == null || value in 0.0..100.0
    private fun String?.validText(maxLength: Int): Boolean = this == null || length <= maxLength
}

data class Measurement(
    val id: Long,
    val date: LocalDate,
    val weightKg: Double? = null,
    val waistCm: Double? = null,
    val activity: ActivityLevel? = null,
    val compliance: DietCompliance? = null,
    val goal: WeightGoal? = null,
    val recommendation: Recommendation? = null
)

data class ProfileData(
    val profile: UserProfile,
    val measurements: List<Measurement> = emptyList()
)

data class AppData(
    val profiles: List<ProfileData> = emptyList(),
    val activeProfileId: Long? = null,
    val foods: List<Food> = emptyList()
) {
    val activeProfileData: ProfileData?
        get() = profiles.firstOrNull { it.profile.id == activeProfileId } ?: profiles.firstOrNull()

    val profile: UserProfile?
        get() = activeProfileData?.profile

    val measurements: List<Measurement>
        get() = activeProfileData?.measurements.orEmpty()

    val isActiveProfileReady: Boolean
        get() = profile != null && measurements.any { it.weightKg != null } &&
            measurements.any { it.waistCm != null } && measurements.any { it.goal != null }
}

data class EffectiveValues(
    val weightKg: Double?,
    val waistCm: Double?,
    val activity: ActivityLevel,
    val goal: WeightGoal
)
