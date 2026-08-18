from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one occurrence, got {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))

# --- WeeklyMenuGenerator: allow a bounded set of days, defaulting to the full week.
p='app/src/main/java/es/david/rumbo/logic/WeeklyMenuGenerator.kt'
replace_once(p,
'''        recommendation: Recommendation,\n        mealShares: Map<MealType, Double> = defaultMealShares,\n        seed: Long = 11L\n    ): GeneratedWeeklyMenu {''',
'''        recommendation: Recommendation,\n        mealShares: Map<MealType, Double> = defaultMealShares,\n        seed: Long = 11L,\n        days: Set<WeekDay> = WeekDay.entries.toSet()\n    ): GeneratedWeeklyMenu {\n        require(days.isNotEmpty()) { "Indica al menos un día para generar." }''')
replace_once(p,
'''        val fixedBySlot = resolveFixedSlots(foodRules, usableDishes)''',
'''        val fixedBySlot = resolveFixedSlots(foodRules, usableDishes)\n            .filterKeys { it.day in days }''')
replace_once(p,
'''        val slots = WeekDay.entries.flatMap { day ->\n            generatedTypes.map { type -> PlanningSlot(day, type) }\n        }''',
'''        val slots = WeekDay.entries.filter(days::contains).flatMap { day ->\n            generatedTypes.map { type -> PlanningSlot(day, type) }\n        }''')
replace_once(p,
'''            val optimized = MealQuantityOptimizer.optimize(\n                preserved + generated, foodsById, dishesById, recommendation,\n                mealShares = mealShares\n            ).meals''',
'''            val optimized = MealQuantityOptimizer.optimize(\n                preserved + generated, foodsById, dishesById, recommendation,\n                days = days,\n                mealShares = mealShares\n            ).meals''')
replace_once(p,
'''                optimized, assignments, recent, foodsById, dishesById, recommendation,\n                mealShares\n            )''',
'''                optimized, assignments, recent, foodsById, dishesById, recommendation,\n                mealShares, days\n            )''')
replace_once(p,
'''            diagnostics = WeekDay.entries.map { day ->\n                deviation(day, MealPlanEvaluator.assessDay(\n                    day, generatedMeals, foodsById, dishesById, recommendation\n                ))\n            }''',
'''            diagnostics = WeekDay.entries.filter(days::contains).map { day ->\n                deviation(day, MealPlanEvaluator.assessDay(\n                    day, generatedMeals, foodsById, dishesById, recommendation\n                ))\n            }''')
replace_once(p,
'''        recommendation: Recommendation,\n        mealShares: Map<MealType, Double>\n    ): Double {\n        val daily = WeekDay.entries.map {\n            MealPlanEvaluator.assessDay(it, meals, foodsById, dishesById, recommendation)\n        }\n        val deviations = daily.mapIndexed { index, assessment ->\n            deviation(WeekDay.entries[index], assessment)\n        }''',
'''        recommendation: Recommendation,\n        mealShares: Map<MealType, Double>,\n        days: Set<WeekDay>\n    ): Double {\n        val orderedDays = WeekDay.entries.filter(days::contains)\n        val daily = orderedDays.map {\n            MealPlanEvaluator.assessDay(it, meals, foodsById, dishesById, recommendation)\n        }\n        val deviations = daily.mapIndexed { index, assessment ->\n            deviation(orderedDays[index], assessment)\n        }''')

# --- Acceptance policy: expose a strict one-day acceptance gate using profile tolerances.
p='app/src/main/java/es/david/rumbo/logic/MealPlanEvaluator.kt'
marker='''    fun isAcceptable(\n        assessments: List<PlanNutritionAssessment>,\n        activeMealTypes: Set<MealType> = MealType.entries.toSet()\n    ): Boolean {'''
addition='''    fun isDayAcceptable(\n        assessment: PlanNutritionAssessment,\n        activeMealTypes: Set<MealType> = MealType.entries.toSet()\n    ): Boolean {\n        if (!assessment.actual.isComplete ||\n            activeMealTypes.any { it in assessment.missingMealTypes }\n        ) return false\n\n        fun ratio(actual: Double, target: Double) = actual / target.coerceAtLeast(1.0)\n        val tolerance = settings\n        return ratio(assessment.actual.calories, assessment.target.calories) in\n            tolerance.caloriesMinimum..tolerance.caloriesMaximum &&\n            ratio(assessment.actual.proteinGrams, assessment.target.proteinGrams) in\n                tolerance.proteinMinimum..tolerance.proteinMaximum &&\n            ratio(assessment.actual.carbohydrateGrams, assessment.target.carbohydrateGrams) in\n                tolerance.carbohydratesMinimum..tolerance.carbohydratesMaximum &&\n            ratio(assessment.actual.fatGrams, assessment.target.fatGrams) in\n                tolerance.fatMinimum..tolerance.fatMaximum\n    }\n\n'''+marker
replace_once(p, marker, addition)

# --- RepertoireEvaluator: feasibility is now proved by one acceptable day.
p='app/src/main/java/es/david/rumbo/logic/RepertoireEvaluator.kt'
replace_once(p,
'''                    recommendation = recommendation,\n                    seed = seed\n                )''',
'''                    recommendation = recommendation,\n                    seed = seed,\n                    days = setOf(WeekDay.MONDAY)\n                )''')
replace_once(p,
'''            val assessments = WeekDay.entries.map { day ->\n                MealPlanEvaluator.assessDay(day, generated.meals, foodsById, dishesById, recommendation)\n            }''',
'''            val assessments = listOf(\n                MealPlanEvaluator.assessDay(\n                    WeekDay.MONDAY, generated.meals, foodsById, dishesById, recommendation\n                )\n            )''')
replace_once(p,
'''        val acceptable = ranked.filter {\n            WeeklyMenuAcceptancePolicy.isAcceptable(it.assessments, activeMealTypes)\n        }''',
'''        val acceptable = ranked.filter {\n            WeeklyMenuAcceptancePolicy.isDayAcceptable(\n                it.assessments.single(), activeMealTypes\n            )\n        }''')

# --- Tests: prove that day generation is bounded and daily feasibility can certify independently of a week.
test=Path('app/src/test/java/es/david/rumbo/logic/CertifiedDayWitnessLevel1Test.kt')
test.write_text(r'''package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class CertifiedDayWitnessLevel1Test {
    private val recommendation = Recommendation(2000, 100, 250, 67, "test")

    private fun food(id: Long, name: String, kcal: Double, protein: Double, carbs: Double, fat: Double) =
        Food(
            id = id,
            name = name,
            category = when {
                protein >= carbs && protein >= fat -> FoodCategory.PROTEIN
                fat >= carbs -> FoodCategory.FAT
                else -> FoodCategory.CARBOHYDRATE
            },
            calories = kcal,
            proteinGrams = protein,
            carbohydrateGrams = carbs,
            fatGrams = fat,
            fiberGrams = 2.0,
            culinaryRoles = setOf("STANDALONE")
        )

    @Test
    fun `generator can search one day without constructing the rest of the week`() {
        val foods = listOf(
            food(1, "A", 200.0, 12.0, 30.0, 4.0),
            food(2, "B", 180.0, 10.0, 25.0, 5.0),
            food(3, "C", 220.0, 15.0, 28.0, 6.0),
            food(4, "D", 190.0, 11.0, 26.0, 5.0)
        ).associateBy { it.id }
        val rules = foods.values.map { f ->
            PlanningRule(
                itemKind = PlannedItemKind.FOOD,
                itemId = f.id,
                allowedMealTypes = MealType.entries.toSet(),
                frequency = PlanningFrequency.NORMAL,
                preferredGrams = 100.0,
                minimumFactor = 0.5,
                maximumFactor = 5.0
            )
        }
        val generated = WeeklyMenuGenerator.generate(
            currentMeals = emptyList(),
            rules = rules,
            history = emptyList(),
            foodsById = foods,
            dishesById = emptyMap(),
            recommendation = recommendation,
            days = setOf(WeekDay.MONDAY)
        )
        assertTrue(generated.meals.isNotEmpty())
        assertEquals(setOf(WeekDay.MONDAY), generated.meals.flatMap { it.days }.toSet())
        assertEquals(1, generated.diagnostics.size)
        assertEquals(WeekDay.MONDAY, generated.diagnostics.single().day)
    }
}
''')
print('daily witness core applied')
