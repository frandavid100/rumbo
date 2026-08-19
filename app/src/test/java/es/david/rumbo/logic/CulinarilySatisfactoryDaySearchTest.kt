package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CulinarilySatisfactoryDaySearchTest {
    @Test
    fun diagnosticKnowsWhenRequiredCompanionAlreadyExistsInRepertoire() {
        val side = food(1, setOf("SIDE"))
        val evaluation = evaluationForMissingPreference(CulinaryRole.PLATE_CENTER)
        val diagnostic = CulinarilySatisfactoryDaySearch.diagnose(
            evaluation,
            listOf(rule(side, MealType.LUNCH)),
            mapOf(side.id to side)
        )
        assertTrue(diagnostic.compatibleCompanionAlreadyAvailable)
        assertTrue(diagnostic.unavailablePreferredRoles.isEmpty())
        assertTrue(diagnostic.searchStatus == ConstraintSearchStatus.SEARCH_INCONCLUSIVE)
    }

    @Test
    fun diagnosticCanExposeTrulyUnavailablePreferredRolesWithoutCallingSearchFailureInsufficiency() {
        val unrelated = food(2, setOf("BEVERAGE"))
        val evaluation = evaluationForMissingPreference(CulinaryRole.PLATE_CENTER)
        val diagnostic = CulinarilySatisfactoryDaySearch.diagnose(
            evaluation,
            listOf(rule(unrelated, MealType.LUNCH)),
            mapOf(unrelated.id to unrelated)
        )
        assertFalse(diagnostic.compatibleCompanionAlreadyAvailable)
        assertTrue(CulinaryRole.PLATE_BASE in diagnostic.unavailablePreferredRoles)
        assertTrue(CulinaryRole.SIDE in diagnostic.unavailablePreferredRoles)
        assertTrue(diagnostic.searchStatus == ConstraintSearchStatus.SEARCH_INCONCLUSIVE)
    }

    private fun evaluationForMissingPreference(role: CulinaryRole): CulinaryDaySatisfaction {
        val issue = CulinarySatisfactionIssue(
            kind = CulinarySatisfactionIssueKind.SOFT_RELATION_UNSATISFIED,
            mealType = MealType.LUNCH,
            foodId = 99L,
            foodName = "fixture",
            grams = 150.0,
            roles = setOf(role),
            message = "fixture"
        )
        return CulinaryDaySatisfaction(
            satisfactory = false,
            meals = listOf(
                CulinaryMealSatisfaction(
                    mealType = MealType.LUNCH,
                    satisfactory = false,
                    issues = listOf(issue)
                )
            )
        )
    }

    private fun food(id: Long, roles: Set<String>) = Food(
        id = id,
        name = "F$id",
        category = FoodCategory.OTHER,
        calories = 100.0,
        fatGrams = 3.0,
        carbohydrateGrams = 10.0,
        proteinGrams = 5.0,
        fiberGrams = 1.0,
        portionBasisGrams = 100.0,
        culinaryRoles = roles
    )

    private fun rule(food: Food, mealType: MealType) = PlanningRule(
        itemKind = PlannedItemKind.FOOD,
        itemId = food.id,
        allowedMealTypes = setOf(mealType),
        frequency = PlanningFrequency.NORMAL,
        preferredGrams = food.portionBasisGrams ?: 100.0
    )
}
