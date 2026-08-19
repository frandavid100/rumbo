package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealDistributionPolicy
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CulinaryGoldenMealsTest {
    private val target = Recommendation(2000, 100, 250, 67, "test")

    @Test
    fun riceChickenVegetableAndOilIsSatisfactory() {
        val rice = food(1, setOf("PLATE_BASE"))
        val chicken = food(2, setOf("PLATE_CENTER"))
        val vegetable = food(3, setOf("SIDE"))
        val oil = food(4, setOf("COOKING_MEDIUM"))
        assertTrue(
            evaluate(
                MealType.LUNCH,
                listOf(
                    rice to 75.0,
                    chicken to 150.0,
                    vegetable to 150.0,
                    oil to 10.0
                )
            ).satisfactory
        )
    }

    @Test
    fun fruitJuiceAndCookingOilIsNotSatisfactory() {
        val fruit = food(10, setOf("STANDALONE"))
        val juice = food(11, setOf("BEVERAGE"))
        val oil = food(12, setOf("COOKING_MEDIUM"))
        val result = evaluate(
            MealType.MORNING_SNACK,
            listOf(fruit to 150.0, juice to 150.0, oil to 10.0)
        )
        assertFalse(result.satisfactory)
        assertTrue(result.issues.any {
            it.kind == CulinarySatisfactionIssueKind.SOFT_RELATION_UNSATISFIED &&
                CulinaryRole.COOKING_MEDIUM in it.roles
        })
    }

    @Test
    fun sandwichBaseAndFillingAreMutuallyCoherent() {
        val bread = food(20, setOf("SANDWICH_BASE"))
        val filling = food(21, setOf("SANDWICH_FILLING"))
        assertTrue(
            evaluate(
                MealType.MORNING_SNACK,
                listOf(bread to 70.0, filling to 60.0)
            ).satisfactory
        )
    }

    @Test
    fun cerealBaseAndMixInAreCoherent() {
        val milk = food(30, setOf("CEREAL_BASE", "BEVERAGE"))
        val cereal = food(31, setOf("CEREAL_MIX_IN"))
        assertTrue(
            evaluate(
                MealType.BREAKFAST,
                listOf(milk to 250.0, cereal to 40.0)
            ).satisfactory
        )
    }

    @Test
    fun powderBaseAndMixInAreCoherent() {
        val milk = food(40, setOf("POWDER_BASE", "BEVERAGE"))
        val powder = food(41, setOf("POWDER_MIX_IN"))
        assertTrue(
            evaluate(
                MealType.MORNING_SNACK,
                listOf(milk to 250.0, powder to 30.0)
            ).satisfactory
        )
    }

    private fun evaluate(
        mealType: MealType,
        contents: List<Pair<Food, Double>>
    ): CulinaryMealSatisfaction {
        val meal = PlannedMeal(
            id = 1L,
            type = mealType,
            days = setOf(WeekDay.MONDAY),
            items = contents.map { (food, grams) -> PlannedFood(food.id, grams, false) }
        )
        return CulinarySatisfactionEvaluator.evaluateMeal(
            WeekDay.MONDAY,
            meal,
            contents.associate { it.first.id to it.first },
            emptyMap(),
            target,
            MealDistributionPolicy.defaults
        )
    }

    private fun food(id: Long, roles: Set<String>) = Food(
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
}
