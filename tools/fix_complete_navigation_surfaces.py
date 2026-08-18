from pathlib import Path

# 1) Make COMPLETE generation actively seek fruit/vegetable coverage.
p = Path('app/src/main/java/es/david/rumbo/logic/WeeklyMenuGenerator.kt')
s = p.read_text()

s = s.replace(
'''object WeeklyMenuGenerator {
    private const val CANDIDATE_WEEKS = 8
''',
'''enum class MenuGenerationObjective { VIABLE, COMPLETE }

object WeeklyMenuGenerator {
    private const val CANDIDATE_WEEKS = 8
''', 1)

s = s.replace(
'''        seed: Long = 11L,
        days: Set<WeekDay> = WeekDay.entries.toSet()
    ): GeneratedWeeklyMenu {
''',
'''        seed: Long = 11L,
        days: Set<WeekDay> = WeekDay.entries.toSet(),
        objective: MenuGenerationObjective = MenuGenerationObjective.VIABLE
    ): GeneratedWeeklyMenu {
''', 1)

s = s.replace(
'''                    mealShare = mealShares[slot.mealType] ?: defaultMealShares.getValue(slot.mealType),
                    exploration = exploration
                )
''',
'''                    mealShare = mealShares[slot.mealType] ?: defaultMealShares.getValue(slot.mealType),
                    exploration = exploration,
                    objective = objective
                )
''', 1)

s = s.replace(
'''                mealShares, days
            )
''',
'''                mealShares, days, objective
            )
''', 1)

s = s.replace(
'''        recommendation: Recommendation,
        mealShare: Double,
        exploration: Double
    ): List<PlanningRule> {
''',
'''        recommendation: Recommendation,
        mealShare: Double,
        exploration: Double,
        objective: MenuGenerationObjective
    ): List<PlanningRule> {
''', 1)

old = '''                val nutritionalImprovement = before - after
                val minimumCalories = (chosen + addition).sumOf {
                    it.vector(slot, foodsById, dishesById).calories
                }
                val calorieCeiling = recommendation.calories * mealShare * 1.10
                if (chosen.isNotEmpty() &&
                    (nutritionalImprovement <= 0.01 || minimumCalories > calorieCeiling)
                ) {
                    return@mapNotNull null
                }
'''
new = '''                val nutritionalImprovement = before - after
                val minimumCalories = (chosen + addition).sumOf {
                    it.vector(slot, foodsById, dishesById).calories
                }
                val calorieCeiling = recommendation.calories * mealShare * 1.10
                fun categoryNeeded(category: es.david.rumbo.model.FoodCategory): Boolean {
                    if (objective != MenuGenerationObjective.COMPLETE) return false
                    val alreadyInThisMeal = chosen.any {
                        it.containsCategory(category, foodsById, dishesById)
                    }
                    if (alreadyInThisMeal) return false
                    val previousMeals = assigned.entries.count { (assignedSlot, assignedRules) ->
                        assignedSlot.day == slot.day && assignedRules.any {
                            it.containsCategory(category, foodsById, dishesById)
                        }
                    }
                    return previousMeals < 2 && addition.any {
                        it.containsCategory(category, foodsById, dishesById)
                    }
                }
                val completeUseful = categoryNeeded(es.david.rumbo.model.FoodCategory.FRUIT) ||
                    categoryNeeded(es.david.rumbo.model.FoodCategory.VEGETABLE)
                if (chosen.isNotEmpty() &&
                    ((nutritionalImprovement <= 0.01 && !completeUseful) || minimumCalories > calorieCeiling)
                ) {
                    return@mapNotNull null
                }
'''
assert old in s
s = s.replace(old, new, 1)

old = '''                val baseScore = nutritionalImprovement + frequencyBonus + varietyBonus - penalty
'''
new = '''                val completeBonus = if (objective == MenuGenerationObjective.COMPLETE) {
                    val dayAssigned = assigned.filterKeys { it.day == slot.day }.values
                    fun bonus(category: es.david.rumbo.model.FoodCategory): Double {
                        val currentHas = chosen.any { it.containsCategory(category, foodsById, dishesById) }
                        val previousCount = dayAssigned.count { assignedRules ->
                            assignedRules.any { it.containsCategory(category, foodsById, dishesById) }
                        }
                        return if (!currentHas && previousCount < 2 && addition.any {
                                it.containsCategory(category, foodsById, dishesById)
                            }) 8.0 else 0.0
                    }
                    bonus(es.david.rumbo.model.FoodCategory.FRUIT) +
                        bonus(es.david.rumbo.model.FoodCategory.VEGETABLE)
                } else 0.0
                val baseScore = nutritionalImprovement + frequencyBonus + varietyBonus + completeBonus - penalty
'''
assert old in s
s = s.replace(old, new, 1)

s = s.replace(
'''        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        days: Set<WeekDay>
    ): Double {
''',
'''        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        days: Set<WeekDay>,
        objective: MenuGenerationObjective
    ): Double {
''', 1)

old = '''        val recentPenalty = allRules.sumOf { rule ->
            history.count { it.itemKind == rule.itemKind && it.itemId == rule.itemId } * 0.15
        }
        return nutritional + mealBalancePenalty * 10.0 + compositionPenalty +
            quantityPenalty + varietyPenalty + recentPenalty
'''
new = '''        val recentPenalty = allRules.sumOf { rule ->
            history.count { it.itemKind == rule.itemKind && it.itemId == rule.itemId } * 0.15
        }
        val completePenalty = if (objective == MenuGenerationObjective.COMPLETE) {
            orderedDays.sumOf { day ->
                val dayMeals = meals.filter { day in it.days }
                fun count(category: es.david.rumbo.model.FoodCategory): Int = dayMeals.count { meal ->
                    meal.items.any { foodsById[it.foodId]?.category == category } ||
                        meal.dishes.any { plannedDish ->
                            dishesById[plannedDish.dishId]?.ingredients?.any {
                                foodsById[it.foodId]?.category == category
                            } == true
                        }
                }
                val actual = MealPlanEvaluator.assessDay(
                    day, meals, foodsById, dishesById, recommendation
                ).actual
                val missingFruit = (2 - count(es.david.rumbo.model.FoodCategory.FRUIT)).coerceAtLeast(0)
                val missingVegetable = (2 - count(es.david.rumbo.model.FoodCategory.VEGETABLE)).coerceAtLeast(0)
                val missingFiberRatio = ((25.0 - actual.fiberGrams).coerceAtLeast(0.0) / 25.0)
                (missingFruit + missingVegetable) * 250_000.0 + missingFiberRatio * 100_000.0
            }
        } else 0.0
        return nutritional + completePenalty + mealBalancePenalty * 10.0 + compositionPenalty +
            quantityPenalty + varietyPenalty + recentPenalty
'''
assert old in s
s = s.replace(old, new, 1)

insert = '''
    private fun PlanningRule.containsCategory(
        category: es.david.rumbo.model.FoodCategory,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): Boolean = when (itemKind) {
        PlannedItemKind.FOOD -> foodsById[itemId]?.category == category
        PlannedItemKind.DISH -> dishesById[itemId]?.ingredients?.any {
            foodsById[it.foodId]?.category == category
        } == true
    }

'''
pos = s.index('    private fun PlanningRule.sameItem(')
s = s[:pos] + insert + s[pos:]
p.write_text(s)

# 2) COMPLETE finder asks the generator for COMPLETE candidates and exposes potential coverage.
p = Path('app/src/main/java/es/david/rumbo/logic/CertifiedDayWitnessEvaluator.kt')
s = p.read_text()
s = s.replace(
'''    data class CompleteDayDiagnostic(
        val fruitMeals: Int,
        val vegetableMeals: Int,
        val fiberGrams: Double,
        val viable: Boolean,
        val limitingNutrient: NutrientKind? = null
    )
''',
'''    data class CompleteDayDiagnostic(
        val fruitMeals: Int,
        val vegetableMeals: Int,
        val fiberGrams: Double,
        val viable: Boolean,
        val limitingNutrient: NutrientKind? = null,
        val availableFruitMeals: Int = 0,
        val availableVegetableMeals: Int = 0
    )
''', 1)

old = '''        val constraints = MenuConstraintModel.fromLegacyData(rules, foodsById, mealShares)
        if (constraints.structuralViolations.isNotEmpty()) return CompleteDaySearchResult(null, null)
        val seeds = listOf(11L, 37L, 89L, 131L, 197L, 251L, 313L, 401L, 509L, 607L, 701L, 809L)
'''
new = '''        val constraints = MenuConstraintModel.fromLegacyData(rules, foodsById, mealShares)
        if (constraints.structuralViolations.isNotEmpty()) return CompleteDaySearchResult(null, null)
        fun availableMeals(category: FoodCategory): Int = constraints.activeMealTypes.count { mealType ->
            constraints.activeRules.any { rule ->
                mealType in rule.allowedMealTypes && rule.frequency != PlanningFrequency.NEVER &&
                    foodsById[rule.itemId]?.category == category
            }
        }
        val availableFruitMeals = availableMeals(FoodCategory.FRUIT)
        val availableVegetableMeals = availableMeals(FoodCategory.VEGETABLE)
        val seeds = listOf(11L, 37L, 89L, 131L, 197L, 251L, 313L, 401L, 509L, 607L, 701L, 809L)
'''
assert old in s
s = s.replace(old, new, 1)

s = s.replace(
'''                    seed = seed,
                    days = setOf(WeekDay.MONDAY)
                )
''',
'''                    seed = seed,
                    days = setOf(WeekDay.MONDAY),
                    objective = MenuGenerationObjective.COMPLETE
                )
''', 1)

s = s.replace(
'''                viable = viable,
                limitingNutrient = limiting
            )
''',
'''                viable = viable,
                limitingNutrient = limiting,
                availableFruitMeals = availableFruitMeals,
                availableVegetableMeals = availableVegetableMeals
            )
''', 1)
p.write_text(s)

# 3) Make level-2 guidance distinguish missing availability from a failed composition attempt.
p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()
old = '''            if (diagnostic.fruitMeals < 2) {
                return 1 to RepertoireProgressTarget(
                    message = "El mejor día encontrado solo consigue incluir fruta en ${diagnostic.fruitMeals} ${if (diagnostic.fruitMeals == 1) "comida" else "comidas"}. Para alcanzar el nivel 2 necesitamos fruta en dos comidas distintas.",
                    buttonLabel = "Añadir otra fruta",
                    nutritionalRole = "FRUIT"
                )
            }
            if (diagnostic.vegetableMeals < 2) {
                return 1 to RepertoireProgressTarget(
                    message = "El mejor día encontrado solo consigue incluir verdura en ${diagnostic.vegetableMeals} ${if (diagnostic.vegetableMeals == 1) "comida" else "comidas"}. Para alcanzar el nivel 2 necesitamos verdura en dos comidas distintas.",
                    buttonLabel = "Añadir otra verdura",
                    nutritionalRole = "VEGETABLE"
                )
            }
'''
new = '''            if (diagnostic.fruitMeals < 2) {
                val enoughAvailable = diagnostic.availableFruitMeals >= 2
                return 1 to RepertoireProgressTarget(
                    message = if (enoughAvailable) {
                        "Tienes fruta disponible para al menos dos comidas, pero el mejor día completo que Rumbo ha conseguido construir solo la coloca en ${diagnostic.fruitMeals}. Vamos a ampliar las combinaciones posibles con otra opción eficiente."
                    } else {
                        "Con la configuración actual solo hay fruta disponible para ${diagnostic.availableFruitMeals} ${if (diagnostic.availableFruitMeals == 1) "comida" else "comidas"}. Para alcanzar el nivel 2 necesitamos poder colocar fruta en dos comidas distintas."
                    },
                    buttonLabel = "Añadir otra fruta",
                    nutritionalRole = "FRUIT"
                )
            }
            if (diagnostic.vegetableMeals < 2) {
                val enoughAvailable = diagnostic.availableVegetableMeals >= 2
                return 1 to RepertoireProgressTarget(
                    message = if (enoughAvailable) {
                        "Tienes verdura disponible para al menos dos comidas, pero el mejor día completo que Rumbo ha conseguido construir solo la coloca en ${diagnostic.vegetableMeals}. Vamos a ampliar las combinaciones posibles con otra opción eficiente."
                    } else {
                        "Con la configuración actual solo hay verdura disponible para ${diagnostic.availableVegetableMeals} ${if (diagnostic.availableVegetableMeals == 1) "comida" else "comidas"}. Para alcanzar el nivel 2 necesitamos poder colocar verdura en dos comidas distintas."
                    },
                    buttonLabel = "Añadir otra verdura",
                    nutritionalRole = "VEGETABLE"
                )
            }
'''
assert old in s
s = s.replace(old, new, 1)

# 4) A common overlay close path: system back and arrow both restore the origin.
old = '''        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background
        ) {
'''
new = '''        val closeCatalogOverlay = {
            catalogOverlayTextState.setTextAndPlaceCursorAtEnd("")
            catalogOverlayMessage = null
            catalogSearchReturnPending = false
            catalogSearchSavedQuery = ""
            catalogSearchSavedScrollIndex = 0
            catalogSearchSavedScrollOffset = 0
            if (catalogSearchOriginScreenName == Screen.FOOD_DETAIL.name) {
                selectedFoodId = catalogSearchOriginFoodId
            }
            screenName = catalogSearchOriginScreenName ?: Screen.HOME.name
            catalogSearchOriginScreenName = null
            catalogSearchOriginFoodId = null
            catalogSearchOverlayOpen = false
        }
        BackHandler(enabled = true) { closeCatalogOverlay() }
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background
        ) {
'''
# only replace overlay Surface occurrence nearest state block; count may have many. Anchor with preceding LaunchedEffect ending.
anchor = '''            if (catalogSearchSavedScrollIndex > 0 || catalogSearchSavedScrollOffset > 0) {
                catalogOverlayListState.scrollToItem(
                    catalogSearchSavedScrollIndex,
                    catalogSearchSavedScrollOffset
                )
            }
        }
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background
        ) {
'''
assert anchor in s
s = s.replace(anchor, anchor.replace('        Surface(\n            modifier = Modifier.fillMaxSize(),\n            color = MaterialTheme.colorScheme.background\n        ) {\n', new), 1)

old = '''                onCloseSearch = {
                    catalogOverlayTextState.setTextAndPlaceCursorAtEnd("")
                    catalogOverlayMessage = null
                    catalogSearchReturnPending = false
                    catalogSearchSavedQuery = ""
                    catalogSearchSavedScrollIndex = 0
                    catalogSearchSavedScrollOffset = 0
                    catalogSearchOverlayOpen = false
                },
'''
new = '''                onCloseSearch = closeCatalogOverlay,
'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

# 5) Dynamic surfaces: deepen only light themes while keeping the dynamic palette itself.
p = Path('app/src/main/java/es/david/rumbo/ui/Theme.kt')
s = p.read_text()
s = s.replace('import androidx.compose.material3.MaterialTheme\n', 'import androidx.compose.material3.MaterialTheme\nimport androidx.compose.material3.ColorScheme\n', 1)
insert = '''
private fun ColorScheme.deeperLightSurfaces(): ColorScheme = copy(
    background = surfaceContainerLow,
    surface = surfaceContainerLow,
    surfaceContainerLowest = surfaceContainerLow,
    surfaceContainerLow = surfaceContainer,
    surfaceContainer = surfaceContainerHigh,
    surfaceContainerHigh = surfaceContainerHighest,
    surfaceContainerHighest = surfaceDim
)

'''
pos = s.index('@Composable\nfun RumboTheme')
s = s[:pos] + insert + s[pos:]
old = '''    val colors = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && darkTheme ->
            dynamicDarkColorScheme(context)
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            dynamicLightColorScheme(context)
        darkTheme -> DarkColors
        else -> LightColors
    }
'''
new = '''    val colors = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && darkTheme ->
            dynamicDarkColorScheme(context)
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            dynamicLightColorScheme(context).deeperLightSurfaces()
        darkTheme -> DarkColors
        else -> LightColors.deeperLightSurfaces()
    }
'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

print('Applied directed COMPLETE generation, overlay close fix, and deeper dynamic surfaces')
