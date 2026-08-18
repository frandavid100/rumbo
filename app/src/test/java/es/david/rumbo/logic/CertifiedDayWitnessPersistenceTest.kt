package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealDistributionPolicy
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import kotlin.test.Test
import kotlin.test.assertTrue

class CertifiedDayWitnessPersistenceTest {
    private val target = Recommendation(2000, 100, 250, 67, "test")

    private fun food(id: Long, kcal: Double, protein: Double, carbs: Double, fat: Double) = Food(
        id, "F$id", FoodCategory.OTHER, kcal, fat, carbs, protein, 2.0,
        culinaryRoles = setOf("STANDALONE")
    )

    @Test
    fun `adding optional foods cannot invalidate an already valid viable witness`() {
        val baseFoods = listOf(
            food(1, 500.0, 25.0, 62.5, 16.75),
            food(2, 500.0, 25.0, 62.5, 16.75),
            food(3, 500.0, 25.0, 62.5, 16.75),
            food(4, 500.0, 25.0, 62.5, 16.75),
            food(5, 500.0, 25.0, 62.5, 16.75)
        )
        val mealTypes = MealType.entries
        val meals = mealTypes.mapIndexed { index, type ->
            PlannedMeal(
                id = (index + 1).toLong(),
                type = type,
                days = setOf(WeekDay.MONDAY),
                items = listOf(PlannedFood(baseFoods[index].id, 80.0, false))
            )
        }
        val baseRules = baseFoods.mapIndexed { index, f ->
            PlanningRule(
                itemKind = PlannedItemKind.FOOD,
                itemId = f.id,
                allowedMealTypes = setOf(mealTypes[index]),
                frequency = PlanningFrequency.NORMAL,
                preferredGrams = 80.0,
                minimumFactor = 0.5,
                maximumFactor = 1.5
            )
        }
        val witness = CertifiedDayWitness(
            CertifiedDayLevel.VIABLE, 11L, WeekDay.MONDAY, meals
        )
        val foodsBefore = baseFoods.associateBy { it.id }
        assertTrue(CertifiedDayWitnessEvaluator.isViable(
            witness, baseRules, foodsBefore, emptyMap(), target, MealDistributionPolicy.defaults
        ))

        val added = listOf(
            food(101, 30.0, 2.0, 5.0, 0.2),
            food(102, 35.0, 2.0, 6.0, 0.2)
        )
        val addedRules = added.map { f ->
            PlanningRule(
                itemKind = PlannedItemKind.FOOD,
                itemId = f.id,
                allowedMealTypes = setOf(MealType.LUNCH, MealType.DINNER),
                frequency = PlanningFrequency.NORMAL,
                preferredGrams = 100.0
            )
        }
        assertTrue(CertifiedDayWitnessEvaluator.isViable(
            witness,
            baseRules + addedRules,
            (baseFoods + added).associateBy { it.id },
            emptyMap(),
            target,
            MealDistributionPolicy.defaults
        ))
    }
}
