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
    LOSE_FASTER("Perder peso más deprisa", -0.0075, 0.75),
    LOSE_SLOWLY("Perder peso poco a poco", -0.005, 0.50),
    MAINTAIN("Mantener el peso", 0.0, 0.0),
    GAIN_SLOWLY("Ganar peso poco a poco", 0.0015, 0.15),
    GAIN_FASTER("Ganar peso algo más deprisa", 0.003, 0.30)
}

data class UserProfile(
    val id: Long,
    val name: String,
    val heightCm: Double,
    val birthYear: Int,
    val sex: Sex,
    val photoUri: String? = null
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

/**
 * Converts the obsolete pre-0.74 culinary type into the canonical functional roles.
 * New code must never persist or reason over the legacy type name itself.
 */
fun legacyCulinaryRoles(typeName: String?): Set<String> = when (typeName) {
    "MILK_BASE" -> setOf("CEREAL_BASE", "POWDER_BASE", "BEVERAGE", "STANDALONE")
    "CREAMY_BASE" -> setOf("CEREAL_BASE", "POWDER_BASE", "STANDALONE", "DESSERT")
    "BREAKFAST_CEREAL" -> setOf("CEREAL_MIX_IN")
    "PROTEIN_POWDER" -> setOf("POWDER_MIX_IN")
    "DRY_RICE", "DRY_PASTA", "FRESH_STARCH" -> setOf("PLATE_BASE")
    "BREAD" -> setOf("SANDWICH_BASE", "PLATE_BASE", "STANDALONE")
    // The old type was too coarse to prove secondary uses. Migrate conservatively:
    // fresh/main proteins remain plate centers unless the new catalogue explicitly
    // assigns SANDWICH_FILLING, TOPPING or STANDALONE.
    "MAIN_MEAT" -> setOf("PLATE_CENTER")
    "MAIN_FISH" -> setOf("PLATE_CENTER")
    "MAIN_EGG" -> setOf("PLATE_CENTER")
    "VEGETABLE" -> setOf("SIDE", "PLATE_BASE", "STANDALONE")
    "FRUIT" -> setOf("STANDALONE", "DESSERT")
    "CULINARY_OIL" -> setOf("COOKING_MEDIUM", "SAUCE_DRESSING")
    "FAT_COMPLEMENT" -> setOf("TOPPING", "STANDALONE")
    "SAUCE" -> setOf("SAUCE_DRESSING")
    "SNACK_DESSERT" -> setOf("STANDALONE", "DESSERT")
    "COOKING_INGREDIENT" -> setOf("SEASONING")
    else -> emptySet()
}

data class CulinaryPolicyOverride(
    val culinaryRole: String,
    val preferredGrams: Double? = null,
    val minimumGrams: Double? = null,
    val maximumGrams: Double? = null,
    val standaloneAllowed: Boolean? = null
)

data class NutritionToleranceSettings(
    val caloriesMinimum: Double = 0.90,
    val caloriesMaximum: Double = 1.10,
    val proteinMinimum: Double = 0.90,
    val proteinMaximum: Double = 1.15,
    val carbohydratesMinimum: Double = 0.85,
    val carbohydratesMaximum: Double = 1.15,
    val fatMinimum: Double = 0.85,
    val fatMaximum: Double = 1.15
) {
    fun isValid(): Boolean = listOf(
        caloriesMinimum to caloriesMaximum,
        proteinMinimum to proteinMaximum,
        carbohydratesMinimum to carbohydratesMaximum,
        fatMinimum to fatMaximum
    ).all { (minimum, maximum) ->
        minimum in 0.50..1.0 && maximum in 1.0..1.60 && minimum <= maximum
    }
}

enum class MealType(val label: String) {
    BREAKFAST("Desayuno"),
    MORNING_SNACK("Almuerzo"),
    LUNCH("Comida"),
    AFTERNOON_SNACK("Merienda"),
    DINNER("Cena")
}

enum class PlanWeek(val label: String) {
    CURRENT("Esta semana"),
    NEXT("Semana que viene")
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

enum class PlanningFrequency(val label: String, val weight: Double) {
    NEVER("Nunca", 0.0),
    OCCASIONAL("De vez en cuando", 1.0),
    NORMAL("A menudo", 3.0),
    FREQUENT("Muy a menudo", 6.0),
    ALWAYS("Todos los días", 0.0)
}

enum class PlannedItemKind {
    FOOD,
    DISH
}

data class PlanningSlot(
    val day: WeekDay,
    val mealType: MealType
)

data class PlanningRule(
    val itemKind: PlannedItemKind,
    val itemId: Long,
    val allowedMealTypes: Set<MealType>,
    val fixedSlots: Set<PlanningSlot> = emptySet(),
    val frequency: PlanningFrequency = PlanningFrequency.NORMAL,
    val isActive: Boolean = true,
    val preferredGrams: Double,
    val minimumFactor: Double = 0.5,
    val maximumFactor: Double = 1.5,
    val ruleId: Long = itemId,
    val allowedDays: Set<WeekDay> = WeekDay.entries.toSet()
) {
    fun isValid(): Boolean =
        itemId > 0 &&
            ruleId > 0 &&
            (frequency == PlanningFrequency.NEVER || allowedMealTypes.isNotEmpty()) &&
            preferredGrams in 1.0..5000.0 &&
            minimumFactor in 0.1..1.0 && maximumFactor in 1.0..5.0

    fun requiredSlots(): Set<PlanningSlot> = if (frequency == PlanningFrequency.ALWAYS) {
        WeekDay.entries.flatMapTo(mutableSetOf()) { day ->
            allowedMealTypes.map { type -> PlanningSlot(day, type) }
        }
    } else emptySet()
}

data class MenuHistoryEntry(
    val generation: Int,
    val itemKind: PlannedItemKind,
    val itemId: Long,
    val day: WeekDay,
    val mealType: MealType
)

data class PlannedFood(
    val foodId: Long,
    val grams: Double,
    val adjustable: Boolean = false,
    val minimumGrams: Double = grams * 0.5,
    val maximumGrams: Double = grams * 1.5
) {
    fun isValid(): Boolean = foodId > 0 && grams in 0.1..5000.0 &&
        (!adjustable || minimumGrams in 0.1..5000.0 && maximumGrams in 0.1..5000.0 &&
            minimumGrams <= grams && grams <= maximumGrams)
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
    val ingredients: List<DishIngredient>,
    val unitName: String? = null,
    val unitPlural: String? = null,
    val unitGender: String = "MASCULINE",
    val unitAmount: Double? = null,
    val wholeUnitsOnly: Boolean = false,
    val unitDivisions: Int = 1,
    val allowedMealTypes: Set<MealType> = MealType.entries.toSet(),
    val allowedDays: Set<WeekDay> = WeekDay.entries.toSet()
) {
    fun isValid(): Boolean = id > 0 && name.trim().isNotEmpty() && name.length <= 80 &&
        ingredients.isNotEmpty() && ingredients.all { it.isValid() } &&
        ingredients.map { it.foodId }.distinct().size == ingredients.size &&
        (unitName == null || unitName.length <= 40) &&
        (unitPlural == null || unitPlural.length <= 40) &&
        unitGender in setOf("MASCULINE", "FEMININE") && unitDivisions in 1..100 &&
        (unitAmount == null || unitAmount in 0.1..5000.0)
}

data class PlannedDish(
    val dishId: Long,
    val grams: Double,
    val adjustable: Boolean = false,
    val minimumGrams: Double = grams * 0.5,
    val maximumGrams: Double = grams * 1.5
) {
    fun isValid(): Boolean = dishId > 0 && grams in 0.1..5000.0 &&
        (!adjustable || minimumGrams in 0.1..5000.0 && maximumGrams in 0.1..5000.0 &&
            minimumGrams <= grams && grams <= maximumGrams)
}

data class MealDayAmounts(
    val day: WeekDay,
    val foodGrams: Map<Long, Double> = emptyMap(),
    val dishGrams: Map<Long, Double> = emptyMap()
)

data class PlannedMeal(
    val id: Long,
    val type: MealType,
    val days: Set<WeekDay>,
    val items: List<PlannedFood> = emptyList(),
    val dishes: List<PlannedDish> = emptyList(),
    val dayAmounts: List<MealDayAmounts> = emptyList(),
    val planWeek: PlanWeek = PlanWeek.CURRENT
) {
    fun isValid(): Boolean {
        val adjustableFoods = items.filter { it.adjustable }.associateBy { it.foodId }
        val adjustableDishes = dishes.filter { it.adjustable }.associateBy { it.dishId }
        return id > 0 && days.isNotEmpty() && (items.isNotEmpty() || dishes.isNotEmpty()) &&
            items.all { it.isValid() } && dishes.all { it.isValid() } &&
            items.map { it.foodId }.distinct().size == items.size &&
            dishes.map { it.dishId }.distinct().size == dishes.size &&
            dayAmounts.map { it.day }.distinct().size == dayAmounts.size &&
            dayAmounts.all { amounts ->
                amounts.day in days &&
                    amounts.foodGrams.all { (id, grams) ->
                        adjustableFoods[id]?.let { grams in it.minimumGrams..it.maximumGrams } == true
                    } &&
                    amounts.dishGrams.all { (id, grams) ->
                        adjustableDishes[id]?.let { grams in it.minimumGrams..it.maximumGrams } == true
                    }
            }
    }
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
    dishesById: Map<Long, Dish> = emptyMap(),
    day: WeekDay? = null
): NutritionTotals {
    val foodTotals = items.fold(NutritionTotals()) { total, planned ->
        total + planned.nutrition(foodsById, resolvedGrams(planned, day))
    }
    return dishes.fold(foodTotals) { total, plannedDish ->
        val dish = dishesById[plannedDish.dishId]
        if (dish == null) total.copy(isComplete = false)
        else total + dish.nutritionForGrams(foodsById, resolvedGrams(plannedDish, day))
    }
}

fun PlannedMeal.resolvedGrams(item: PlannedFood, day: WeekDay?): Double =
    if (!item.adjustable || day == null) item.grams
    else dayAmounts.firstOrNull { it.day == day }?.foodGrams?.get(item.foodId) ?: item.grams

fun PlannedMeal.resolvedGrams(item: PlannedDish, day: WeekDay?): Double =
    if (!item.adjustable || day == null) item.grams
    else dayAmounts.firstOrNull { it.day == day }?.dishGrams?.get(item.dishId) ?: item.grams

fun PlannedMeal.sanitizedDayAmounts(): PlannedMeal {
    val foods = items.filter { it.adjustable }.associateBy { it.foodId }
    val plannedDishes = dishes.filter { it.adjustable }.associateBy { it.dishId }
    val cleaned = dayAmounts.filter { it.day in days }.distinctBy { it.day }.mapNotNull { amounts ->
        val foodAmounts = amounts.foodGrams.mapNotNull { (id, grams) ->
            foods[id]?.let { id to grams.coerceIn(it.minimumGrams, it.maximumGrams) }
        }.toMap()
        val dishAmounts = amounts.dishGrams.mapNotNull { (id, grams) ->
            plannedDishes[id]?.let { id to grams.coerceIn(it.minimumGrams, it.maximumGrams) }
        }.toMap()
        MealDayAmounts(amounts.day, foodAmounts, dishAmounts)
            .takeIf { foodAmounts.isNotEmpty() || dishAmounts.isNotEmpty() }
    }
    return copy(dayAmounts = cleaned)
}

private fun PlannedFood.nutrition(foodsById: Map<Long, Food>, resolvedGrams: Double): NutritionTotals {
    val food = foodsById[foodId]
    val factor = resolvedGrams / 100.0
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
    val source: String? = null,
    val unitName: String? = null,
    val unitPlural: String? = null,
    val unitGender: String = "MASCULINE",
    val unitAmount: Double? = null,
    val wholeUnitsOnly: Boolean = false,
    val unitDivisions: Int = 1,
    val portionBasisGrams: Double? = null,
    val nutritionalRoles: Set<String> = emptySet(),
    val culinaryRoles: Set<String> = emptySet()
) {
    fun isValid(): Boolean = id > 0 && name.trim().isNotEmpty() && name.length <= 160 &&
        validCalories(calories) && validNutrient(fatGrams) &&
        validNutrient(carbohydrateGrams) && validNutrient(proteinGrams) &&
        validNutrient(fiberGrams) && validNutrient(saturatedFatGrams) &&
        validNutrient(sugarGrams) && validNutrient(saltGrams) &&
        (barcode == null || barcode.length in 8..14) && brand.validText(100) && family.validText(180) &&
        subcategory.validText(140) && legalName.validText(600) &&
        ingredients.validText(5000) && retailer.validText(100) && source.validText(100) &&
        unitName.validText(40) && unitPlural.validText(40) &&
        unitGender in setOf("MASCULINE", "FEMININE") && unitDivisions in 1..100 &&
        (unitAmount == null || unitAmount in 0.1..5000.0) &&
        (portionBasisGrams == null || portionBasisGrams in 0.1..5000.0) &&
        (!wholeUnitsOnly || unitName?.isNotBlank() == true) &&
        nutritionalRoles.size <= 20 && culinaryRoles.size <= 30 &&
        nutritionalRoles.all { it.length in 1..80 } &&
        culinaryRoles.all { it.length in 1..80 } &&
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
    val weeklyRateKg: Double? = null,
    val recommendation: Recommendation? = null
)

enum class CertifiedDayLevel {
    VIABLE,
    COMPLETE,
    CULINARILY_SATISFACTORY
}

data class CertifiedDayWitness(
    val level: CertifiedDayLevel,
    val seed: Long,
    val day: WeekDay,
    val meals: List<PlannedMeal>,
    val fingerprint: Int = meals.hashCode()
) {
    fun isStructurallyValid(): Boolean =
        meals.isNotEmpty() &&
            meals.all { meal -> meal.isValid() && meal.days == setOf(day) } &&
            meals.map { it.type }.distinct().size == meals.size
}

data class ProfileData(
    val profile: UserProfile,
    val measurements: List<Measurement> = emptyList(),
    val plannedMeals: List<PlannedMeal> = emptyList(),
    val planningRules: List<PlanningRule> = emptyList(),
    val repertoireFoodIds: Set<Long> = planningRules
        .filter { it.itemKind == PlannedItemKind.FOOD }.mapTo(mutableSetOf()) { it.itemId },
    val menuHistory: List<MenuHistoryEntry> = emptyList(),
    val dismissedSuggestionFoodIds: Set<Long> = emptySet(),
    val culinaryPolicyOverrides: List<CulinaryPolicyOverride> = emptyList(),
    val nutritionToleranceSettings: NutritionToleranceSettings = NutritionToleranceSettings(),
    val mealShares: Map<MealType, Double>? = null,
    val certifiedDayWitnesses: List<CertifiedDayWitness> = emptyList(),
    val certifiedDayLibrary: List<CertifiedDayWitness> = emptyList()
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
        get() = profile != null
}

data class EffectiveValues(
    val weightKg: Double?,
    val waistCm: Double?,
    val activity: ActivityLevel,
    val goal: WeightGoal,
    val weeklyRateKg: Double?
)
