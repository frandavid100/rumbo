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
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class CulinarilySatisfactoryWitnessRepairTest {
    private val target = Recommendation(2000, 100, 250, 67, "test")
    private val mealTypes = MealType.entries

    @Before
    fun resetPolicies() {
        CulinaryPolicy.configure(emptyList())
        WeeklyMenuAcceptancePolicy.configure(NutritionToleranceSettings())
    }

    @Test
    fun repairMovesExtremeButValidQuantityIntoSatisfactoryZoneWithoutLosingComplete() {
        val foods = baseFoods().mapIndexed { index, food ->
            if (index == 0) food.copy(portionBasisGrams = 40.0) else food
        }
        val (baseline, rules) = fixture(foods)
        val level3 = baseline.copy(level = CertifiedDayLevel.CULINARILY_SATISFACTORY)
        assertFalse(
            CulinarySatisfactionEvaluator.isCulinarilySatisfactory(
                level3, rules, foods.associateBy { it.id }, emptyMap(), target,
                MealDistributionPolicy.defaults
            )
        )

        val repaired = CulinarilySatisfactoryWitnessRepair.find(
            baseline,
            rules,
            foods.associateBy { it.id },
            emptyMap(),
            target,
            MealDistributionPolicy.defaults
        )
        assertNotNull(repaired)
        assertTrue(
            CulinarySatisfactionEvaluator.isCulinarilySatisfactory(
                repaired!!, rules, foods.associateBy { it.id }, emptyMap(), target,
                MealDistributionPolicy.defaults
            )
        )
    }

    @Test
    fun repairAddsAlreadyAvailableSideToPlateCenter() {
        val base = baseFoods().toMutableList()
        base[4] = base[4].copy(culinaryRoles = setOf("PLATE_CENTER"), portionBasisGrams = 80.0)
        val side = zeroFood(100, setOf("SIDE"), 150.0)
        val foods = base + side
        val (baseline, initialRules) = fixture(base)
        val rules = initialRules + rule(side, MealType.DINNER)

        val repaired = CulinarilySatisfactoryWitnessRepair.find(
            baseline,
            rules,
            foods.associateBy { it.id },
            emptyMap(),
            target,
            MealDistributionPolicy.defaults
        )
        assertNotNull(repaired)
        assertTrue(repaired!!.meals.single { it.type == MealType.DINNER }.items.any { it.foodId == side.id })
        assertTrue(
            CulinarySatisfactionEvaluator.isCulinarilySatisfactory(
                repaired, rules, foods.associateBy { it.id }, emptyMap(), target,
                MealDistributionPolicy.defaults
            )
        )
    }

    @Test
    fun repairRemovesOptionalCookingOilFromFruitSnackInsteadOfInventingAPlate() {
        val base = baseFoods()
        val oil = zeroFood(200, setOf("COOKING_MEDIUM"), 10.0)
        val foods = base + oil
        val (plain, initialRules) = fixture(base)
        val snackIndex = plain.meals.indexOfFirst { it.type == MealType.MORNING_SNACK }
        val meals = plain.meals.toMutableList()
        meals[snackIndex] = meals[snackIndex].copy(
            items = meals[snackIndex].items + PlannedFood(
                oil.id, 10.0, true, 5.0, 15.0
            )
        )
        val baseline = plain.copy(meals = meals, fingerprint = meals.hashCode())
        val rules = initialRules + rule(oil, MealType.MORNING_SNACK)

        assertTrue(
            CertifiedDayWitnessEvaluator.isComplete(
                baseline, rules, foods.associateBy { it.id }, emptyMap(), target,
                MealDistributionPolicy.defaults
            )
        )
        val repaired = CulinarilySatisfactoryWitnessRepair.find(
            baseline,
            rules,
            foods.associateBy { it.id },
            emptyMap(),
            target,
            MealDistributionPolicy.defaults
        )
        assertNotNull(repaired)
        assertFalse(repaired!!.meals.single { it.type == MealType.MORNING_SNACK }
            .items.any { it.foodId == oil.id })
    }

    @Test
    fun repairReplacesRepeatedFamilyWithRoleEquivalentAlternative() {
        val foods = baseFoods()
        val (plain, initialRules) = fixture(foods)
        val breakfastFood = foods[0].copy(family = "fruit-a")
        val snackAlternative = foods[1].copy(family = "fruit-b")
        val adjustedFoods = listOf(breakfastFood, snackAlternative) + foods.drop(2)
        val snackIndex = plain.meals.indexOfFirst { it.type == MealType.MORNING_SNACK }
        val meals = plain.meals.toMutableList()
        meals[snackIndex] = meals[snackIndex].copy(
            items = listOf(plain.meals[snackIndex].items.single().copy(foodId = breakfastFood.id))
        )
        val baseline = plain.copy(meals = meals, fingerprint = meals.hashCode())
        val rules = initialRules + rule(breakfastFood, MealType.MORNING_SNACK)
        val byId = adjustedFoods.associateBy { it.id }

        assertFalse(
            CulinarySatisfactionEvaluator.evaluateDay(
                baseline.day, baseline.meals, byId, emptyMap(), target,
                MealDistributionPolicy.defaults
            ).satisfactory
        )

        val repaired = CulinarilySatisfactoryWitnessRepair.find(
            baseline, rules, byId, emptyMap(), target, MealDistributionPolicy.defaults
        )

        assertNotNull(repaired)
        assertTrue(repaired!!.meals.single { it.type == MealType.MORNING_SNACK }
            .items.any { it.foodId == snackAlternative.id })
        assertTrue(
            CulinarySatisfactionEvaluator.isCulinarilySatisfactory(
                repaired, rules, byId, emptyMap(), target, MealDistributionPolicy.defaults
            )
        )
    }

    private fun fixture(foods: List<Food>): Pair<CertifiedDayWitness, List<PlanningRule>> {
        val meals = mealTypes.mapIndexed { index, type ->
            PlannedMeal(
                id = (index + 1).toLong(),
                type = type,
                days = setOf(WeekDay.MONDAY),
                items = listOf(
                    PlannedFood(
                        foods[index].id,
                        80.0,
                        adjustable = true,
                        minimumGrams = 20.0,
                        maximumGrams = 200.0
                    )
                )
            )
        }
        val rules = foods.take(5).mapIndexed { index, food ->
            rule(food, mealTypes[index])
        }
        val witness = CertifiedDayWitness(
            level = CertifiedDayLevel.COMPLETE,
            seed = 11L,
            day = WeekDay.MONDAY,
            meals = meals,
            fingerprint = meals.hashCode()
        )
        return witness to rules
    }

    private fun baseFoods(): List<Food> = listOf(
        balancedFood(1, FoodCategory.FRUIT),
        balancedFood(2, FoodCategory.FRUIT),
        balancedFood(3, FoodCategory.VEGETABLE),
        balancedFood(4, FoodCategory.VEGETABLE),
        balancedFood(5, FoodCategory.PROTEIN)
    )

    private fun balancedFood(id: Long, category: FoodCategory) = Food(
        id = id,
        name = "F$id",
        category = category,
        calories = 500.0,
        fatGrams = 16.75,
        carbohydrateGrams = 62.5,
        proteinGrams = 25.0,
        fiberGrams = 8.0,
        portionBasisGrams = 80.0,
        culinaryRoles = setOf("STANDALONE")
    )

    private fun zeroFood(id: Long, roles: Set<String>, basis: Double) = Food(
        id = id,
        name = "F$id",
        category = FoodCategory.OTHER,
        calories = 0.0,
        fatGrams = 0.0,
        carbohydrateGrams = 0.0,
        proteinGrams = 0.0,
        fiberGrams = 0.0,
        portionBasisGrams = basis,
        culinaryRoles = roles
    )

    private fun rule(food: Food, mealType: MealType) = PlanningRule(
        itemKind = PlannedItemKind.FOOD,
        itemId = food.id,
        allowedMealTypes = setOf(mealType),
        frequency = PlanningFrequency.NORMAL,
        preferredGrams = food.portionBasisGrams ?: 80.0,
        minimumFactor = 0.25,
        maximumFactor = 2.5
    )
}
