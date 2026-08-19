package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealDistributionPolicy
import es.david.rumbo.model.MealType
import es.david.rumbo.model.NutritionToleranceSettings
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AraKnownLevel3WitnessTest {
    private val target = Recommendation(1675, 105, 208, 47, "Ara")

    @Before
    fun resetPolicies() {
        CulinaryPolicy.configure(emptyList())
        WeeklyMenuAcceptancePolicy.configure(NutritionToleranceSettings())
    }

    @Test
    fun knownAraCompositionIsCompleteAndCulinarilySatisfactory() {
        val foods = listOf(
            food(4359402894918143880L, "Arándanos", FoodCategory.FRUIT, 323.0, 0.0, 75.0, 1.2, 5.4, 150.0, setOf("DESSERT", "STANDALONE")),
            food(4713451237391941996L, "Queso fresco proteína+", FoodCategory.PROTEIN, 50.0, 8.2, 4.4, 0.0, 0.0, 150.0, setOf("CEREAL_BASE", "DESSERT", "POWDER_BASE", "STANDALONE")),
            food(5427737837577403981L, "Zumo de manzana", FoodCategory.CARBOHYDRATE, 41.0, 0.0, 10.0, 0.0, 0.5, 250.0, setOf("BEVERAGE", "STANDALONE")),
            food(4824921464295006360L, "Papaya desecada", FoodCategory.FRUIT, 342.0, 0.0, 85.0, 0.0, 1.0, 30.0, setOf("DESSERT", "STANDALONE", "TOPPING")),
            food(5863259172627146722L, "Zumo Don Simón", FoodCategory.CARBOHYDRATE, 42.0, 0.4, 10.1, 0.0, null, 250.0, setOf("BEVERAGE", "STANDALONE")),
            food(4494907683069959481L, "Tomate deshidratado", FoodCategory.VEGETABLE, 255.0, 6.4, 44.0, 1.8, 23.0, 200.0, setOf("SIDE", "TOPPING")),
            food(5065604127361444435L, "Arroz", FoodCategory.CARBOHYDRATE, 354.0, 6.7, 80.0, 0.0, 1.0, 80.0, setOf("PLATE_BASE", "SIDE")),
            food(5751811545638569543L, "Pavo", FoodCategory.PROTEIN, 74.0, 17.0, 0.5, 0.5, null, 150.0, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
            food(4042487276430228545L, "Aceite", FoodCategory.FAT, 824.0, 0.0, 0.0, 92.0, null, 10.0, setOf("COOKING_MEDIUM", "SAUCE_DRESSING")),
            food(4108023238282100017L, "Berenjena", FoodCategory.VEGETABLE, 78.0, 1.1, 6.5, 4.7, 2.5, 200.0, setOf("SIDE", "TOPPING")),
            food(5138918923368881607L, "Sepia", FoodCategory.PROTEIN, 50.0, 11.0, 0.0, 0.7, null, 170.0, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
            food(4912645548334196354L, "Mousse proteico", FoodCategory.PROTEIN, 82.0, 10.0, 6.0, 2.0, 2.0, 100.0, setOf("DESSERT", "STANDALONE"))
        ).associateBy { it.id }

        val rules = listOf(
            rule(4359402894918143880L, MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER),
            rule(4713451237391941996L, MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER),
            rule(5427737837577403981L, MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER),
            rule(4824921464295006360L, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
            rule(5863259172627146722L, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
            rule(4494907683069959481L, MealType.LUNCH, MealType.DINNER),
            rule(5065604127361444435L, MealType.LUNCH),
            rule(5751811545638569543L, MealType.LUNCH, MealType.DINNER),
            rule(4042487276430228545L, *MealType.entries.toTypedArray()),
            rule(4108023238282100017L, MealType.DINNER),
            rule(5138918923368881607L, MealType.LUNCH, MealType.DINNER),
            rule(4912645548334196354L, MealType.LUNCH, MealType.DINNER)
        )

        fun meal(id: Long, type: MealType, vararg entries: Pair<Long, Double>) = PlannedMeal(
            id = id,
            type = type,
            days = setOf(WeekDay.MONDAY),
            items = entries.map { (foodId, grams) -> PlannedFood(foodId, grams, false) }
        )

        val meals = listOf(
            meal(1L, MealType.BREAKFAST,
                4359402894918143880L to 73.7,
                4713451237391941996L to 73.7,
                5427737837577403981L to 147.4),
            meal(2L, MealType.MORNING_SNACK,
                4824921464295006360L to 20.0,
                5863259172627146722L to 147.4),
            meal(3L, MealType.LUNCH,
                4494907683069959481L to 97.4,
                5065604127361444435L to 45.8,
                5751811545638569543L to 211.5,
                4042487276430228545L to 8.9),
            meal(4L, MealType.AFTERNOON_SNACK,
                4824921464295006360L to 20.0,
                5863259172627146722L to 147.4),
            meal(5L, MealType.DINNER,
                4108023238282100017L to 210.3,
                5138918923368881607L to 239.7,
                4912645548334196354L to 133.6,
                4042487276430228545L to 15.0)
        )

        val complete = CertifiedDayWitness(
            CertifiedDayLevel.COMPLETE,
            30_000L,
            WeekDay.MONDAY,
            meals
        )
        assertTrue(
            "El día constructivo de Ara debe cumplir COMPLETE",
            CertifiedDayWitnessEvaluator.isComplete(
                complete, rules, foods, emptyMap(), target, MealDistributionPolicy.defaults
            )
        )

        val level3 = complete.copy(level = CertifiedDayLevel.CULINARILY_SATISFACTORY)
        val evaluation = CulinarySatisfactionEvaluator.evaluateDay(
            WeekDay.MONDAY,
            meals,
            foods,
            emptyMap(),
            target,
            MealDistributionPolicy.defaults
        )
        assertTrue(
            "El día constructivo de Ara debe ser culinariamente satisfactorio: " +
                evaluation.issues.joinToString(" | ") { it.message },
            CulinarySatisfactionEvaluator.isCulinarilySatisfactory(
                level3, rules, foods, emptyMap(), target, MealDistributionPolicy.defaults
            )
        )
    }

    private fun rule(id: Long, vararg meals: MealType) = PlanningRule(
        itemKind = PlannedItemKind.FOOD,
        itemId = id,
        allowedMealTypes = meals.toSet(),
        frequency = PlanningFrequency.NORMAL,
        preferredGrams = 100.0,
        minimumFactor = 0.5,
        maximumFactor = 1.5
    )

    private fun food(
        id: Long,
        name: String,
        category: FoodCategory,
        calories: Double,
        protein: Double,
        carbohydrates: Double,
        fat: Double,
        fiber: Double?,
        portionBasis: Double,
        roles: Set<String>
    ) = Food(
        id = id,
        name = name,
        category = category,
        calories = calories,
        fatGrams = fat,
        carbohydrateGrams = carbohydrates,
        proteinGrams = protein,
        fiberGrams = fiber,
        portionBasisGrams = portionBasis,
        culinaryRoles = roles
    )
}
