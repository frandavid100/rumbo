from pathlib import Path

# 1) Choose portion policy contextually from the role actually plausible in the rule's meals.
p = Path('app/src/main/java/es/david/rumbo/logic/CulinaryPolicy.kt')
s = p.read_text()
old = '''    private fun portionRole(food: Food): CulinaryRole? = roles(food).minByOrNull { role ->
        when (role) {
            CulinaryRole.COOKING_MEDIUM, CulinaryRole.SEASONING, CulinaryRole.TOPPING,
            CulinaryRole.SAUCE_DRESSING, CulinaryRole.SPREAD, CulinaryRole.BINDER,
            CulinaryRole.COATING -> 0
            CulinaryRole.CEREAL_MIX_IN, CulinaryRole.POWDER_MIX_IN,
            CulinaryRole.SANDWICH_FILLING -> 1
            CulinaryRole.PLATE_CENTER, CulinaryRole.PLATE_BASE, CulinaryRole.SIDE -> 2
            CulinaryRole.STANDALONE, CulinaryRole.BEVERAGE, CulinaryRole.DESSERT,
            CulinaryRole.CEREAL_BASE, CulinaryRole.POWDER_BASE, CulinaryRole.SANDWICH_BASE -> 3
        }
    }

    fun applyPortion(rule: PlanningRule, food: Food): PlanningRule {
        val role = portionRole(food) ?: return rule
'''
new = '''    private fun portionRole(rule: PlanningRule, food: Food): CulinaryRole? {
        val available = roles(food)
        if (available.isEmpty()) return null
        val contextual = available.filterTo(linkedSetOf()) { role ->
            rule.allowedMealTypes.isEmpty() || rule.allowedMealTypes.any { mealType ->
                mealType in policy(role).suggestedMealTypes
            }
        }.ifEmpty { available }
        return contextual.minByOrNull { role ->
            when (role) {
                // Prefer the substantive use when more than one role is plausible.
                // Example: SIDE must win over TOPPING for vegetables in lunch/dinner.
                CulinaryRole.PLATE_CENTER, CulinaryRole.PLATE_BASE, CulinaryRole.SIDE,
                CulinaryRole.CEREAL_BASE, CulinaryRole.POWDER_BASE, CulinaryRole.SANDWICH_BASE,
                CulinaryRole.STANDALONE, CulinaryRole.BEVERAGE, CulinaryRole.DESSERT -> 0
                CulinaryRole.CEREAL_MIX_IN, CulinaryRole.POWDER_MIX_IN,
                CulinaryRole.SANDWICH_FILLING -> 1
                CulinaryRole.COOKING_MEDIUM, CulinaryRole.SEASONING, CulinaryRole.TOPPING,
                CulinaryRole.SAUCE_DRESSING, CulinaryRole.SPREAD, CulinaryRole.BINDER,
                CulinaryRole.COATING -> 2
            }
        }
    }

    fun applyPortion(rule: PlanningRule, food: Food): PlanningRule {
        val role = portionRole(rule, food) ?: return rule
'''
assert old in s, 'portionRole block not found'
s = s.replace(old, new, 1)
p.write_text(s)

# 2) Preserve the best COMPLETE attempt even when it is not yet VIABLE, so diagnostics
#    describe what the search actually tried instead of falling back to the old VIABLE witness.
p = Path('app/src/main/java/es/david/rumbo/logic/CertifiedDayWitnessEvaluator.kt')
s = p.read_text()
old = '''        var bestDiagnostic: CompleteDayDiagnostic? = null
        var bestProgressWitness: CertifiedDayWitness? = null
        var bestScore = Double.NEGATIVE_INFINITY
'''
new = '''        var bestDiagnostic: CompleteDayDiagnostic? = null
        var bestProgressWitness: CertifiedDayWitness? = null
        var bestScore = Double.NEGATIVE_INFINITY
        var bestAttemptDiagnostic: CompleteDayDiagnostic? = null
        var bestAttemptScore = Double.NEGATIVE_INFINITY
'''
assert old in s
s = s.replace(old, new, 1)

anchor = '''            val diagnostic = CompleteDayDiagnostic(
                fruitMeals = fruitMeals,
                vegetableMeals = vegetableMeals,
                fiberGrams = assessment.actual.fiberGrams,
                viable = viable,
                limitingNutrient = limiting,
                availableFruitMeals = availableFruitMeals,
                availableVegetableMeals = availableVegetableMeals
            )
            val progressCandidate = CertifiedDayWitness(
'''
replacement = '''            val diagnostic = CompleteDayDiagnostic(
                fruitMeals = fruitMeals,
                vegetableMeals = vegetableMeals,
                fiberGrams = assessment.actual.fiberGrams,
                viable = viable,
                limitingNutrient = limiting,
                availableFruitMeals = availableFruitMeals,
                availableVegetableMeals = availableVegetableMeals
            )
            val attemptScore = fruitMeals.coerceAtMost(2) * 1_000_000.0 +
                vegetableMeals.coerceAtMost(2) * 1_000_000.0 +
                assessment.actual.fiberGrams.coerceAtMost(25.0) * 1_000.0 +
                if (viable) 100.0 else 0.0
            if (attemptScore > bestAttemptScore) {
                bestAttemptScore = attemptScore
                bestAttemptDiagnostic = diagnostic
            }
            val progressCandidate = CertifiedDayWitness(
'''
assert anchor in s
s = s.replace(anchor, replacement, 1)
old = '''        return CompleteDaySearchResult(null, bestDiagnostic, bestProgressWitness)
'''
new = '''        return CompleteDaySearchResult(
            null,
            bestAttemptDiagnostic ?: bestDiagnostic,
            bestProgressWitness
        )
'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

# 3) If produce is already available for two meals, never recommend adding more of it
#    merely because heuristic search did not place it in the returned attempt.
p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()
old = '''            if (diagnostic.fruitMeals < 2) {
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
new = '''            if (diagnostic.fruitMeals < 2 && diagnostic.availableFruitMeals < 2) {
                return 1 to RepertoireProgressTarget(
                    message = "Con la configuración actual solo hay fruta disponible para ${diagnostic.availableFruitMeals} ${if (diagnostic.availableFruitMeals == 1) "comida" else "comidas"}. Para alcanzar el nivel 2 necesitamos poder colocar fruta en dos comidas distintas.",
                    buttonLabel = "Añadir otra fruta",
                    nutritionalRole = "FRUIT"
                )
            }
            if (diagnostic.vegetableMeals < 2 && diagnostic.availableVegetableMeals < 2) {
                return 1 to RepertoireProgressTarget(
                    message = "Con la configuración actual solo hay verdura disponible para ${diagnostic.availableVegetableMeals} ${if (diagnostic.availableVegetableMeals == 1) "comida" else "comidas"}. Para alcanzar el nivel 2 necesitamos poder colocar verdura en dos comidas distintas.",
                    buttonLabel = "Añadir otra verdura",
                    nutritionalRole = "VEGETABLE"
                )
            }
'''
assert old in s, 'produce guidance block not found'
s = s.replace(old, new, 1)

# Cards and search body share the same dynamic surface token.
s = s.replace(
'''    colors: CardColors = CardDefaults.cardColors(
        containerColor = MaterialTheme.colorScheme.surfaceContainerLowest
    ),
''',
'''    colors: CardColors = CardDefaults.cardColors(
        containerColor = MaterialTheme.colorScheme.surface
    ),
''', 1)

# Search overlay surface was intentionally tuned separately; align it with cards.
marker = '    if (catalogSearchOverlayOpen) {'
start = s.index(marker)
old_surface = '''        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.surfaceContainerHighest
        ) {
'''
pos = s.find(old_surface, start)
if pos >= 0:
    s = s[:pos] + s[pos:].replace(old_surface, '''        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.surface
        ) {
''', 1)
p.write_text(s)

# 4) Regression test for multi-role vegetables: lunch/dinner must use SIDE-sized portions.
p = Path('app/src/test/java/es/david/rumbo/logic/CulinaryPolicyTest.kt')
s = p.read_text()
insert_before = '''    private fun food(roles: Set<String>) = Food(
'''
test = '''    @Test
    fun vegetableSidePortionWinsOverToppingInMainMeals() {
        val vegetable = food(setOf("SIDE", "TOPPING"))
        val input = PlanningRule(
            itemKind = PlannedItemKind.FOOD,
            itemId = vegetable.id,
            allowedMealTypes = setOf(es.david.rumbo.model.MealType.LUNCH, es.david.rumbo.model.MealType.DINNER),
            frequency = PlanningFrequency.NORMAL,
            preferredGrams = 100.0
        )
        val result = CulinaryPolicy.applyPortion(input, vegetable)
        assertEquals(150.0, result.preferredGrams, 0.001)
        assertEquals(50.0, result.preferredGrams * result.minimumFactor, 0.001)
        assertEquals(300.0, result.preferredGrams * result.maximumFactor, 0.001)
    }

'''
assert insert_before in s
s = s.replace(insert_before, test + insert_before, 1)
p.write_text(s)

print('Applied Ara COMPLETE diagnostic, contextual portion roles, and card/search surface fixes')
