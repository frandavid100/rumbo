package es.david.rumbo.logic

import es.david.rumbo.model.legacyCulinaryRoles
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MenuProgressDiagnosticsTest {
    private val recommendation = Recommendation(1000, 80, 100, 35, "")
    private val lunchOnly = MealType.entries.associateWith {
        if (it == MealType.LUNCH) 1.0 else 0.0
    }

    @Test
    fun missingCoverageRecommendsOnlyViableMealCoverage() {
        val food = food(1, "Arroz", FoodCategory.CARBOHYDRATE, 360.0, 7.0, 79.0, 0.6)
        val shares = MealType.entries.associateWith {
            if (it == MealType.LUNCH || it == MealType.DINNER) .5 else 0.0
        }
        val assessment = RepertoireEvaluator.evaluate(
            rules = listOf(rule(food.id).copy(allowedMealTypes = setOf(MealType.LUNCH))),
            foodsById = mapOf(food.id to food),
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = shares
        )
        val diagnosis = assessment.progressDiagnosis

        assertEquals(MenuQualityLevel.VIABLE, diagnosis.nextPendingLevel)
        assertTrue(diagnosis.diagnostics.all { it.targetLevel == MenuQualityLevel.VIABLE })
        assertEquals(
            MenuDiagnosticKind.MISSING_MEAL_COVERAGE,
            diagnosis.diagnostics.single { it.mealType == MealType.DINNER }.kind
        )
        assertEquals(RecommendedActionKind.ADD_MEAL_OPTION, diagnosis.recommendedAction?.kind)
        assertEquals(MenuQualityLevel.VIABLE, diagnosis.recommendedAction?.targetLevel)
        assertEquals(MealType.DINNER, diagnosis.recommendedAction?.mealType)
    }

    @Test
    fun missingMandatoryCompanionProducesCulinaryActionForViableOnly() {
        val powder = food(
            2, "Proteína en polvo", FoodCategory.PROTEIN, 360.0, 83.0, 2.0, 2.0
        ).copy(culinaryRoles = legacyCulinaryRoles("PROTEIN_POWDER"))
        val breakfastOnly = MealType.entries.associateWith {
            if (it == MealType.BREAKFAST) 1.0 else 0.0
        }
        val assessment = RepertoireEvaluator.evaluate(
            rules = listOf(rule(powder.id).copy(
                allowedMealTypes = setOf(MealType.BREAKFAST),
                frequency = PlanningFrequency.ALWAYS
            )),
            foodsById = mapOf(powder.id to powder),
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = breakfastOnly
        )
        val diagnosis = assessment.progressDiagnosis

        assertEquals(MenuQualityLevel.VIABLE, diagnosis.nextPendingLevel)
        assertEquals(
            MenuDiagnosticKind.MISSING_REQUIRED_COMPANION,
            diagnosis.diagnostics.single().kind
        )
        assertEquals(
            RecommendedActionKind.ADD_COMPATIBLE_COMPANION,
            diagnosis.recommendedAction?.kind
        )
        assertEquals(MealType.BREAKFAST, diagnosis.recommendedAction?.mealType)
        assertEquals(setOf(powder.id), diagnosis.recommendedAction?.itemIds)
    }

    @Test
    fun inconclusiveSearchDoesNotPretendFoodIsMissing() {
        val tinyFood = food(3, "Ración insuficiente", FoodCategory.OTHER, 10.0, 1.0, 1.0, 0.2)
        val assessment = RepertoireEvaluator.evaluate(
            rules = listOf(rule(tinyFood.id).copy(
                preferredGrams = 100.0,
                minimumFactor = 1.0,
                maximumFactor = 1.0
            )),
            foodsById = mapOf(tinyFood.id to tinyFood),
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = lunchOnly
        )
        val diagnosis = assessment.progressDiagnosis

        assertEquals(MenuQualityLevel.VIABLE, diagnosis.nextPendingLevel)
        assertEquals(MenuDiagnosticKind.SEARCH_INCONCLUSIVE, diagnosis.diagnostics.single().kind)
        assertEquals(RecommendedActionKind.REVIEW_SEARCH, diagnosis.recommendedAction?.kind)
    }

    @Test
    fun viableAssessmentTargetsCompleteAndDoesNotInventUserAction() {
        val completeMeal = food(4, "Comida completa", FoodCategory.OTHER, 1000.0, 80.0, 100.0, 35.0)
        val assessment = RepertoireEvaluator.evaluate(
            rules = listOf(rule(completeMeal.id).copy(
                preferredGrams = 100.0,
                minimumFactor = 1.0,
                maximumFactor = 1.0
            )),
            foodsById = mapOf(completeMeal.id to completeMeal),
            dishesById = emptyMap(),
            recommendation = recommendation,
            mealShares = lunchOnly
        )
        val diagnosis = assessment.progressDiagnosis

        assertEquals(MenuQualityLevel.VIABLE, diagnosis.highestCertifiedLevel)
        assertEquals(MenuQualityLevel.COMPLETE, diagnosis.nextPendingLevel)
        assertEquals(MenuDiagnosticKind.POLICY_UNAVAILABLE, diagnosis.diagnostics.single().kind)
        assertEquals(MenuQualityLevel.COMPLETE, diagnosis.diagnostics.single().targetLevel)
        assertNull(diagnosis.recommendedAction)
    }

    @Test(expected = IllegalArgumentException::class)
    fun diagnosisRejectsRecommendationForAnyOtherLevel() {
        MenuProgressDiagnosis(
            highestCertifiedLevel = null,
            nextPendingLevel = MenuQualityLevel.VIABLE,
            diagnostics = emptyList(),
            recommendedAction = RecommendedAction(
                targetLevel = MenuQualityLevel.VARIED,
                kind = RecommendedActionKind.REVIEW_SEARCH
            )
        )
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
