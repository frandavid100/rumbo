package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.Dish
import es.david.rumbo.model.DishIngredient
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class WeeklyMenuGeneratorTest {
    private val foods = listOf(
        food(1, "Pollo", 165.0, 31.0, 0.0, 3.6),
        food(2, "Arroz", 360.0, 7.0, 79.0, 0.6),
        food(3, "Salmón", 208.0, 20.0, 0.0, 13.0),
        food(4, "Patata", 77.0, 2.0, 17.0, 0.1),
        food(5, "Nueces", 700.0, 17.0, 2.0, 70.0)
    )
    private val recommendation = Recommendation(2000, 140, 220, 65, "")

    @Test
    fun allowedMealTypesAreRespected() {
        val rules = listOf(
            rule(1, setOf(MealType.LUNCH)),
            rule(2, setOf(MealType.LUNCH)),
            rule(3, setOf(MealType.DINNER)),
            rule(4, setOf(MealType.DINNER))
        )

        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = rules,
            history = emptyList(),
            foodsById = foods.associateBy { it.id },
            dishesById = emptyMap(),
            recommendation = recommendation,
            seed = 42
        )

        assertEquals(14, result.meals.size)
        assertTrue(result.meals.filter { it.type == MealType.LUNCH }.all {
            it.items.isNotEmpty() && it.items.all { item -> item.foodId in setOf(1L, 2L) }
        })
        assertTrue(result.meals.filter { it.type == MealType.DINNER }.all {
            it.items.isNotEmpty() && it.items.all { item -> item.foodId in setOf(3L, 4L) }
        })
        assertTrue(result.history.size in 14..28)
    }

    @Test
    fun calorieDenseOptionalFoodIsNotAddedWhenItsMinimumExceedsMealTarget() {
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = listOf(
                PlanningRule(
                    itemKind = PlannedItemKind.FOOD,
                    itemId = 2,
                    allowedMealTypes = setOf(MealType.BREAKFAST),
                    frequency = PlanningFrequency.ALWAYS,
                    preferredGrams = 110.0
                ),
                rule(5, setOf(MealType.BREAKFAST))
            ),
            history = emptyList(),
            foodsById = foods.associateBy { it.id },
            dishesById = emptyMap(),
            recommendation = recommendation,
            seed = 7
        )

        val breakfast = result.meals.single {
            it.type == MealType.BREAKFAST && WeekDay.MONDAY in it.days
        }
        assertEquals(listOf(2L), breakfast.items.map { it.foodId })
    }

    @Test
    fun severalDailyFoodsCanShareTheSameMeal() {
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = listOf(
                rule(1, setOf(MealType.LUNCH)).copy(frequency = PlanningFrequency.ALWAYS),
                rule(2, setOf(MealType.LUNCH)).copy(frequency = PlanningFrequency.ALWAYS),
                rule(3, setOf(MealType.DINNER))
            ),
            history = emptyList(),
            foodsById = foods.associateBy { it.id },
            dishesById = emptyMap(),
            recommendation = recommendation,
            seed = 42
        )

        val mondayLunch = result.meals.single {
            it.type == MealType.LUNCH && WeekDay.MONDAY in it.days
        }
        assertEquals(setOf(1L, 2L), mondayLunch.items.map { it.foodId }.toSet())
    }

    @Test
    fun oneDishCanSatisfyTwoDailyFoodRules() {
        val dish = Dish(
            id = 20,
            name = "Pollo con arroz",
            ingredients = listOf(DishIngredient(1, 150.0), DishIngredient(2, 100.0))
        )
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = listOf(
                rule(1, setOf(MealType.LUNCH)).copy(frequency = PlanningFrequency.ALWAYS),
                rule(2, setOf(MealType.LUNCH)).copy(frequency = PlanningFrequency.ALWAYS)
            ),
            history = emptyList(),
            foodsById = foods.associateBy { it.id },
            dishesById = mapOf(dish.id to dish),
            recommendation = recommendation,
            mealShares = MealType.entries.associateWith { if (it == MealType.LUNCH) 1.0 else 0.0 },
            seed = 42
        )

        val mondayLunch = result.meals.single { WeekDay.MONDAY in it.days }
        assertEquals(listOf(20L), mondayLunch.dishes.map { it.dishId })
        assertTrue(mondayLunch.items.isEmpty())
    }

    @Test
    fun everyConfiguredMealTypeIsGenerated() {
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = MealType.entries.mapIndexed { index, type ->
                rule((index % 4 + 1).toLong(), setOf(type))
            },
            history = emptyList(),
            foodsById = foods.associateBy { it.id },
            dishesById = emptyMap(),
            recommendation = recommendation,
            seed = 9
        )

        assertEquals(35, result.meals.size)
        assertEquals(MealType.entries.toSet(), result.meals.map { it.type }.toSet())
    }

    @Test
    fun zeroCalorieShareSkipsSnackAndRemovesItsPreviousPlan() {
        val previousSnack = es.david.rumbo.model.PlannedMeal(
            id = 99,
            type = MealType.MORNING_SNACK,
            days = setOf(WeekDay.MONDAY),
            items = listOf(es.david.rumbo.model.PlannedFood(2, 100.0, true, 50.0, 200.0))
        )
        val shares = mapOf(
            MealType.BREAKFAST to 0.30,
            MealType.MORNING_SNACK to 0.0,
            MealType.LUNCH to 0.40,
            MealType.AFTERNOON_SNACK to 0.0,
            MealType.DINNER to 0.30
        )

        val result = WeeklyMenuGenerator.generate(
            currentMeals = listOf(previousSnack),
            rules = listOf(
                rule(2, setOf(MealType.BREAKFAST, MealType.MORNING_SNACK)),
                rule(1, setOf(MealType.LUNCH)),
                rule(3, setOf(MealType.DINNER))
            ),
            history = emptyList(),
            foodsById = foods.associateBy { it.id },
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = shares,
            seed = 10
        )

        assertTrue(result.meals.none {
            it.type == MealType.MORNING_SNACK || it.type == MealType.AFTERNOON_SNACK
        })
    }

    @Test
    fun dailyPresenceNeverLocksTheGeneratedQuantity() {
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = listOf(
                PlanningRule(
                    itemKind = PlannedItemKind.FOOD,
                    itemId = 2,
                    allowedMealTypes = setOf(MealType.MORNING_SNACK, MealType.DINNER),
                    frequency = PlanningFrequency.ALWAYS,
                    preferredGrams = 150.0
                ),
                rule(1, setOf(MealType.MORNING_SNACK, MealType.DINNER))
            ),
            history = emptyList(),
            foodsById = foods.associateBy { it.id },
            dishesById = emptyMap(),
            recommendation = recommendation,
            seed = 12
        )

        val snackItem = result.meals.single {
            it.type == MealType.MORNING_SNACK && WeekDay.MONDAY in it.days
        }.items.single { it.foodId == 2L }
        val dinnerItem = result.meals.single {
            it.type == MealType.DINNER && WeekDay.MONDAY in it.days
        }.items.single { it.foodId == 2L }
        assertTrue(snackItem.adjustable)
        assertTrue(dinnerItem.adjustable)
    }

    @Test
    fun nutritionallyImperfectWeekReturnsBestAvailableMenuInsteadOfFailure() {
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = listOf(rule(5, setOf(MealType.BREAKFAST))),
            history = emptyList(),
            foodsById = foods.associateBy { it.id },
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = MealType.entries.associateWith {
                if (it == MealType.BREAKFAST) 1.0 else 0.0
            },
            seed = 31
        )

        assertEquals(7, result.meals.size)
        assertEquals(7, result.diagnostics.size)
        assertTrue(result.diagnostics.all { it.worst > 0.0 })
    }

    @Test
    fun inactiveFoodAndDishesContainingItAreNotGenerated() {
        val dish = Dish(
            id = 50,
            name = "Pollo con arroz",
            ingredients = listOf(DishIngredient(1, 100.0), DishIngredient(2, 100.0))
        )
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = listOf(
                rule(1, setOf(MealType.LUNCH)),
                rule(2, setOf(MealType.LUNCH)).copy(isActive = false)
            ),
            history = emptyList(),
            foodsById = foods.associateBy { it.id },
            dishesById = mapOf(dish.id to dish),
            recommendation = recommendation,
            mealShares = MealType.entries.associateWith { if (it == MealType.LUNCH) 1.0 else 0.0 },
            seed = 41
        )

        assertTrue(result.meals.flatMap { it.items }.none { it.foodId == 2L })
        assertTrue(result.meals.flatMap { it.dishes }.none { it.dishId == dish.id })
    }

    @Test
    fun dailyFrequencyUsesEveryDayAndLegacyDayRestrictionsAreIgnored() {
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = listOf(
                rule(1, setOf(MealType.LUNCH)).copy(
                    ruleId = 101,
                    frequency = PlanningFrequency.ALWAYS
                ),
                rule(2, setOf(MealType.DINNER)).copy(
                    ruleId = 102,
                    frequency = PlanningFrequency.OCCASIONAL,
                    allowedDays = setOf(WeekDay.MONDAY)
                ),
                rule(4, setOf(MealType.LUNCH)).copy(ruleId = 103)
            ),
            history = emptyList(),
            foodsById = foods.associateBy { it.id },
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = MealType.entries.associateWith {
                if (it == MealType.LUNCH || it == MealType.DINNER) .5 else 0.0
            },
            seed = 51
        )

        val lunches = result.meals.filter { it.type == MealType.LUNCH }
        assertTrue(lunches.all { meal -> meal.items.any { it.foodId == 1L } })
        val dinners = result.meals.filter { it.type == MealType.DINNER }
        assertTrue(dinners.all { meal -> meal.items.any { it.foodId == 2L } })
    }

    private fun rule(
        id: Long,
        types: Set<MealType>
    ) = PlanningRule(
        itemKind = PlannedItemKind.FOOD,
        itemId = id,
        allowedMealTypes = types,
        frequency = PlanningFrequency.NORMAL,
        preferredGrams = 150.0,
        minimumFactor = 0.5,
        maximumFactor = 2.0
    )

    private fun food(
        id: Long,
        name: String,
        calories: Double,
        protein: Double,
        carbs: Double,
        fat: Double
    ) = Food(
        id = id,
        name = name,
        category = FoodCategory.OTHER,
        calories = calories,
        fatGrams = fat,
        carbohydrateGrams = carbs,
        proteinGrams = protein,
        fiberGrams = 1.0
    )
}
