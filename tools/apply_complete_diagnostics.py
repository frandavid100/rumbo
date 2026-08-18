from pathlib import Path

# Replace COMPLETE search with a diagnostic result while preserving findCompleteWitness compatibility.
p = Path('app/src/main/java/es/david/rumbo/logic/CertifiedDayWitnessEvaluator.kt')
s = p.read_text()
start = s.index('    fun findCompleteWitness(')
end = s.index('    private fun completeCriteria(', start)
replacement = r'''    data class CompleteDayDiagnostic(
        val fruitMeals: Int,
        val vegetableMeals: Int,
        val fiberGrams: Double,
        val viable: Boolean,
        val limitingNutrient: NutrientKind? = null
    )

    data class CompleteDaySearchResult(
        val witness: CertifiedDayWitness?,
        val diagnostic: CompleteDayDiagnostic?
    )

    fun findCompleteWitness(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): CertifiedDayWitness? = findCompleteDay(
        rules, foodsById, dishesById, recommendation, mealShares
    ).witness

    fun findCompleteDay(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): CompleteDaySearchResult {
        val constraints = MenuConstraintModel.fromLegacyData(rules, foodsById, mealShares)
        if (constraints.structuralViolations.isNotEmpty()) return CompleteDaySearchResult(null, null)
        val seeds = listOf(11L, 37L, 89L, 131L, 197L, 251L, 313L, 401L, 509L, 607L, 701L, 809L)
        var bestDiagnostic: CompleteDayDiagnostic? = null
        var bestScore = Double.NEGATIVE_INFINITY
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
            val assessment = MealPlanEvaluator.assessDay(
                WeekDay.MONDAY, generated.meals, foodsById, dishesById, recommendation
            )
            val fruitMeals = mealsContaining(
                generated.meals, FoodCategory.FRUIT, foodsById, dishesById
            )
            val vegetableMeals = mealsContaining(
                generated.meals, FoodCategory.VEGETABLE, foodsById, dishesById
            )
            val viable = WeeklyMenuAcceptancePolicy.isDayAcceptable(
                assessment, constraints.activeMealTypes
            )
            val limiting = assessment.evaluations
                .filter { it.fit == TargetFit.OUTSIDE }
                .maxByOrNull { kotlin.math.abs(it.difference / it.target.coerceAtLeast(1.0)) }
                ?.kind
            val diagnostic = CompleteDayDiagnostic(
                fruitMeals = fruitMeals,
                vegetableMeals = vegetableMeals,
                fiberGrams = assessment.actual.fiberGrams,
                viable = viable,
                limitingNutrient = limiting
            )
            val score = (if (viable) 4.0 else 0.0) +
                fruitMeals.coerceAtMost(2) + vegetableMeals.coerceAtMost(2) +
                (assessment.actual.fiberGrams / 25.0).coerceIn(0.0, 1.0)
            if (score > bestScore) {
                bestScore = score
                bestDiagnostic = diagnostic
            }
            if (viable && fruitMeals >= 2 && vegetableMeals >= 2 && assessment.actual.fiberGrams >= 25.0) {
                val candidate = CertifiedDayWitness(
                    level = CertifiedDayLevel.COMPLETE,
                    seed = seed,
                    day = WeekDay.MONDAY,
                    meals = generated.meals,
                    fingerprint = generated.meals.hashCode()
                )
                if (isComplete(candidate, rules, foodsById, dishesById, recommendation, mealShares)) {
                    return CompleteDaySearchResult(candidate, diagnostic)
                }
            }
        }
        return CompleteDaySearchResult(null, bestDiagnostic)
    }

    private fun mealsContaining(
        meals: List<es.david.rumbo.model.PlannedMeal>,
        category: FoodCategory,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): Int = meals.count { meal ->
        val direct = meal.items.any { foodsById[it.foodId]?.category == category }
        val inDish = meal.dishes.any { plannedDish ->
            dishesById[plannedDish.dishId]?.ingredients?.any {
                foodsById[it.foodId]?.category == category
            } == true
        }
        direct || inDish
    }

'''
s = s[:start] + replacement + s[end:]
# Deduplicate local helper inside completeCriteria.
old = '''        fun mealsContaining(category: FoodCategory): Int = meals.count { meal ->
            val direct = meal.items.any { foodsById[it.foodId]?.category == category }
            val inDish = meal.dishes.any { plannedDish ->
                dishesById[plannedDish.dishId]?.ingredients?.any {
                    foodsById[it.foodId]?.category == category
                } == true
            }
            direct || inDish
        }
        return mealsContaining(FoodCategory.VEGETABLE) >= 2 && mealsContaining(FoodCategory.FRUIT) >= 2
'''
new = '''        return mealsContaining(meals, FoodCategory.VEGETABLE, foodsById, dishesById) >= 2 &&
            mealsContaining(meals, FoodCategory.FRUIT, foodsById, dishesById) >= 2
'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

# Wire diagnostic result into Home and make progress target actionable.
p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()
s = s.replace(
'''    val freshCompleteWitness by produceState<CertifiedDayWitness?>(
        initialValue = null,
''',
'''    val completeDaySearch by produceState<CertifiedDayWitnessEvaluator.CompleteDaySearchResult?>(
        initialValue = null,
''', 1)
s = s.replace(
'''        value = if (hasCertifiedViableDay && recommendation != null && !savedCompleteWitnessValid) {
            withContext(Dispatchers.Default) {
                CertifiedDayWitnessEvaluator.findCompleteWitness(
''',
'''        value = if (hasCertifiedViableDay && recommendation != null && !savedCompleteWitnessValid) {
            withContext(Dispatchers.Default) {
                CertifiedDayWitnessEvaluator.findCompleteDay(
''', 1)
s = s.replace(
'''        } else null
    }
    LaunchedEffect(
''',
'''        } else null
    }
    val freshCompleteWitness = completeDaySearch?.witness
    val completeDayDiagnostic = completeDaySearch?.diagnostic
    LaunchedEffect(
''', 1)
# Progress card call
s = s.replace(
'''                    hasCertifiedCompleteDay = hasCertifiedCompleteDay,
                    foods = data.foods,
''',
'''                    hasCertifiedCompleteDay = hasCertifiedCompleteDay,
                    completeDayDiagnostic = completeDayDiagnostic,
                    foods = data.foods,
''', 1)
# Card signature and target call
s = s.replace(
'''    hasCertifiedCompleteDay: Boolean,
    foods: List<Food>,
''',
'''    hasCertifiedCompleteDay: Boolean,
    completeDayDiagnostic: CertifiedDayWitnessEvaluator.CompleteDayDiagnostic?,
    foods: List<Food>,
''', 1)
s = s.replace(
'''        assessment, hasCertifiedViableDay, hasCertifiedCompleteDay, foods, repertoireFoodIds, planningRules
''',
'''        assessment, hasCertifiedViableDay, hasCertifiedCompleteDay, completeDayDiagnostic,
        foods, repertoireFoodIds, planningRules
''', 1)
s = s.replace(
'''            assessment, hasCertifiedViableDay, hasCertifiedCompleteDay, foods, repertoireFoodIds, planningRules
''',
'''            assessment, hasCertifiedViableDay, hasCertifiedCompleteDay, completeDayDiagnostic,
            foods, repertoireFoodIds, planningRules
''', 1)
# target signature
s = s.replace(
'''    hasCertifiedCompleteDay: Boolean,
    foods: List<Food>,
''',
'''    hasCertifiedCompleteDay: Boolean,
    completeDayDiagnostic: CertifiedDayWitnessEvaluator.CompleteDayDiagnostic?,
    foods: List<Food>,
''', 1)
# Replace generic terminal level1 message.
old = '''        return 1 to RepertoireProgressTarget(
            "Sigues en el nivel 1: Rumbo todavía no ha encontrado un único día que reúna a la vez fruta en dos comidas, verdura en dos comidas, al menos 25 g de fibra y todos los requisitos de un menú viable. Añadir más opciones de fruta, verdura y alimentos ricos en fibra aumenta las combinaciones posibles."
        )
'''
new = '''        completeDayDiagnostic?.let { diagnostic ->
            if (diagnostic.fruitMeals < 2) {
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
            if (diagnostic.fiberGrams < 25.0) {
                return 1 to RepertoireProgressTarget(
                    message = "El mejor día encontrado alcanza ${formatOneDecimal(diagnostic.fiberGrams)} g de fibra. Para el nivel 2 necesitamos al menos 25 g. Añade una opción rica en fibra para darle al generador más margen.",
                    buttonLabel = "Añadir verdura rica en fibra",
                    nutritionalRole = "VEGETABLE"
                )
            }
            if (!diagnostic.viable) {
                val role = when (diagnostic.limitingNutrient) {
                    NutrientKind.PROTEIN -> "PRIMARY_PROTEIN"
                    NutrientKind.CARBOHYDRATES -> "PRIMARY_CARBOHYDRATE"
                    NutrientKind.FAT -> "COMPLEMENTARY_FAT"
                    else -> null
                }
                val label = role?.let(::nutritionalRoleLabel)?.lowercase()
                return 1 to RepertoireProgressTarget(
                    message = "Rumbo consigue colocar fruta, verdura y fibra suficientes, pero ese día todavía queda fuera de los objetivos nutricionales. Añade otra opción eficiente para que pueda cuadrar ambas cosas a la vez.",
                    buttonLabel = label?.let { "Añadir $it" } ?: "Añadir otro alimento",
                    nutritionalRole = role
                )
            }
        }
        return 1 to RepertoireProgressTarget(
            message = "Rumbo todavía no ha encontrado un día completo. Añade una opción adicional de fruta o verdura para ampliar las combinaciones posibles.",
            buttonLabel = "Añadir otra verdura",
            nutritionalRole = "VEGETABLE"
        )
'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

# Extend tests to ensure diagnostics explain fibre failure.
p = Path('app/src/test/java/es/david/rumbo/logic/CertifiedDayWitnessCompleteTest.kt')
s = p.read_text()
insert = r'''

    @Test
    fun completeSearchReturnsActionableDiagnosticWhenNoWitnessExists() {
        val (_, rules, foods) = fixture(4.0)
        val result = CertifiedDayWitnessEvaluator.findCompleteDay(
            rules, foods, emptyMap(), target, MealDistributionPolicy.defaults
        )
        assertTrue(result.witness == null)
        assertTrue(result.diagnostic != null)
    }
'''
pos = s.rfind('\n}')
s = s[:pos] + insert + s[pos:]
p.write_text(s)
print('Applied actionable COMPLETE diagnostics')
