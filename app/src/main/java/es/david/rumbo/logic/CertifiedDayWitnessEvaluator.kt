package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation

object CertifiedDayWitnessEvaluator {
    fun fromMenuWitness(
        witness: MenuWitness,
        level: CertifiedDayLevel = CertifiedDayLevel.VIABLE
    ): CertifiedDayWitness? {
        val days = witness.meals.flatMap { it.days }.distinct()
        if (days.size != 1) return null
        return CertifiedDayWitness(
            level = level,
            seed = witness.seed,
            day = days.single(),
            meals = witness.meals,
            fingerprint = witness.fingerprint
        ).takeIf { it.isStructurallyValid() }
    }

    fun isViable(
        witness: CertifiedDayWitness,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): Boolean {
        if (witness.level != CertifiedDayLevel.VIABLE || !witness.isStructurallyValid()) return false
        val constraints = MenuConstraintModel.fromLegacyData(rules, foodsById, mealShares)
        if (constraints.structuralViolations.isNotEmpty()) return false
        val activeRules = constraints.activeRules
        val activeByFood = activeRules.groupBy { it.itemId }
        val activeMealTypes = constraints.activeMealTypes
        val meals = witness.meals

        if (meals.map { it.type }.toSet() != activeMealTypes) return false
        if (meals.any { it.type !in activeMealTypes }) return false

        meals.forEach { meal ->
            meal.items.forEach { item ->
                val compatible = activeByFood[item.foodId].orEmpty().any { rule ->
                    meal.type in rule.allowedMealTypes && rule.frequency != PlanningFrequency.NEVER
                }
                if (!compatible) return false
            }
            meal.dishes.forEach { plannedDish ->
                val dish = dishesById[plannedDish.dishId] ?: return false
                if (meal.type !in dish.allowedMealTypes) return false
                if (dish.ingredients.any { ingredient ->
                        activeByFood[ingredient.foodId].orEmpty().none { rule ->
                            meal.type in rule.allowedMealTypes && rule.frequency != PlanningFrequency.NEVER
                        }
                    }
                ) return false
            }
        }

        activeRules.filter { it.frequency == PlanningFrequency.ALWAYS }.forEach { rule ->
            rule.allowedMealTypes.intersect(activeMealTypes).forEach { mealType ->
                val meal = meals.singleOrNull { it.type == mealType } ?: return false
                val direct = meal.items.any { it.foodId == rule.itemId }
                val inDish = meal.dishes.any { plannedDish ->
                    dishesById[plannedDish.dishId]?.ingredients?.any { it.foodId == rule.itemId } == true
                }
                if (!direct && !inDish) return false
            }
        }

        if (!WeeklyMenuGenerator.isCulinarilyValid(meals, foodsById, dishesById)) return false
        val assessment = MealPlanEvaluator.assessDay(
            witness.day, meals, foodsById, dishesById, recommendation
        )
        return WeeklyMenuAcceptancePolicy.isDayAcceptable(assessment, activeMealTypes)
    }
}
