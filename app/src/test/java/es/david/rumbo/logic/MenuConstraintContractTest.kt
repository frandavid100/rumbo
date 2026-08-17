package es.david.rumbo.logic

import es.david.rumbo.model.CulinaryType
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MenuConstraintContractTest {
    private val recommendation = Recommendation(1000, 80, 100, 35, "")
    private val lunchOnly = MealType.entries.associateWith {
        if (it == MealType.LUNCH) 1.0 else 0.0
    }

    @Test
    fun structuralMissingCoverageIsProvenInsufficient() {
        val food = food(1, "Arroz", FoodCategory.CARBOHYDRATE, 360.0, 7.0, 79.0, 0.6)
        val shares = MealType.entries.associateWith {
            if (it == MealType.LUNCH || it == MealType.DINNER) .5 else 0.0
        }
        val result = RepertoireEvaluator.evaluate(
            rules = listOf(rule(food.id).copy(allowedMealTypes = setOf(MealType.LUNCH))),
            foodsById = mapOf(food.id to food),
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = shares
        )

        assertEquals(ConstraintSearchStatus.INSUFFICIENT, result.searchStatus)
        assertTrue(result.constraintViolations.any {
            it.kind == ConstraintViolationKind.MISSING_MEAL_COVERAGE &&
                it.mealType == MealType.DINNER
        })
        assertNull(result.witness)
    }

    @Test
    fun mandatoryPowderWithoutAnyCompatibleBaseIsProvenInsufficient() {
        val powder = food(
            2, "Proteína en polvo", FoodCategory.PROTEIN, 360.0, 83.0, 2.0, 2.0
        ).copy(culinaryType = CulinaryType.PROTEIN_POWDER)
        val breakfastOnly = MealType.entries.associateWith {
            if (it == MealType.BREAKFAST) 1.0 else 0.0
        }
        val result = RepertoireEvaluator.evaluate(
            rules = listOf(rule(powder.id).copy(
                allowedMealTypes = setOf(MealType.BREAKFAST),
                frequency = PlanningFrequency.ALWAYS
            )),
            foodsById = mapOf(powder.id to powder),
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = breakfastOnly
        )

        assertEquals(ConstraintSearchStatus.INSUFFICIENT, result.searchStatus)
        val violation = result.constraintViolations.single {
            it.kind == ConstraintViolationKind.MISSING_REQUIRED_COMPANION
        }
        assertEquals(MealType.BREAKFAST, violation.mealType)
        assertEquals(setOf(powder.id), violation.itemIds)
        assertNull(result.witness)
    }

    @Test
    fun mandatoryDependentFoodIsNotProvenInsufficientWhenCompatibleBaseExists() {
        val powder = food(
            3, "Proteína en polvo", FoodCategory.PROTEIN, 360.0, 83.0, 2.0, 2.0
        ).copy(culinaryType = CulinaryType.PROTEIN_POWDER)
        val milk = food(
            4, "Leche", FoodCategory.PROTEIN, 60.0, 3.2, 4.8, 3.2
        ).copy(culinaryType = CulinaryType.MILK_BASE)
        val breakfastOnly = MealType.entries.associateWith {
            if (it == MealType.BREAKFAST) 1.0 else 0.0
        }
        val model = MenuConstraintModel.fromLegacyData(
            rules = listOf(
                rule(powder.id).copy(
                    allowedMealTypes = setOf(MealType.BREAKFAST),
                    frequency = PlanningFrequency.ALWAYS
                ),
                rule(milk.id).copy(allowedMealTypes = setOf(MealType.BREAKFAST))
            ),
            foodsById = mapOf(powder.id to powder, milk.id to milk),
            mealShares = breakfastOnly
        )

        assertTrue(model.structuralViolations.none {
            it.kind == ConstraintViolationKind.MISSING_REQUIRED_COMPANION
        })
    }

    @Test
    fun nutritionalFailureWithoutProofRemainsSearchInconclusive() {
        val tinyFood = food(
            5, "Ración insuficiente", FoodCategory.OTHER,
            10.0, 1.0, 1.0, 0.2
        )
        val result = RepertoireEvaluator.evaluate(
            rules = listOf(rule(tinyFood.id).copy(
                allowedMealTypes = setOf(MealType.LUNCH),
                preferredGrams = 100.0,
                minimumFactor = 1.0,
                maximumFactor = 1.0
            )),
            foodsById = mapOf(tinyFood.id to tinyFood),
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = lunchOnly
        )

        assertEquals(ConstraintSearchStatus.SEARCH_INCONCLUSIVE, result.searchStatus)
        assertTrue(result.constraintViolations.isEmpty())
        assertNull(result.witness)
    }

    @Test
    fun feasibleAssessmentCarriesReproducibleWitness() {
        val completeMeal = food(
            6, "Comida completa", FoodCategory.OTHER,
            1000.0, 80.0, 100.0, 35.0
        )
        val rules = listOf(rule(completeMeal.id).copy(
            allowedMealTypes = setOf(MealType.LUNCH),
            preferredGrams = 100.0,
            minimumFactor = 1.0,
            maximumFactor = 1.0
        ))
        val foods = mapOf(completeMeal.id to completeMeal)
        val constraints = MenuConstraintModel.fromLegacyData(rules, foods, lunchOnly)
        val result = RepertoireEvaluator.evaluate(
            rules, foods, emptyMap(), recommendation, lunchOnly
        )

        assertEquals(ConstraintSearchStatus.FEASIBLE, result.searchStatus)
        val witness = assertNotNull(result.witness).let { result.witness!! }
        val reproduced = witness.reproduce(
            constraints = constraints,
            foodsById = foods,
            dishesById = emptyMap(),
            recommendation = recommendation
        )
        assertEquals(witness.meals, reproduced.meals)
        assertEquals(witness.fingerprint, reproduced.meals.hashCode())
    }

    @Test
    fun sharedConstraintModelPreservesLegacyRuleFiltering() {
        val active = food(7, "Activo", FoodCategory.OTHER, 1000.0, 80.0, 100.0, 35.0)
        val inactive = active.copy(id = 8, name = "Inactivo")
        val model = MenuConstraintModel.fromLegacyData(
            rules = listOf(rule(active.id), rule(inactive.id).copy(isActive = false)),
            foodsById = mapOf(active.id to active, inactive.id to inactive),
            mealShares = lunchOnly
        )

        assertEquals(listOf(active.id), model.activeRules.map { it.itemId })
        assertEquals(setOf(MealType.LUNCH), model.activeMealTypes)
        assertTrue(model.structuralViolations.isEmpty())
    }

    private fun rule(id: Long) = PlanningRule(
        itemKind = PlannedItemKind.FOOD,
        itemId = id,
        allowedMealTypes = setOf(MealType.LUNCH),
        frequency = PlanningFrequency.NORMAL,
        preferredGrams = 100.0
    )

    private fun food(
        id: Long,
        name: String,
        category: FoodCategory,
        calories: Double,
        protein: Double,
        carbs: Double,
        fat: Double
    ) = Food(id, name, category, calories, fat, carbs, protein, 0.0)
}
