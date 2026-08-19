package es.david.rumbo.logic

import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningRule

/** Structural nutritional anchors required in every certified day. */
object MajorNutritionalRolePolicy {
    const val PRIMARY_PROTEIN = "PRIMARY_PROTEIN"
    const val PRIMARY_CARBOHYDRATE = "PRIMARY_CARBOHYDRATE"
    const val CONCENTRATED_FAT = "CONCENTRATED_FAT"

    val requiredRoles = setOf(PRIMARY_PROTEIN, PRIMARY_CARBOHYDRATE, CONCENTRATED_FAT)

    private fun effectiveRoles(food: Food?): Set<String> {
        if (food == null) return emptySet()
        if (food.nutritionalRoles.isNotEmpty()) return food.nutritionalRoles
        // Compatibility for pre-taxonomy user foods. Imported products with
        // explicit roles always use those roles, so a tagged complementary
        // food can never be promoted by this fallback.
        return when (food.category) {
            FoodCategory.PROTEIN -> setOf(PRIMARY_PROTEIN)
            FoodCategory.CARBOHYDRATE -> setOf(PRIMARY_CARBOHYDRATE)
            FoodCategory.FAT -> setOf(CONCENTRATED_FAT)
            else -> emptySet()
        }
    }

    fun roles(
        rule: PlanningRule,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): Set<String> = when (rule.itemKind) {
        PlannedItemKind.FOOD -> effectiveRoles(foodsById[rule.itemId])
        PlannedItemKind.DISH -> dishesById[rule.itemId]?.ingredients.orEmpty()
            .flatMapTo(linkedSetOf()) { effectiveRoles(foodsById[it.foodId]) }
    }

    fun presentRoles(
        meals: List<PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): Set<String> = buildSet {
        meals.forEach { meal ->
            meal.items.forEach { addAll(effectiveRoles(foodsById[it.foodId])) }
            meal.dishes.forEach { dish ->
                dishesById[dish.dishId]?.ingredients.orEmpty().forEach { ingredient ->
                    addAll(effectiveRoles(foodsById[ingredient.foodId]))
                }
            }
        }
    }

    fun hasAllRequiredRoles(
        meals: List<PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): Boolean {
        val referencedFoods = buildList {
            meals.forEach { meal ->
                meal.items.mapNotNullTo(this) { foodsById[it.foodId] }
                meal.dishes.forEach { plannedDish ->
                    dishesById[plannedDish.dishId]?.ingredients.orEmpty()
                        .mapNotNullTo(this) { foodsById[it.foodId] }
                }
            }
        }
        // Persisted user foods and old unit fixtures predate nutritionalRoles.
        // Preserve those witnesses until migration; once any referenced product
        // uses the explicit taxonomy, only explicit main roles can certify it.
        if (referencedFoods.none { it.nutritionalRoles.isNotEmpty() }) return true
        val explicitRoles = referencedFoods.flatMapTo(linkedSetOf()) { it.nutritionalRoles }
        return explicitRoles.containsAll(requiredRoles)
    }
}
