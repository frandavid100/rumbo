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
        fun ratio(numerator: Double?, calories: Double?): Double =
            (numerator ?: 0.0) / (calories ?: 0.0).coerceAtLeast(20.0)
        fun fiberCapacity(food: Food): Double =
            (food.fiberGrams ?: 0.0) * (food.portionBasisGrams ?: 100.0) / 100.0
        fun roles(food: Food): Set<CulinaryRole> = CulinaryPolicy.roles(food)
        fun hasRole(food: Food, role: CulinaryRole): Boolean = role in roles(food)
        fun structuralFood(food: Food): Boolean = roles(food).any { role ->
            role !in setOf(
                CulinaryRole.COOKING_MEDIUM, CulinaryRole.SAUCE_DRESSING,
                CulinaryRole.TOPPING, CulinaryRole.SEASONING,
                CulinaryRole.BINDER, CulinaryRole.COATING, CulinaryRole.SPREAD
            )
        }

        val baselineIds = baselineCompleteWitness?.meals.orEmpty()
            .flatMapTo(linkedSetOf()) { meal -> meal.items.map { it.foodId } }

        fun newSelection(): LinkedHashSet<Long> = LinkedHashSet<Long>().apply { addAll(mandatoryIds) }
        fun add(selected: LinkedHashSet<Long>, food: Food?) {
            if (food != null && (selected.size < MAX_SHORTLIST_FOODS || food.id in mandatoryIds)) {
                selected += food.id
            }
        }
        fun addTop(
            selected: LinkedHashSet<Long>,
            values: Sequence<Food>,
            count: Int,
            score: (Food) -> Double
        ) {
            values.distinctBy { it.id }.sortedByDescending(score).take(count)
                .forEach { add(selected, it) }
        }
        fun ensureMeals(selected: LinkedHashSet<Long>) {
            mealTypes.sortedBy { it.ordinal }.forEach { mealType ->
                if (selected.none { id -> mealType in allowedMeals[id].orEmpty() }) {
                    add(
                        selected,
                        activeFoods.asSequence()
                            .filter { mealType in meals(it) }
                            .sortedByDescending { structuralFood(it) }
                            .firstOrNull()
                    )
                }
            }
        }
        fun addFruitCoverage(selected: LinkedHashSet<Long>) {
            mealTypes.sortedBy { it.ordinal }.forEach { mealType ->
                add(
                    selected,
                    activeFoods.asSequence()
                        .filter { it.category == FoodCategory.FRUIT && mealType in meals(it) }
                        .maxByOrNull { food ->
                            meals(food).size * 100.0 + fiberCapacity(food) -
                                (food.calories ?: 0.0) / 1000.0
                        }
                )
            }
        }

        fun nutrientChampions(preferBaseline: Boolean): Set<Long> {
            val selected = newSelection()
            addFruitCoverage(selected)
            addTop(
                selected,
                activeFoods.asSequence().filter { (it.fiberGrams ?: 0.0) > 0.0 },
                2,
                ::fiberCapacity
            )
            mealTypes.sortedBy { it.ordinal }.forEach { mealType ->
                add(
                    selected,
                    activeFoods.asSequence()
                        .filter { mealType in meals(it) && structuralFood(it) }
                        .maxByOrNull { ratio(it.proteinGrams, it.calories) }
                )
            }
            addTop(
                selected,
                activeFoods.asSequence().filter(::structuralFood),
                2,
                { ratio(it.proteinGrams, it.calories) }
            )
            addTop(
                selected,
                activeFoods.asSequence().filter {
                    it.category == FoodCategory.CARBOHYDRATE && structuralFood(it)
                },
                3,
                { ratio(it.carbohydrateGrams, it.calories) }
            )
            addTop(
                selected,
                activeFoods.asSequence().filter { (it.fatGrams ?: 0.0) > 0.0 },
                1,
                { ratio(it.fatGrams, it.calories) }
            )
            if (preferBaseline) {
                baselineIds.asSequence().mapNotNull(foodsById::get)
                    .sortedByDescending { food ->
                        fiberCapacity(food) * 10.0 + ratio(food.proteinGrams, food.calories) * 100.0
                    }.forEach { add(selected, it) }
            }
            ensureMeals(selected)
            return selected
        }

        /**
         * Keeps one or two foods for each major culinary job instead of choosing
         * everything by nutrient efficiency. This complements the champion list:
         * a dessert/standalone protein or a dinner-only side can be crucial even
         * when it loses a global protein/fibre ranking.
         */
        fun culinaryStructure(): Set<Long> {
            val selected = newSelection()
            addFruitCoverage(selected)

            addTop(
                selected,
                activeFoods.asSequence().filter { hasRole(it, CulinaryRole.PLATE_CENTER) },
                2,
                { ratio(it.proteinGrams, it.calories) }
            )
            addTop(
                selected,
                activeFoods.asSequence().filter {
                    (hasRole(it, CulinaryRole.STANDALONE) || hasRole(it, CulinaryRole.DESSERT)) &&
                        (it.proteinGrams ?: 0.0) > 0.0
                },
                2,
                { ratio(it.proteinGrams, it.calories) }
            )
            addTop(
                selected,
                activeFoods.asSequence().filter { hasRole(it, CulinaryRole.PLATE_BASE) },
                1,
                { ratio(it.carbohydrateGrams, it.calories) }
            )
            addTop(
                selected,
                activeFoods.asSequence().filter {
                    it.category == FoodCategory.VEGETABLE &&
                        (hasRole(it, CulinaryRole.SIDE) || hasRole(it, CulinaryRole.SALAD_BASE))
                },
                1,
                ::fiberCapacity
            )
            listOf(MealType.LUNCH, MealType.DINNER).forEach { mealType ->
                add(
                    selected,
                        activeFoods.asSequence().filter {
                            it.category == FoodCategory.VEGETABLE &&
                            (hasRole(it, CulinaryRole.SIDE) || hasRole(it, CulinaryRole.SALAD_BASE)) &&
                            mealType in meals(it)
                    }.maxByOrNull { food ->
                        // Prefer a meal-specialised side after the global fibre
                        // anchor; this deliberately keeps different vegetable
                        // options without requiring them to win the same ranking.
                        (if (meals(food).size == 1) 1000.0 else 0.0) +
                            fiberCapacity(food)
                    }
                )
            }
            addTop(
                selected,
                activeFoods.asSequence().filter { hasRole(it, CulinaryRole.SAUCE_DRESSING) },
                1,
                { -(it.calories ?: 0.0) }
            )
            listOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK)
                .forEach { mealType ->
                    add(
                        selected,
                        activeFoods.asSequence().filter {
                            hasRole(it, CulinaryRole.BEVERAGE) && mealType in meals(it)
                        }.maxByOrNull { ratio(it.carbohydrateGrams, it.calories) }
                    )
                }
            addTop(
                selected,
                activeFoods.asSequence().filter {
                    hasRole(it, CulinaryRole.COOKING_MEDIUM) ||
                        hasRole(it, CulinaryRole.SAUCE_DRESSING)
                },
                1,
                { ratio(it.fatGrams, it.calories) }
            )
            ensureMeals(selected)
            return selected
        }

        fun fiberAnchored(): Set<Long> {
            val selected = LinkedHashSet<Long>()
            selected += culinaryStructure()
            val strongestFiber = activeFoods.maxByOrNull(::fiberCapacity)
            add(selected, strongestFiber)
            // Prefer the next high-fibre option not already present, but never
            // displace a structural category merely to fill the shortlist.
            activeFoods.asSequence().filter { it.id !in selected }
                .sortedByDescending(::fiberCapacity).firstOrNull()?.let { add(selected, it) }
            ensureMeals(selected)
            return selected
        }

        val shortlists = listOf(
            nutrientChampions(preferBaseline = false),
            culinaryStructure(),
            fiberAnchored(),
            nutrientChampions(preferBaseline = true)
        ).filter { ids ->
            ids.isNotEmpty() && ids.size <= MAX_SHORTLIST_FOODS &&
                mandatoryIds.all(ids::contains) &&
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
