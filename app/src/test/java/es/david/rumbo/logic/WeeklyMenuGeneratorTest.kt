package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.legacyCulinaryRoles
import es.david.rumbo.model.Dish
import es.david.rumbo.model.DishIngredient
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
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

    @Test
    fun aMealNeverContainsSeveralStandaloneStarchBases() {
        val culinaryFoods = listOf(
            food(10, "Filetes de pechuga de pavo", 110.0, 24.0, 0.0, 1.0, "MAIN_MEAT"),
            food(11, "Arroz basmati Hacendado", 350.0, 7.0, 78.0, 1.0, "DRY_RICE"),
            food(12, "Hacendado hélices vegetales", 350.0, 12.0, 72.0, 2.0, "DRY_PASTA"),
            food(13, "Hacendado macarrón", 350.0, 12.0, 72.0, 2.0, "DRY_PASTA")
        )
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = culinaryFoods.map { rule(it.id, setOf(MealType.LUNCH)) },
            history = emptyList(),
            foodsById = culinaryFoods.associateBy { it.id },
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = MealType.entries.associateWith { if (it == MealType.LUNCH) 1.0 else 0.0 },
            seed = 61
        )

        result.meals.forEach { meal ->
            val starches = meal.items.count { item ->
                CulinaryRole.PLATE_BASE in CulinaryPolicy.roles(
                    culinaryFoods.single { it.id == item.foodId }
                )
            }
            assertTrue(starches <= 1)
        }
    }

    @Test
    fun proteinPowderAlwaysBringsAnAvailableLiquidOrCreamyBase() {
        val powder = food(20, "Polvo de proteínas Natural Isolate", 358.0, 83.0, 2.0, 2.0, "PROTEIN_POWDER")
        val milk = food(21, "Leche semidesnatada", 46.0, 3.2, 4.8, 1.6, "MILK_BASE")
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = listOf(
                rule(powder.id, setOf(MealType.BREAKFAST)).copy(
                    frequency = PlanningFrequency.ALWAYS,
                    preferredGrams = 30.0
                ),
                rule(milk.id, setOf(MealType.BREAKFAST)).copy(preferredGrams = 250.0)
            ),
            history = emptyList(),
            foodsById = listOf(powder, milk).associateBy { it.id },
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = MealType.entries.associateWith {
                if (it == MealType.BREAKFAST) 1.0 else 0.0
            },
            seed = 62
        )

        assertTrue(result.meals.all { meal ->
            meal.items.any { it.foodId == powder.id } && meal.items.any { it.foodId == milk.id }
        })
    }

    @Test
    fun proteinPowderCannotBeGeneratedWithoutACompatibleBase() {
        val powder = food(30, "Proteína en polvo whey", 358.0, 83.0, 2.0, 2.0, "PROTEIN_POWDER")
        val cereal = food(31, "Corn flakes integrales", 380.0, 8.0, 80.0, 2.0, "BREAKFAST_CEREAL")

        assertThrows(PlanningConflictException::class.java) {
            WeeklyMenuGenerator.generate(
                currentMeals = emptyList(),
                rules = listOf(
                    rule(powder.id, setOf(MealType.BREAKFAST)).copy(
                        frequency = PlanningFrequency.ALWAYS,
                        preferredGrams = 30.0
                    ),
                    rule(cereal.id, setOf(MealType.BREAKFAST))
                ),
                history = emptyList(),
                foodsById = listOf(powder, cereal).associateBy { it.id },
                dishesById = emptyMap(),
                recommendation = recommendation,
                mealShares = MealType.entries.associateWith {
                    if (it == MealType.BREAKFAST) 1.0 else 0.0
                },
                seed = 63
            )
        }
    }

    @Test
    fun aMealUsesOneStandalonePrimaryProteinAndCulinaryOilPortions() {
        val chicken = food(40, "Pechuga de pollo", 108.0, 22.0, 1.0, 2.0, "MAIN_MEAT")
        val fish = food(41, "Lubina", 90.0, 18.0, 0.0, 2.0, "MAIN_FISH")
        val rice = food(42, "Arroz basmati", 353.0, 9.0, 78.0, 1.0, "DRY_RICE")
        val oil = food(43, "AOVE", 819.0, 0.0, 0.0, 91.0, "CULINARY_OIL")
        val catalog = listOf(chicken, fish, rice, oil)
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = listOf(
                rule(chicken.id, setOf(MealType.LUNCH)),
                rule(fish.id, setOf(MealType.LUNCH)),
                rule(rice.id, setOf(MealType.LUNCH)),
                rule(oil.id, setOf(MealType.LUNCH)).copy(frequency = PlanningFrequency.ALWAYS)
            ),
            history = emptyList(),
            foodsById = catalog.associateBy { it.id },
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = MealType.entries.associateWith { if (it == MealType.LUNCH) 1.0 else 0.0 },
            seed = 64
        )

        result.meals.forEach { meal ->
            assertTrue(meal.items.count { it.foodId == chicken.id || it.foodId == fish.id } <= 1)
            val plannedOil = meal.items.single { it.foodId == oil.id }
            assertTrue(plannedOil.minimumGrams >= 5.0)
            assertTrue(plannedOil.maximumGrams <= 15.0)
        }
    }

    @Test
    fun cookingIngredientRoleNeverAppearsAsTheOnlyElementOfAMeal() {
        val breadcrumbs = food(
            50, "Pan rallado", 336.0, 8.7, 71.3, 1.7,
            "COOKING_INGREDIENT"
        )
        val rice = food(51, "Arroz", 353.0, 9.0, 78.0, 1.0, "DRY_RICE")
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = listOf(
                rule(breadcrumbs.id, setOf(MealType.LUNCH)),
                rule(rice.id, setOf(MealType.LUNCH))
            ),
            history = emptyList(),
            foodsById = listOf(breadcrumbs, rice).associateBy { it.id },
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = MealType.entries.associateWith { if (it == MealType.LUNCH) 1.0 else 0.0 },
            seed = 65
        )

        assertTrue(result.meals.all { meal ->
            meal.items.none { it.foodId == breadcrumbs.id } || meal.items.size + meal.dishes.size > 1
        })
    }

    @Test
    fun culinaryAndQuantityInvariantsHoldAcrossGoalsAndSeeds() {
        val catalog = listOf(
            food(101, "Proteína en polvo", 358.0, 83.0, 2.0, 2.0, "PROTEIN_POWDER"),
            food(102, "Leche", 46.0, 3.1, 4.8, 1.6, "MILK_BASE"),
            food(103, "Cereales", 373.0, 6.7, 82.0, 1.1, "BREAKFAST_CEREAL"),
            food(104, "Pavo loncheado", 90.0, 19.5, .1, 1.3, "MAIN_MEAT"),
            food(105, "Barquillo", 390.0, 11.0, 79.0, 2.6, "SNACK_DESSERT"),
            food(106, "Pollo", 108.0, 22.3, .9, 1.7, "MAIN_MEAT"),
            food(107, "Pavo", 104.0, 24.0, 0.0, .9, "MAIN_MEAT"),
            food(108, "Merluza", 82.0, 18.0, .5, 1.2, "MAIN_FISH"),
            food(109, "Lubina", 90.0, 18.0, 0.0, 2.0, "MAIN_FISH"),
            food(110, "Arroz", 353.0, 9.0, 78.0, .6, "DRY_RICE"),
            food(111, "Pasta", 359.0, 12.0, 74.0, 1.7, "DRY_PASTA"),
            food(112, "Batata", 155.0, 1.6, 26.0, 5.0, "FRESH_STARCH"),
            food(113, "AOVE", 819.0, 0.0, 0.0, 91.0, "CULINARY_OIL"),
            food(114, "Nueces", 703.0, 17.0, 2.2, 69.6, "FAT_COMPLEMENT"),
            food(115, "Verdura", 30.0, 1.5, 4.0, .3, "VEGETABLE")
        )
        val rules = listOf(
            rule(101, setOf(MealType.BREAKFAST)).copy(frequency = PlanningFrequency.ALWAYS),
            rule(102, setOf(MealType.BREAKFAST)),
            rule(103, setOf(MealType.BREAKFAST)),
            rule(104, setOf(MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK)),
            rule(105, setOf(MealType.AFTERNOON_SNACK)),
            rule(106, setOf(MealType.LUNCH, MealType.DINNER)),
            rule(107, setOf(MealType.LUNCH, MealType.DINNER)),
            rule(108, setOf(MealType.DINNER)),
            rule(109, setOf(MealType.DINNER)),
            rule(110, setOf(MealType.LUNCH)),
            rule(111, setOf(MealType.LUNCH)),
            rule(112, setOf(MealType.DINNER)),
            rule(113, setOf(MealType.LUNCH, MealType.DINNER)),
            rule(114, MealType.entries.toSet()),
            rule(115, setOf(MealType.LUNCH, MealType.DINNER))
        )
        val goals = listOf(
            Recommendation(1700, 130, 180, 48, ""),
            Recommendation(1900, 154, 198, 52, ""),
            Recommendation(2200, 165, 250, 65, "")
        )

        goals.forEachIndexed { goalIndex, goal ->
            repeat(8) { seedIndex ->
                val result = WeeklyMenuGenerator.generate(
                    currentMeals = emptyList(), rules = rules, history = emptyList(),
                    foodsById = catalog.associateBy { it.id }, dishesById = emptyMap(),
                    recommendation = goal, seed = goalIndex * 10_000L + seedIndex
                )
                assertTrue(WeeklyMenuGenerator.isCulinarilyValid(
                    result.meals, catalog.associateBy { it.id }, emptyMap()
                ))
                result.meals.forEach { meal ->
                    meal.items.forEach { item ->
                        assertTrue(item.minimumGrams <= item.grams)
                        assertTrue(item.grams <= item.maximumGrams)
                        meal.dayAmounts.forEach { amounts ->
                            amounts.foodGrams[item.foodId]?.let { grams ->
                                assertTrue(item.minimumGrams <= grams)
                                assertTrue(grams <= item.maximumGrams)
                            }
                        }
                    }
                }
            }
        }
    }

    @Test
    fun anAcceptableVariedWeekIsNotReplacedByOneRepeatedOptimalDay() {
        // MAIN_MEAT/MAIN_FISH use a culinary portion of 150 g. Each option
        // therefore reaches the same complete daily target at that portion.
        val chicken = food(201, "Pollo", 433.333, 36.667, 60.0, 4.667, "MAIN_MEAT")
        val turkey = food(202, "Pavo", 433.333, 36.667, 60.0, 4.667, "MAIN_MEAT")
        val hake = food(203, "Merluza", 433.333, 36.667, 60.0, 4.667, "MAIN_FISH")
        val catalog = listOf(chicken, turkey, hake)
        val repeatedIncumbent = WeekDay.entries.map { day ->
            PlannedMeal(
                id = 10_000L + day.ordinal,
                type = MealType.LUNCH,
                days = setOf(day),
                items = listOf(
                    PlannedFood(turkey.id, 150.0, true, 75.0, 250.0)
                )
            )
        }
        val result = WeeklyMenuGenerator.generate(
            currentMeals = repeatedIncumbent,
            rules = listOf(
                rule(chicken.id, setOf(MealType.LUNCH)),
                rule(turkey.id, setOf(MealType.LUNCH)),
                rule(hake.id, setOf(MealType.LUNCH))
            ),
            history = emptyList(), foodsById = catalog.associateBy { it.id },
            dishesById = emptyMap(), recommendation = Recommendation(650, 55, 90, 7, ""),
            mealShares = MealType.entries.associateWith {
                if (it == MealType.LUNCH) 1.0 else 0.0
            },
            seed = 206
        )

        val fingerprints = result.meals.map { meal ->
            meal.items.map { it.foodId }.sorted()
        }.toSet()
        assertTrue("A varied acceptable repertoire produced one repeated day", fingerprints.size > 1)
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
        fat: Double,
        legacyTypeName: String? = null
    ) = Food(
        id = id,
        name = name,
        category = FoodCategory.OTHER,
        calories = calories,
        fatGrams = fat,
        carbohydrateGrams = carbs,
        proteinGrams = protein,
        fiberGrams = 1.0,
        culinaryRoles = legacyCulinaryRoles(legacyTypeName)
    )
}
