package es.david.rumbo.logic

import es.david.rumbo.model.Food
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule

data class InitialRepertoireRequirement(
    val role: String,
    val target: Int,
    val current: Int,
    val singular: String,
    val plural: String,
    val minimumMealsPerFood: Int = 1
) {
    val missing: Int get() = (target - current).coerceAtLeast(0)
}

data class InitialRepertoireGateResult(
    val requirements: List<InitialRepertoireRequirement>
) {
    val isSatisfied: Boolean get() = requirements.all { it.missing == 0 }
    val nextMissing: InitialRepertoireRequirement? get() = requirements.firstOrNull { it.missing > 0 }
}

/** Cheap structural gate. The generator must not run before this is satisfied. */
object InitialRepertoireGate {
    private data class Definition(
        val role: String,
        val target: Int,
        val singular: String,
        val plural: String,
        val minimumMealsPerFood: Int = 1
    )

    private val definitions = listOf(
        Definition("PRIMARY_PROTEIN", 3, "proteína principal", "proteínas principales", 2),
        Definition("PRIMARY_CARBOHYDRATE", 3, "hidrato principal", "hidratos principales"),
        Definition("CONCENTRATED_FAT", 1, "grasa principal", "grasas principales"),
        Definition("COMPLEMENTARY_PROTEIN", 3, "proteína complementaria", "proteínas complementarias"),
        Definition("COMPLEMENTARY_CARBOHYDRATE", 3, "hidrato complementario", "hidratos complementarios")
    )

    fun evaluate(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        repertoireFoodIds: Set<Long>
    ): InitialRepertoireGateResult {
        val allowedMealsByFood = rules.asSequence()
            .filter {
                it.itemKind == PlannedItemKind.FOOD && it.isActive &&
                    it.frequency != PlanningFrequency.NEVER && it.itemId in repertoireFoodIds
            }
            .groupBy { it.itemId }
            .mapValues { (_, entries) ->
                entries.flatMapTo(linkedSetOf<MealType>()) { it.allowedMealTypes }
            }
        val configuredFoods = allowedMealsByFood.keys.mapNotNull(foodsById::get)
        return InitialRepertoireGateResult(definitions.map { definition ->
            val current = configuredFoods.count { food ->
                definition.role in food.nutritionalRoles &&
                    allowedMealsByFood[food.id].orEmpty().size >= definition.minimumMealsPerFood
            }
            InitialRepertoireRequirement(
                definition.role, definition.target, current,
                definition.singular, definition.plural, definition.minimumMealsPerFood
            )
        })
    }
}
