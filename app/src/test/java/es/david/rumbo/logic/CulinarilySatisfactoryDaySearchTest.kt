package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import org.junit.Assert.assertFalse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CulinarilySatisfactoryDaySearchTest {
    @Test
    fun diagnosticKnowsWhenRequiredCompanionAlreadyExistsInRepertoire() {
        val center = food(99, setOf("PLATE_CENTER"))
        val side = food(1, setOf("SIDE"))
        val evaluation = evaluationForMissingPreference(center.id, CulinaryRole.PLATE_CENTER)
        val diagnostic = CulinarilySatisfactoryDaySearch.diagnose(
            evaluation,
            listOf(rule(center, MealType.LUNCH), rule(side, MealType.LUNCH)),
            mapOf(center.id to center, side.id to side)
        )
        assertTrue(diagnostic.compatibleCompanionAlreadyAvailable)
        assertTrue(diagnostic.unavailablePreferredRoles.isEmpty())
        assertTrue(diagnostic.searchStatus == ConstraintSearchStatus.SEARCH_INCONCLUSIVE)
    }

    @Test
    fun optionalSourceDoesNotTurnBoundedSearchFailureIntoAddFoodAdvice() {
        val center = food(99, setOf("PLATE_CENTER"))
        val unrelated = food(2, setOf("BEVERAGE"))
        val evaluation = evaluationForMissingPreference(center.id, CulinaryRole.PLATE_CENTER)
        val diagnostic = CulinarilySatisfactoryDaySearch.diagnose(
            evaluation,
            listOf(rule(center, MealType.LUNCH), rule(unrelated, MealType.LUNCH)),
            mapOf(center.id to center, unrelated.id to unrelated)
        )
        assertFalse(diagnostic.compatibleCompanionAlreadyAvailable)
        assertTrue(diagnostic.unavailablePreferredRoles.isEmpty())
        assertTrue(diagnostic.searchStatus == ConstraintSearchStatus.SEARCH_INCONCLUSIVE)
    }

    @Test
    fun diagnosticCanExposeCompanionOnlyWhenSingleRoleSourceIsMandatory() {
        val center = food(99, setOf("PLATE_CENTER"))
        val unrelated = food(2, setOf("BEVERAGE"))
        val evaluation = evaluationForMissingPreference(center.id, CulinaryRole.PLATE_CENTER)
        val mandatoryCenter = rule(center, MealType.LUNCH).copy(frequency = PlanningFrequency.ALWAYS)
        val diagnostic = CulinarilySatisfactoryDaySearch.diagnose(
            evaluation,
            listOf(mandatoryCenter, rule(unrelated, MealType.LUNCH)),
            mapOf(center.id to center, unrelated.id to unrelated)
        )
        assertFalse(diagnostic.compatibleCompanionAlreadyAvailable)
        assertTrue(CulinaryRole.PLATE_BASE in diagnostic.unavailablePreferredRoles)
        assertTrue(CulinaryRole.SIDE in diagnostic.unavailablePreferredRoles)
        assertTrue(diagnostic.searchStatus == ConstraintSearchStatus.SEARCH_INCONCLUSIVE)
    }

    @Test
    fun mandatoryMultiRoleSourceWithStandaloneEscapeDoesNotClaimCompanionMissing() {
        val versatile = food(99, setOf("PLATE_CENTER", "STANDALONE"))
        val evaluation = evaluationForMissingPreference(versatile.id, CulinaryRole.PLATE_CENTER)
        val diagnostic = CulinarilySatisfactoryDaySearch.diagnose(
            evaluation,
            listOf(
                rule(versatile, MealType.LUNCH).copy(frequency = PlanningFrequency.ALWAYS)
            ),
            mapOf(versatile.id to versatile)
        )
        assertFalse(diagnostic.compatibleCompanionAlreadyAvailable)
        assertTrue(diagnostic.unavailablePreferredRoles.isEmpty())
    }

    @Test
    fun hardRoleDependencyBeatsIncidentalQuantityAndFindsExistingDisabledCompanion() {
        val filling = food(10, setOf("PLATE_CENTER", "SANDWICH_FILLING")).copy(name = "Jamón")
        val bread = food(20, setOf("SANDWICH_BASE", "PLATE_BASE")).copy(name = "Pan")
        val banana = food(30, setOf("DESSERT", "STANDALONE")).copy(name = "Plátano")
        val quantityIssue = CulinarySatisfactionIssue(
            kind = CulinarySatisfactionIssueKind.QUANTITY_OUTSIDE_SATISFACTORY_RANGE,
            mealType = MealType.BREAKFAST,
            foodId = banana.id,
            foodName = banana.name,
            grams = 400.0,
            roles = setOf(CulinaryRole.DESSERT),
            message = "fixture"
        )
        val evaluation = CulinaryDaySatisfaction(
            satisfactory = false,
            meals = listOf(
                CulinaryMealSatisfaction(
                    mealType = MealType.BREAKFAST,
                    satisfactory = false,
                    issues = listOf(quantityIssue)
                )
            )
        )
        val diagnostic = CulinarilySatisfactoryDaySearch.diagnose(
            evaluation,
            listOf(
                rule(filling, MealType.MORNING_SNACK),
                rule(bread, MealType.BREAKFAST),
                rule(banana, MealType.BREAKFAST)
            ),
            listOf(filling, bread, banana).associateBy { it.id }
        )

        val dependency = assertNotNull(diagnostic.dependencyOpportunity).let {
            diagnostic.dependencyOpportunity!!
        }
        assertEquals(filling.id, dependency.sourceFoodId)
        assertEquals(CulinaryRole.SANDWICH_FILLING, dependency.sourceRole)
        assertEquals(CulinaryRole.SANDWICH_BASE, dependency.requiredRole)
        assertEquals(MealType.MORNING_SNACK, dependency.mealType)
        assertEquals("Pan", dependency.existingCompatibleFoodName)
        assertTrue(dependency.hardRequirement)
    }

    private fun evaluationForMissingPreference(
        foodId: Long,
        role: CulinaryRole
    ): CulinaryDaySatisfaction {
        val issue = CulinarySatisfactionIssue(
            kind = CulinarySatisfactionIssueKind.SOFT_RELATION_UNSATISFIED,
            mealType = MealType.LUNCH,
            foodId = foodId,
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
