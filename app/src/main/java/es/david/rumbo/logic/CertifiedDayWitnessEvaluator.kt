package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.WeekDay
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
        if (!witness.isStructurallyValid()) return false
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

    /** COMPLETE = viable + fruit in two distinct meals + vegetables in two distinct meals + >=25 g fibre. */
    fun isComplete(
        witness: CertifiedDayWitness,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): Boolean {
        if (witness.level != CertifiedDayLevel.COMPLETE || !isViable(
                witness, rules, foodsById, dishesById, recommendation, mealShares
            )) return false
        return completeCriteria(witness.day, witness.meals, foodsById, dishesById, recommendation)
    }

    fun findCompleteWitness(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): CertifiedDayWitness? {
        val constraints = MenuConstraintModel.fromLegacyData(rules, foodsById, mealShares)
        if (constraints.structuralViolations.isNotEmpty()) return null
        val seeds = listOf(11L, 37L, 89L, 131L, 197L, 251L, 313L, 401L, 509L, 607L, 701L, 809L)
        for (seed in seeds) {
            val generated = runCatching {
                WeeklyMenuGenerator.generate(
                    constraints = constraints,
                    currentMeals = emptyList(),
                    history = emptyList(),
                    foodsById = foodsById,
                    dishesById = dishesById,
                    recommendation = recommendation,
                    seed = seed,
                    days = setOf(WeekDay.MONDAY)
                )
            }.getOrNull() ?: continue
            if (!completeCriteria(WeekDay.MONDAY, generated.meals, foodsById, dishesById, recommendation)) continue
            val candidate = CertifiedDayWitness(
                level = CertifiedDayLevel.COMPLETE,
                seed = seed,
                day = WeekDay.MONDAY,
                meals = generated.meals,
                fingerprint = generated.meals.hashCode()
            )
            if (isComplete(candidate, rules, foodsById, dishesById, recommendation, mealShares)) return candidate
        }
        return null
    }

    private fun completeCriteria(
        day: WeekDay,
        meals: List<es.david.rumbo.model.PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation
    ): Boolean {
        val assessment = MealPlanEvaluator.assessDay(day, meals, foodsById, dishesById, recommendation)
        if (!WeeklyMenuAcceptancePolicy.isDayAcceptable(assessment, meals.mapTo(mutableSetOf()) { it.type })) return false
        if (assessment.actual.fiberGrams < 25.0) return false
        fun mealsContaining(category: FoodCategory): Int = meals.count { meal ->
            val direct = meal.items.any { foodsById[it.foodId]?.category == category }
            val inDish = meal.dishes.any { plannedDish ->
                dishesById[plannedDish.dishId]?.ingredients?.any {
                    foodsById[it.foodId]?.category == category
                } == true
            }
            direct || inDish
        }
        return mealsContaining(FoodCategory.VEGETABLE) >= 2 && mealsContaining(FoodCategory.FRUIT) >= 2
    }

}
