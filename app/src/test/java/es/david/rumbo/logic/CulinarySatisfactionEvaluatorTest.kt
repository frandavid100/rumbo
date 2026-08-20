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
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class CulinarySatisfactionEvaluatorTest {
    private val target = Recommendation(2000, 100, 250, 67, "test")

    @Before
    fun resetPolicies() {
        CulinaryPolicy.configure(emptyList())
        WeeklyMenuAcceptancePolicy.configure(NutritionToleranceSettings())
    }

    @Test
    fun completeDayWithSatisfactoryStandaloneOccurrencesReachesLevel3() {
        val mealTypes = MealType.entries
        val foods = listOf(
            balancedFood(1, FoodCategory.FRUIT, setOf("STANDALONE")),
            balancedFood(2, FoodCategory.FRUIT, setOf("STANDALONE")),
            balancedFood(3, FoodCategory.VEGETABLE, setOf("STANDALONE")),
            balancedFood(4, FoodCategory.VEGETABLE, setOf("STANDALONE")),
            balancedFood(5, FoodCategory.PROTEIN, setOf("STANDALONE"))
        )
        val meals = mealTypes.mapIndexed { index, type ->
            PlannedMeal(
                id = (index + 1).toLong(),
                type = type,
                days = setOf(WeekDay.MONDAY),
                items = listOf(PlannedFood(foods[index].id, 80.0, false))
            )
        }
        val rules = foods.mapIndexed { index, food ->
            PlanningRule(
                itemKind = PlannedItemKind.FOOD,
                itemId = food.id,
                allowedMealTypes = setOf(mealTypes[index]),
                frequency = PlanningFrequency.NORMAL,
                preferredGrams = 80.0,
                minimumFactor = 0.5,
                maximumFactor = 1.5
            )
        }
        val witness = CertifiedDayWitness(
            CertifiedDayLevel.CULINARILY_SATISFACTORY,
            11L,
            WeekDay.MONDAY,
            meals
        )

        assertTrue(
            CulinarySatisfactionEvaluator.isCulinarilySatisfactory(
                witness,
                rules,
                foods.associateBy { it.id },
                emptyMap(),
                target,
                MealDistributionPolicy.defaults
            )
        )
    }

    @Test
    fun plateCenterAndSideSatisfyEachOthersPreference() {
        val center = simpleFood(10, setOf("PLATE_CENTER"))
        val side = simpleFood(11, setOf("SIDE"))
        val result = evaluateLunch(
            listOf(
                PlannedFood(center.id, 150.0, false),
                PlannedFood(side.id, 150.0, false)
            ),
            listOf(center, side)
        )
        assertTrue(result.satisfactory)
    }

    @Test
    fun plateCenterAloneRemainsHardValidButDoesNotReachLevel3() {
        val center = simpleFood(20, setOf("PLATE_CENTER"))
        val result = evaluateLunch(
            listOf(PlannedFood(center.id, 150.0, false)),
            listOf(center)
        )
        assertFalse(result.satisfactory)
        assertTrue(result.issues.any {
            it.kind == CulinarySatisfactionIssueKind.SOFT_RELATION_UNSATISFIED
        })
    }

    @Test
    fun quantityBetweenSatisfactoryMaximumAndHardMaximumBlocksLevel3() {
        val center = simpleFood(30, setOf("PLATE_CENTER"))
        val side = simpleFood(31, setOf("SIDE"))
        val result = evaluateLunch(
            listOf(
                PlannedFood(center.id, 250.0, false),
                PlannedFood(side.id, 150.0, false)
            ),
            listOf(center, side)
        )
        assertFalse(result.satisfactory)
        assertTrue(result.issues.any {
            it.kind == CulinarySatisfactionIssueKind.QUANTITY_OUTSIDE_SATISFACTORY_RANGE &&
                it.foodId == center.id
        })
        assertTrue(250.0 <= CulinaryPolicy.defaultPolicy(CulinaryRole.PLATE_CENTER).maximumGrams!!)
    }

    @Test
    fun exactPreferredQuantityIsNotRequiredForLevel3() {
        val center = simpleFood(40, setOf("PLATE_CENTER"))
        val side = simpleFood(41, setOf("SIDE"))
        val result = evaluateLunch(
            listOf(
                PlannedFood(center.id, 175.0, false),
                PlannedFood(side.id, 180.0, false)
            ),
            listOf(center, side)
        )
        assertTrue(result.satisfactory)
        assertFalse(175.0 == CulinaryPolicy.defaultPolicy(CulinaryRole.PLATE_CENTER).preferredGrams)
        assertFalse(180.0 == CulinaryPolicy.defaultPolicy(CulinaryRole.SIDE).preferredGrams)
    }

    @Test
    fun multiroleFoodCanChooseBeverageInsteadOfActivatingCerealPreference() {
        val milk = simpleFood(50, setOf("CEREAL_BASE", "BEVERAGE"))
        val meal = PlannedMeal(
            id = 1,
            type = MealType.BREAKFAST,
            days = setOf(WeekDay.MONDAY),
            items = listOf(PlannedFood(milk.id, 250.0, false))
        )
        val result = CulinarySatisfactionEvaluator.evaluateMeal(
            WeekDay.MONDAY,
            meal,
            mapOf(milk.id to milk),
            emptyMap(),
            target,
            MealDistributionPolicy.defaults
        )
        assertTrue(result.satisfactory)
        assertEquals(CulinaryRole.BEVERAGE, result.assignedRoles.single().second)
    }

    @Test
    fun rolelessOccurrenceCannotBeCertifiedAtLevel3() {
        val legacy = simpleFood(60, emptySet())
        val result = evaluateLunch(
            listOf(PlannedFood(legacy.id, 100.0, false)),
            listOf(legacy)
        )
        assertFalse(result.satisfactory)
        assertTrue(result.issues.any { it.kind == CulinarySatisfactionIssueKind.ROLE_UNRESOLVED })
    }

    @Test
    fun repeatingSubstantialFoodAcrossMealsBlocksLevel3() {
        val food = simpleFood(70, setOf("STANDALONE"))
        val meals = listOf(MealType.BREAKFAST, MealType.MORNING_SNACK).mapIndexed { index, type ->
            PlannedMeal(
                id = index.toLong(),
                type = type,
                days = setOf(WeekDay.MONDAY),
                items = listOf(PlannedFood(food.id, 80.0, false))
            )
        }
        val result = CulinarySatisfactionEvaluator.evaluateDay(
            WeekDay.MONDAY,
            meals,
            mapOf(food.id to food),
            emptyMap(),
            target,
            MealDistributionPolicy.defaults
        )
        assertFalse(result.satisfactory)
        assertTrue(result.issues.any {
            it.kind == CulinarySatisfactionIssueKind.DAILY_REPETITION_DISCOURAGED &&
                it.foodId == food.id
        })
    }

    @Test
    fun repeatingFoodFamilyAcrossDifferentProductsBlocksLevel3() {
        val first = simpleFood(73, setOf("STANDALONE")).copy(family = "pollo")
        val second = simpleFood(74, setOf("STANDALONE")).copy(family = "Pollo")
        val meals = listOf(
            PlannedMeal(1, MealType.MORNING_SNACK, days = setOf(WeekDay.MONDAY), items = listOf(PlannedFood(first.id, 80.0, false))),
            PlannedMeal(2, MealType.AFTERNOON_SNACK, days = setOf(WeekDay.MONDAY), items = listOf(PlannedFood(second.id, 80.0, false)))
        )
        val result = CulinarySatisfactionEvaluator.evaluateDay(
            WeekDay.MONDAY, meals, listOf(first, second).associateBy { it.id }, emptyMap(),
            target, MealDistributionPolicy.defaults
        )
        assertFalse(result.satisfactory)
        assertTrue(result.issues.any { it.kind == CulinarySatisfactionIssueKind.DAILY_REPETITION_DISCOURAGED })
    }

    @Test
    fun sandwichCannotHideSecondFillingAsPlateCenter() {
        val bread = simpleFood(75, setOf("SANDWICH_BASE"))
        val turkey = simpleFood(76, setOf("SANDWICH_FILLING", "PLATE_CENTER"))
        val chicken = simpleFood(77, setOf("SANDWICH_FILLING", "PLATE_CENTER"))
        val meal = PlannedMeal(
            1, MealType.MORNING_SNACK, days = setOf(WeekDay.MONDAY),
            items = listOf(
                PlannedFood(bread.id, 70.0, false),
                PlannedFood(turkey.id, 60.0, false),
                PlannedFood(chicken.id, 60.0, false)
            )
        )
        val result = CulinarySatisfactionEvaluator.evaluateMeal(
            WeekDay.MONDAY, meal, listOf(bread, turkey, chicken).associateBy { it.id }, emptyMap(),
            target, MealDistributionPolicy.defaults
        )
        assertFalse(result.satisfactory)
    }

    @Test
    fun leafySaladNeedsDressingForLevel3() {
        val chicken = simpleFood(78, setOf("PLATE_CENTER"))
        val beans = simpleFood(79, setOf("PLATE_BASE"))
        val leaves = simpleFood(80, setOf("SIDE")).copy(name = "Canónigos")
        val withoutDressing = evaluateLunch(
            listOf(
                PlannedFood(chicken.id, 150.0, false),
                PlannedFood(beans.id, 100.0, false),
                PlannedFood(leaves.id, 150.0, false)
            ),
            listOf(chicken, beans, leaves)
        )
        assertFalse(withoutDressing.satisfactory)

        val dressing = simpleFood(81, setOf("SAUCE_DRESSING"))
        val withDressing = evaluateLunch(
            listOf(
                PlannedFood(chicken.id, 150.0, false),
                PlannedFood(beans.id, 100.0, false),
                PlannedFood(leaves.id, 150.0, false),
                PlannedFood(dressing.id, 30.0, false)
            ),
            listOf(chicken, beans, leaves, dressing)
        )
        assertTrue(withDressing.satisfactory)
    }

    @Test
    fun roleCompatibilityPreventsCoatingAtBreakfast() {
        val coating = simpleFood(71, setOf("COATING"))
        val center = simpleFood(72, setOf("PLATE_CENTER"))
        val meal = PlannedMeal(
            id = 1,
            type = MealType.BREAKFAST,
            days = setOf(WeekDay.MONDAY),
            items = listOf(
                PlannedFood(coating.id, 30.0, false),
                PlannedFood(center.id, 150.0, false)
            )
        )
        val result = CulinarySatisfactionEvaluator.evaluateMeal(
            WeekDay.MONDAY,
            meal,
            listOf(coating, center).associateBy { it.id },
            emptyMap(),
            target,
            MealDistributionPolicy.defaults
        )
        assertFalse(result.satisfactory)
    }

    private fun evaluateLunch(
        items: List<PlannedFood>,
        foods: List<Food>
    ): CulinaryMealSatisfaction {
        val meal = PlannedMeal(
            id = 1,
            type = MealType.LUNCH,
            days = setOf(WeekDay.MONDAY),
            items = items
        )
        return CulinarySatisfactionEvaluator.evaluateMeal(
            WeekDay.MONDAY,
            meal,
            foods.associateBy { it.id },
            emptyMap(),
            target,
            MealDistributionPolicy.defaults
        )
    }

    private fun simpleFood(id: Long, roles: Set<String>) = Food(
        id = id,
        name = "F$id",
        category = FoodCategory.OTHER,
        calories = 100.0,
        fatGrams = 3.0,
        carbohydrateGrams = 10.0,
        proteinGrams = 10.0,
        fiberGrams = 2.0,
        culinaryRoles = roles
    )

    private fun balancedFood(id: Long, category: FoodCategory, roles: Set<String>) = Food(
        id = id,
        name = "F$id",
        category = category,
        calories = 500.0,
        fatGrams = 16.75,
        carbohydrateGrams = 62.5,
        proteinGrams = 25.0,
        fiberGrams = 8.0,
        culinaryRoles = roles
    )
}
