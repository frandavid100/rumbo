package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealDistributionPolicy
import es.david.rumbo.model.MealType
import es.david.rumbo.model.NutritionToleranceSettings
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import org.junit.Assert.assertNotNull
import org.junit.Before
import org.junit.Test

class AraLevel3ReducedSearchTest {
    private val target = Recommendation(1675, 105, 208, 47, "Ara")

    @Before
    fun resetPolicies() {
        CulinaryPolicy.configure(emptyList())
        WeeklyMenuAcceptancePolicy.configure(NutritionToleranceSettings())
    }

    @Test
    fun directSearchFindsLevel3WhenOnlyKnownFeasibleAraFoodsArePresent() {
        val foods = listOf(
            food(4359402894918143880L, FoodCategory.FRUIT, 323.0, 0.0, 75.0, 1.2, 5.4, 150.0, setOf("DESSERT", "STANDALONE")),
            food(4713451237391941996L, FoodCategory.PROTEIN, 50.0, 8.2, 4.4, 0.0, 0.0, 150.0, setOf("CEREAL_BASE", "DESSERT", "POWDER_BASE", "STANDALONE")),
            food(5427737837577403981L, FoodCategory.CARBOHYDRATE, 41.0, 0.0, 10.0, 0.0, 0.5, 250.0, setOf("BEVERAGE", "STANDALONE")),
            food(4824921464295006360L, FoodCategory.FRUIT, 342.0, 0.0, 85.0, 0.0, 1.0, 30.0, setOf("DESSERT", "STANDALONE", "TOPPING")),
            food(5863259172627146722L, FoodCategory.CARBOHYDRATE, 42.0, 0.4, 10.1, 0.0, null, 250.0, setOf("BEVERAGE", "STANDALONE")),
            food(4494907683069959481L, FoodCategory.VEGETABLE, 255.0, 6.4, 44.0, 1.8, 23.0, 200.0, setOf("SIDE", "TOPPING")),
            food(5065604127361444435L, FoodCategory.CARBOHYDRATE, 354.0, 6.7, 80.0, 0.0, 1.0, 80.0, setOf("PLATE_BASE", "SIDE")),
            food(5751811545638569543L, FoodCategory.PROTEIN, 74.0, 17.0, 0.5, 0.5, null, 150.0, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
            food(4042487276430228545L, FoodCategory.FAT, 824.0, 0.0, 0.0, 92.0, null, 10.0, setOf("COOKING_MEDIUM", "SAUCE_DRESSING")),
            food(4108023238282100017L, FoodCategory.VEGETABLE, 78.0, 1.1, 6.5, 4.7, 2.5, 200.0, setOf("SIDE", "TOPPING")),
            food(5138918923368881607L, FoodCategory.PROTEIN, 50.0, 11.0, 0.0, 0.7, null, 170.0, setOf("PLATE_CENTER", "SANDWICH_FILLING")),
            food(4912645548334196354L, FoodCategory.PROTEIN, 82.0, 10.0, 6.0, 2.0, 2.0, 100.0, setOf("DESSERT", "STANDALONE"))
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

        val result = CulinaryLevel3CompositionSearch.find(
            rules = rules,
            foodsById = foods,
            dishesById = emptyMap(),
            recommendation = target,
            mealShares = MealDistributionPolicy.defaults
        )
        assertNotNull("El buscador directo no encuentra el subconjunto factible conocido de Ara", result)
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
        category: FoodCategory,
        calories: Double,
        protein: Double,
        carbohydrates: Double,
        fat: Double,
        fiber: Double?,
        basis: Double,
        roles: Set<String>
    ) = Food(
        id = id,
        name = "F$id",
        category = category,
        calories = calories,
        fatGrams = fat,
        carbohydrateGrams = carbohydrates,
        proteinGrams = protein,
        fiberGrams = fiber,
        portionBasisGrams = basis,
        culinaryRoles = roles
    )
}
