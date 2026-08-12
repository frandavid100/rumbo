package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import es.david.rumbo.model.resolvedGrams
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

class MealQuantityOptimizerTest {
    private val base = Food(1, "Base", FoodCategory.OTHER, 300.0, 8.0, 35.0, 20.0, 4.0)
    private val rice = Food(2, "Arroz", FoodCategory.CARBOHYDRATE, 350.0, 1.0, 75.0, 8.0, 2.0)
    private val peach = Food(3, "Melocotón", FoodCategory.FRUIT, 40.0, 0.2, 9.0, 0.8, 1.5)
    private val foods = listOf(base, rice, peach).associateBy { it.id }
    private val recommendation = Recommendation(2000, 115, 245, 55, "Prueba")

    @Test
    fun optimizerKeepsFixedFoodAndResolvesSharedAdjustableFoodPerDay() {
        val sharedBreakfast = PlannedMeal(
            id = 10,
            type = MealType.BREAKFAST,
            days = setOf(WeekDay.MONDAY, WeekDay.TUESDAY),
            items = listOf(
                PlannedFood(peach.id, 150.0),
                PlannedFood(rice.id, 100.0, true, 40.0, 250.0)
            )
        )
        val sharedTypes = listOf(MealType.MORNING_SNACK, MealType.LUNCH, MealType.AFTERNOON_SNACK)
            .mapIndexed { index, type ->
                PlannedMeal(
                    id = 20L + index,
                    type = type,
                    days = setOf(WeekDay.MONDAY, WeekDay.TUESDAY),
                    items = listOf(PlannedFood(base.id, 100.0))
                )
            }
        val mondayDinner = PlannedMeal(
            30, MealType.DINNER, setOf(WeekDay.MONDAY), items = listOf(PlannedFood(base.id, 100.0))
        )
        val tuesdayDinner = PlannedMeal(
            31, MealType.DINNER, setOf(WeekDay.TUESDAY), items = listOf(PlannedFood(base.id, 160.0))
        )
        val meals = listOf(sharedBreakfast) + sharedTypes + mondayDinner + tuesdayDinner
        val beforeMonday = MealPlanEvaluator.assessDay(
            WeekDay.MONDAY, meals, foods, emptyMap(), recommendation
        )

        val result = MealQuantityOptimizer.optimize(meals, foods, emptyMap(), recommendation)
        val optimizedBreakfast = result.meals.first { it.id == sharedBreakfast.id }
        val fixedPeach = optimizedBreakfast.items.first { it.foodId == peach.id }
        val adjustableRice = optimizedBreakfast.items.first { it.foodId == rice.id }
        val afterMonday = MealPlanEvaluator.assessDay(
            WeekDay.MONDAY, result.meals, foods, emptyMap(), recommendation
        )

        assertEquals(150.0, optimizedBreakfast.resolvedGrams(fixedPeach, WeekDay.MONDAY), 0.001)
        assertEquals(150.0, optimizedBreakfast.resolvedGrams(fixedPeach, WeekDay.TUESDAY), 0.001)
        assertNotEquals(
            optimizedBreakfast.resolvedGrams(adjustableRice, WeekDay.MONDAY),
            optimizedBreakfast.resolvedGrams(adjustableRice, WeekDay.TUESDAY),
            0.001
        )
        assertTrue(optimizedBreakfast.resolvedGrams(adjustableRice, WeekDay.MONDAY) in 40.0..250.0)
        assertTrue(optimizedBreakfast.resolvedGrams(adjustableRice, WeekDay.TUESDAY) in 40.0..250.0)
        assertTrue(
            abs(afterMonday.actual.calories - recommendation.calories) <
                abs(beforeMonday.actual.calories - recommendation.calories)
        )
        assertTrue(result.changes.none { it.label == peach.name })
    }
}
