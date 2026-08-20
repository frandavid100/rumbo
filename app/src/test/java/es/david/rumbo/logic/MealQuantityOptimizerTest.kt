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
        assertTrue(optimizedBreakfast.resolvedGrams(adjustableRice, WeekDay.MONDAY) in 40.0..250.0)
        assertTrue(optimizedBreakfast.resolvedGrams(adjustableRice, WeekDay.TUESDAY) in 40.0..250.0)
        fun worstDeviation(assessment: PlanNutritionAssessment): Double = maxOf(
            abs(assessment.actual.calories - assessment.target.calories) / assessment.target.calories,
            abs(assessment.actual.proteinGrams - assessment.target.proteinGrams) / assessment.target.proteinGrams,
            abs(assessment.actual.carbohydrateGrams - assessment.target.carbohydrateGrams) /
                assessment.target.carbohydrateGrams,
            abs(assessment.actual.fatGrams - assessment.target.fatGrams) / assessment.target.fatGrams
        )
        assertTrue(worstDeviation(afterMonday) < worstDeviation(beforeMonday))
        assertTrue(result.changes.none { it.label == peach.name })
    }

    @Test
    fun optimizerUsesWholePracticalUnitsForAdjustableFood() {
        val yogurt = Food(
            4, "Yogur", FoodCategory.PROTEIN, 80.0, 3.0, 8.0, 5.0, 0.0,
            unitName = "vasito", unitAmount = 120.0, wholeUnitsOnly = true
        )
        val allFoods = (foods.values + yogurt).associateBy { it.id }
        val meals = MealType.entries.mapIndexed { index, type ->
            PlannedMeal(
                id = 100L + index,
                type = type,
                days = setOf(WeekDay.MONDAY),
                items = if (type == MealType.BREAKFAST) listOf(
                    PlannedFood(yogurt.id, 120.0, true, 60.0, 360.0)
                ) else listOf(PlannedFood(base.id, 100.0))
            )
        }

        val result = MealQuantityOptimizer.optimize(
            meals, allFoods, emptyMap(), recommendation, setOf(WeekDay.MONDAY)
        )
        val breakfast = result.meals.first { it.type == MealType.BREAKFAST }
        val yogurtAmount = breakfast.resolvedGrams(breakfast.items.single(), WeekDay.MONDAY)

        assertEquals(0.0, yogurtAmount % 120.0, 0.001)
        assertTrue(yogurtAmount in setOf(120.0, 240.0, 360.0))
    }

    @Test
    fun wholeUnitOverridesAnOlderGramRangeThatCannotContainIt() {
        val milk = Food(
            5, "Leche", FoodCategory.PROTEIN, 46.4, 1.6, 4.6, 3.4, 0.0,
            unitName = "taza", unitAmount = 230.0, wholeUnitsOnly = true
        )
        val allFoods = (foods.values + milk).associateBy { it.id }
        val meals = MealType.entries.mapIndexed { index, type ->
            PlannedMeal(
                id = 200L + index,
                type = type,
                days = setOf(WeekDay.MONDAY),
                items = if (type == MealType.BREAKFAST) listOf(
                    PlannedFood(milk.id, 100.0, true, 50.0, 150.0)
                ) else listOf(PlannedFood(base.id, 100.0))
            )
        }

        val result = MealQuantityOptimizer.optimize(
            meals, allFoods, emptyMap(), recommendation, setOf(WeekDay.MONDAY)
        )
        val breakfast = result.meals.first { it.type == MealType.BREAKFAST }
        val plannedMilk = breakfast.items.single()
        val milkAmount = breakfast.resolvedGrams(plannedMilk, WeekDay.MONDAY)

        assertEquals(230.0, milkAmount, 0.001)
        assertEquals(230.0, plannedMilk.minimumGrams, 0.001)
        assertEquals(230.0, plannedMilk.maximumGrams, 0.001)
        assertTrue(usesPracticalUnits(milkAmount, milk.practicalUnitStep()))
    }

    @Test
    fun practicalGramAmountsUseComfortableSteps() {
        assertEquals(7.0, practicalGramAmount(7.4), 0.001)
        assertEquals(35.0, practicalGramAmount(33.0), 0.001)
        assertEquals(150.0, practicalGramAmount(148.0), 0.001)
    }
}
