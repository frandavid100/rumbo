package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation

/**
 * Runs the proven small-repertoire level-3 composition search on a few
 * deterministic shortlists extracted from a larger repertoire.
 *
 * A larger repertoire is logically a superset of every shortlist, but thousands
 * of locally similar meal combinations can make a bounded beam discard the
 * useful one. Reducing optional alternatives is therefore a search technique,
 * not a relaxation of the contract: every returned witness is revalidated later
 * against the complete rule set.
 */
object CulinaryLevel3ShortlistSearch {
    private const val MAX_SHORTLIST_FOODS = 14

    fun find(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        baselineCompleteWitness: CertifiedDayWitness? = null,
        portionContext: PortionContext = PortionContext.GENERAL_ADULT
    ): CertifiedDayWitness? {
        val constraints = MenuConstraintModel.fromLegacyData(rules, foodsById, mealShares)
        if (constraints.structuralViolations.isNotEmpty()) return null
        val activeRules = constraints.activeRules.filter {
            it.itemKind == PlannedItemKind.FOOD && it.isActive &&
                it.frequency != PlanningFrequency.NEVER &&
                foodsById[it.itemId]?.hasComparableNutrition() == true
        }
        if (activeRules.isEmpty()) return null

        val mandatoryIds = activeRules.filter { it.frequency == PlanningFrequency.ALWAYS }
            .mapTo(linkedSetOf()) { it.itemId }
        if (mandatoryIds.size > MAX_SHORTLIST_FOODS) return null

        val mealTypes = constraints.activeMealTypes
        val activeFoods = activeRules.mapNotNull { foodsById[it.itemId] }
            .distinctBy { it.id }
        val allowedMeals = activeRules.groupBy { it.itemId }.mapValues { (_, entries) ->
            entries.flatMapTo(linkedSetOf()) { it.allowedMealTypes }
        }

        fun meals(food: Food): Set<MealType> = allowedMeals[food.id].orEmpty()
        fun comparableRatio(numerator: Double?, calories: Double?): Double =
            (numerator ?: 0.0) / (calories ?: 0.0).coerceAtLeast(20.0)
        fun fiberCapacity(food: Food): Double =
            (food.fiberGrams ?: 0.0) * (food.portionBasisGrams ?: 100.0) / 100.0
        fun structuralFood(food: Food): Boolean = CulinaryPolicy.roles(food).any { role ->
            role !in setOf(
                CulinaryRole.COOKING_MEDIUM, CulinaryRole.SAUCE_DRESSING,
                CulinaryRole.TOPPING, CulinaryRole.SEASONING,
                CulinaryRole.BINDER, CulinaryRole.COATING, CulinaryRole.SPREAD
            )
        }

        val baselineIds = baselineCompleteWitness?.meals.orEmpty()
            .flatMapTo(linkedSetOf()) { meal -> meal.items.map { it.foodId } }

        fun build(
            extraVegetables: Int,
            extraProteins: Int,
            preferBaseline: Boolean
        ): Set<Long> {
            val selected = LinkedHashSet<Long>()
            selected += mandatoryIds

            fun add(food: Food?) {
                if (food != null && (selected.size < MAX_SHORTLIST_FOODS || food.id in mandatoryIds)) {
                    selected += food.id
                }
            }
            fun addTop(values: Sequence<Food>, count: Int, score: (Food) -> Double) {
                values.distinctBy { it.id }.sortedByDescending(score).take(count).forEach(::add)
            }

            // Fruit coverage is a hard COMPLETE requirement. Selecting per meal
            // naturally keeps a breakfast/lunch fruit and a snack fruit when the
            // repertoire distinguishes those uses.
            mealTypes.sortedBy { it.ordinal }.forEach { mealType ->
                add(
                    activeFoods.asSequence()
                        .filter { it.category == FoodCategory.FRUIT && mealType in meals(it) }
                        .maxByOrNull { food ->
                            meals(food).size * 100.0 + fiberCapacity(food) -
                                (food.calories ?: 0.0) / 1000.0
                        }
                )
            }

            // Preserve the strongest fibre carriers. A high-fibre ingredient can
            // be essential to level 2/3 even if its preferred serving looks
            // caloric in one meal.
            addTop(
                activeFoods.asSequence().filter { (it.fiberGrams ?: 0.0) > 0.0 },
                2 + extraVegetables,
                ::fiberCapacity
            )

            // At least one protein-efficient structural option for every active
            // meal, plus global alternatives for lunch/dinner.
            mealTypes.sortedBy { it.ordinal }.forEach { mealType ->
                add(
                    activeFoods.asSequence()
                        .filter { mealType in meals(it) && structuralFood(it) }
                        .maxByOrNull { comparableRatio(it.proteinGrams, it.calories) }
                )
            }
            addTop(
                activeFoods.asSequence().filter(::structuralFood),
                2 + extraProteins,
                { comparableRatio(it.proteinGrams, it.calories) }
            )

            // Carbohydrate carriers and a concentrated fat source give the
            // optimiser independent levers for daily macros.
            addTop(
                activeFoods.asSequence().filter {
                    it.category == FoodCategory.CARBOHYDRATE && structuralFood(it)
                },
                3,
                { comparableRatio(it.carbohydrateGrams, it.calories) }
            )
            addTop(
                activeFoods.asSequence().filter { (it.fatGrams ?: 0.0) > 0.0 },
                1,
                { comparableRatio(it.fatGrams, it.calories) }
            )

            if (preferBaseline) {
                baselineIds.asSequence().mapNotNull(foodsById::get)
                    .sortedByDescending { food ->
                        fiberCapacity(food) * 10.0 +
                            comparableRatio(food.proteinGrams, food.calories) * 100.0
                    }.forEach(::add)
            }

            // Ensure no active meal disappears from the reduced model. Prefer a
            // non-modifier candidate because it can form a meal on its own.
            mealTypes.sortedBy { it.ordinal }.forEach { mealType ->
                if (selected.none { id -> mealType in allowedMeals[id].orEmpty() }) {
                    add(
                        activeFoods.asSequence()
                            .filter { mealType in meals(it) }
                            .sortedByDescending { structuralFood(it) }
                            .firstOrNull()
                    )
                }
            }
            return selected
        }

        val shortlists = listOf(
            build(extraVegetables = 0, extraProteins = 0, preferBaseline = false),
            build(extraVegetables = 1, extraProteins = 0, preferBaseline = false),
            build(extraVegetables = 0, extraProteins = 1, preferBaseline = true),
            build(extraVegetables = 1, extraProteins = 1, preferBaseline = true)
        ).filter { ids ->
            ids.isNotEmpty() && mandatoryIds.all(ids::contains) &&
                mealTypes.all { mealType -> ids.any { mealType in allowedMeals[it].orEmpty() } }
        }.distinct()

        shortlists.forEach { ids ->
            val reducedRules = rules.filter { rule ->
                rule.itemKind != PlannedItemKind.FOOD || rule.itemId in ids
            }
            CulinaryLevel3CompositionSearch.find(
                rules = reducedRules,
                foodsById = foodsById,
                dishesById = dishesById,
                recommendation = recommendation,
                mealShares = mealShares,
                portionContext = portionContext
            )?.let { return it }
        }
        return null
    }
}
