package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.PlanningSlot
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
        food(4, "Patata", 77.0, 2.0, 17.0, 0.1)
    )
    private val recommendation = Recommendation(2000, 140, 220, 65, "")

    @Test
    fun fixedSlotsAndAllowedMealTypesAreRespected() {
        val rules = listOf(
            rule(
                1,
                setOf(MealType.LUNCH),
                fixed = setOf(PlanningSlot(WeekDay.TUESDAY, MealType.LUNCH))
            ),
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
        val tuesdayLunch = result.meals.single {
            it.type == MealType.LUNCH && WeekDay.TUESDAY in it.days
        }
        assertEquals(1L, tuesdayLunch.items.single().foodId)
        assertTrue(result.meals.filter { it.type == MealType.LUNCH }.all {
            it.items.single().foodId in setOf(1L, 2L)
        })
        assertTrue(result.meals.filter { it.type == MealType.DINNER }.all {
            it.items.single().foodId in setOf(3L, 4L)
        })
        assertEquals(14, result.history.size)
    }

    @Test
    fun severalFixedFoodsCanShareTheSameMeal() {
        val slot = PlanningSlot(WeekDay.MONDAY, MealType.LUNCH)
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = listOf(
                rule(1, setOf(MealType.LUNCH), fixed = setOf(slot)),
                rule(2, setOf(MealType.LUNCH), fixed = setOf(slot)),
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
    fun everyConfiguredMealTypeIsGenerated() {
        val result = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = MealType.entries.mapIndexed { index, type ->
                rule((index % foods.size + 1).toLong(), setOf(type))
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

    private fun rule(
        id: Long,
        types: Set<MealType>,
        fixed: Set<PlanningSlot> = emptySet()
    ) = PlanningRule(
        itemKind = PlannedItemKind.FOOD,
        itemId = id,
        allowedMealTypes = types,
        fixedSlots = fixed,
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
