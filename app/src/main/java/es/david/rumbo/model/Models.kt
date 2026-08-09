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
    AUTOMATIC("Automático", 0.0, 0.0),
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

enum class MealType(val label: String) {
    BREAKFAST("Desayuno"),
    MORNING_SNACK("Almuerzo"),
    LUNCH("Comida"),
    AFTERNOON_SNACK("Merienda"),
    DINNER("Cena")
}

enum class WeekDay(val label: String, val shortLabel: String) {
    MONDAY("Lunes", "L"),
    TUESDAY("Martes", "M"),
    WEDNESDAY("Miércoles", "X"),
    THURSDAY("Jueves", "J"),
    FRIDAY("Viernes", "V"),
    SATURDAY("Sábado", "S"),
    SUNDAY("Domingo", "D")
}

data class PlannedFood(
    val foodId: Long,
    val grams: Double
) {
    fun isValid(): Boolean = foodId > 0 && grams in 0.1..5000.0
}

data class DishIngredient(
    val foodId: Long,
    val grams: Double
) {
    fun isValid(): Boolean = foodId > 0 && grams in 0.1..5000.0
}

data class Dish(
    val id: Long,
    val name: String,
    val ingredients: List<DishIngredient>
) {
    fun isValid(): Boolean = id > 0 && name.trim().isNotEmpty() && name.length <= 80 &&
        ingredients.isNotEmpty() && ingredients.all { it.isValid() } &&
        ingredients.map { it.foodId }.distinct().size == ingredients.size
}

data class PlannedDish(
    val dishId: Long,
    val grams: Double
) {
    fun isValid(): Boolean = dishId > 0 && grams in 0.1..5000.0
}

data class PlannedMeal(
    val id: Long,
    val type: MealType,
    val days: Set<WeekDay>,
    val items: List<PlannedFood> = emptyList(),
    val dishes: List<PlannedDish> = emptyList()
) {
    fun isValid(): Boolean = id > 0 && days.isNotEmpty() && (items.isNotEmpty() || dishes.isNotEmpty()) &&
        items.all { it.isValid() } && dishes.all { it.isValid() } &&
        items.map { it.foodId }.distinct().size == items.size &&
        dishes.map { it.dishId }.distinct().size == dishes.size
}

data class NutritionTotals(
    val calories: Double = 0.0,
    val proteinGrams: Double = 0.0,
    val carbohydrateGrams: Double = 0.0,
    val fatGrams: Double = 0.0,
    val fiberGrams: Double = 0.0,
    val isComplete: Boolean = true
)

fun Dish.totalWeightGrams(): Double = ingredients.sumOf { it.grams }

fun Dish.nutrition(foodsById: Map<Long, Food>): NutritionTotals =
    ingredients.fold(NutritionTotals()) { total, ingredient ->
        total + ingredient.nutrition(foodsById)
    }

fun Dish.nutritionForGrams(foodsById: Map<Long, Food>, grams: Double): NutritionTotals {
    val totalWeight = totalWeightGrams()
    return if (totalWeight <= 0.0) NutritionTotals(isComplete = false)
    else nutrition(foodsById).scaled(grams / totalWeight)
}

fun Dish.dominantCategory(foodsById: Map<Long, Food>): FoodCategory {
    val totals = nutrition(foodsById)
    val energyByMacro = listOf(
        FoodCategory.PROTEIN to totals.proteinGrams * 4.0,
        FoodCategory.CARBOHYDRATE to totals.carbohydrateGrams * 4.0,
        FoodCategory.FAT to totals.fatGrams * 9.0
    )
    return energyByMacro.maxByOrNull { it.second }?.takeIf { it.second > 0.0 }?.first
        ?: FoodCategory.OTHER
}

fun PlannedMeal.nutrition(
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish> = emptyMap()
): NutritionTotals {
    val foodTotals = items.fold(NutritionTotals()) { total, planned ->
        total + planned.nutrition(foodsById)
    }
    return dishes.fold(foodTotals) { total, plannedDish ->
        val dish = dishesById[plannedDish.dishId]
        if (dish == null) total.copy(isComplete = false)
        else total + dish.nutritionForGrams(foodsById, plannedDish.grams)
    }
}

private fun PlannedFood.nutrition(foodsById: Map<Long, Food>): NutritionTotals {
    val food = foodsById[foodId]
    val factor = grams / 100.0
    return food.nutrition(factor)
}

private fun DishIngredient.nutrition(foodsById: Map<Long, Food>): NutritionTotals {
    val food = foodsById[foodId]
    val factor = grams / 100.0
    return food.nutrition(factor)
}

private fun Food?.nutrition(factor: Double): NutritionTotals = NutritionTotals(
    calories = (this?.calories ?: 0.0) * factor,
    proteinGrams = (this?.proteinGrams ?: 0.0) * factor,
    carbohydrateGrams = (this?.carbohydrateGrams ?: 0.0) * factor,
    fatGrams = (this?.fatGrams ?: 0.0) * factor,
    fiberGrams = (this?.fiberGrams ?: 0.0) * factor,
    isComplete = this?.hasComparableNutrition() == true
)

private operator fun NutritionTotals.plus(other: NutritionTotals): NutritionTotals =
    NutritionTotals(
        calories = calories + other.calories,
        proteinGrams = proteinGrams + other.proteinGrams,
        carbohydrateGrams = carbohydrateGrams + other.carbohydrateGrams,
        fatGrams = fatGrams + other.fatGrams,
        fiberGrams = fiberGrams + other.fiberGrams,
        isComplete = isComplete && other.isComplete
    )

private fun NutritionTotals.scaled(factor: Double): NutritionTotals = NutritionTotals(
    calories = calories * factor,
    proteinGrams = proteinGrams * factor,
    carbohydrateGrams = carbohydrateGrams * factor,
    fatGrams = fatGrams * factor,
    fiberGrams = fiberGrams * factor,
    isComplete = isComplete
)

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
    val measurements: List<Measurement> = emptyList(),
    val plannedMeals: List<PlannedMeal> = emptyList()
)

data class AppData(
    val profiles: List<ProfileData> = emptyList(),
    val activeProfileId: Long? = null,
    val foods: List<Food> = emptyList(),
    val dishes: List<Dish> = emptyList()
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
