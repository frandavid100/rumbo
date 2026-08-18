from pathlib import Path

# --- CertifiedDayWitnessEvaluator: carry the best viable COMPLETE-progress witness forward. ---
p = Path('app/src/main/java/es/david/rumbo/logic/CertifiedDayWitnessEvaluator.kt')
s = p.read_text()
s = s.replace(
'''    data class CompleteDaySearchResult(
        val witness: CertifiedDayWitness?,
        val diagnostic: CompleteDayDiagnostic?
    )
''',
'''    data class CompleteDaySearchResult(
        val witness: CertifiedDayWitness?,
        val diagnostic: CompleteDayDiagnostic?,
        val progressWitness: CertifiedDayWitness? = null
    )
''', 1)

s = s.replace(
'''        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): CompleteDaySearchResult {
''',
'''        recommendation: Recommendation,
        mealShares: Map<MealType, Double>,
        baselineWitness: CertifiedDayWitness? = null
    ): CompleteDaySearchResult {
''', 1)

old = '''        var bestDiagnostic: CompleteDayDiagnostic? = null
        var bestScore = Double.NEGATIVE_INFINITY
        for (seed in seeds) {
'''
new = '''        var bestDiagnostic: CompleteDayDiagnostic? = null
        var bestProgressWitness: CertifiedDayWitness? = null
        var bestScore = Double.NEGATIVE_INFINITY

        fun considerProgressWitness(candidate: CertifiedDayWitness) {
            if (!isViable(candidate, rules, foodsById, dishesById, recommendation, mealShares)) return
            val assessment = MealPlanEvaluator.assessDay(
                candidate.day, candidate.meals, foodsById, dishesById, recommendation
            )
            val fruitMeals = mealsContaining(candidate.meals, FoodCategory.FRUIT, foodsById, dishesById)
            val vegetableMeals = mealsContaining(candidate.meals, FoodCategory.VEGETABLE, foodsById, dishesById)
            val limiting = assessment.evaluations
                .filter { it.fit == TargetFit.OUTSIDE }
                .maxByOrNull { kotlin.math.abs(it.difference / it.target.coerceAtLeast(1.0)) }
                ?.kind
            val diagnostic = CompleteDayDiagnostic(
                fruitMeals = fruitMeals,
                vegetableMeals = vegetableMeals,
                fiberGrams = assessment.actual.fiberGrams,
                viable = true,
                limitingNutrient = limiting,
                availableFruitMeals = availableFruitMeals,
                availableVegetableMeals = availableVegetableMeals
            )
            // Lexicographic in practice: first secure both fruit/vegetable slots, then fibre.
            val score = fruitMeals.coerceAtMost(2) * 1_000_000.0 +
                vegetableMeals.coerceAtMost(2) * 1_000_000.0 +
                assessment.actual.fiberGrams.coerceAtMost(25.0) * 1_000.0
            if (score > bestScore) {
                bestScore = score
                bestDiagnostic = diagnostic
                bestProgressWitness = candidate.copy(level = CertifiedDayLevel.VIABLE)
            }
        }

        baselineWitness?.takeIf { it.isStructurallyValid() }?.let(::considerProgressWitness)

        for (seed in seeds) {
'''
assert old in s
s = s.replace(old, new, 1)

# Replace generated candidate scoring block with persistent viable candidate consideration.
old = '''            val score = (if (viable) 4.0 else 0.0) +
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
'''
new = '''            val progressCandidate = CertifiedDayWitness(
                level = CertifiedDayLevel.VIABLE,
                seed = seed,
                day = WeekDay.MONDAY,
                meals = generated.meals,
                fingerprint = generated.meals.hashCode()
            )
            if (viable) considerProgressWitness(progressCandidate)
            if (viable && fruitMeals >= 2 && vegetableMeals >= 2 && assessment.actual.fiberGrams >= 25.0) {
                val candidate = progressCandidate.copy(level = CertifiedDayLevel.COMPLETE)
                if (isComplete(candidate, rules, foodsById, dishesById, recommendation, mealShares)) {
                    return CompleteDaySearchResult(candidate, diagnostic, progressCandidate)
                }
            }
        }
        return CompleteDaySearchResult(null, bestDiagnostic, bestProgressWitness)
'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

# --- App: pass baseline, persist better VIABLE progress witness, close overlay when SearchBar collapses. ---
p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()

old = '''                CertifiedDayWitnessEvaluator.findCompleteDay(
                    data.activeProfileData?.planningRules.orEmpty(),
                    foodsById,
                    dishesById,
                    recommendation,
                    mealShares
                )
'''
new = '''                CertifiedDayWitnessEvaluator.findCompleteDay(
                    data.activeProfileData?.planningRules.orEmpty(),
                    foodsById,
                    dishesById,
                    recommendation,
                    mealShares,
                    baselineWitness = savedViableWitness?.takeIf { savedViableWitnessValid }
                )
'''
assert old in s
s = s.replace(old, new, 1)

old = '''    val freshCompleteWitness = completeDaySearch?.witness
    val completeDayDiagnostic = completeDaySearch?.diagnostic
'''
new = '''    val freshCompleteWitness = completeDaySearch?.witness
    val completeDayDiagnostic = completeDaySearch?.diagnostic
    val completeProgressWitness = completeDaySearch?.progressWitness
'''
assert old in s
s = s.replace(old, new, 1)

# Save the best viable progress witness if it differs from the persisted one.
anchor = '''    LaunchedEffect(savedCompleteWitness, savedCompleteWitnessValid, freshCompleteWitness) {
        when {
            savedCompleteWitnessValid -> Unit
            freshCompleteWitness != null -> onSaveCertifiedDayWitness(freshCompleteWitness!!)
            savedCompleteWitness != null -> onClearCertifiedDayWitness(CertifiedDayLevel.COMPLETE)
        }
    }
'''
addition = anchor + '''    LaunchedEffect(completeProgressWitness, savedViableWitness?.fingerprint) {
        val progress = completeProgressWitness
        if (progress != null && progress.fingerprint != savedViableWitness?.fingerprint) {
            onSaveCertifiedDayWitness(progress.copy(level = CertifiedDayLevel.VIABLE))
        }
    }
'''
assert anchor in s
s = s.replace(anchor, addition, 1)

# Avoid presenting an unstable exact regression; phrase the stored/best figure as a floor.
old = '''                    message = "El mejor día encontrado alcanza ${formatOneDecimal(diagnostic.fiberGrams)} g de fibra. Para el nivel 2 necesitamos al menos 25 g. Añade una opción rica en fibra para darle al generador más margen.",
'''
new = '''                    message = "Rumbo ya ha encontrado un día viable con al menos ${formatOneDecimal(diagnostic.fiberGrams)} g de fibra. Para el nivel 2 necesitamos 25 g. Añade una opción rica en fibra para ampliar las combinaciones sin perder ese progreso.",
'''
assert old in s
s = s.replace(old, new, 1)

# When the internal Material SearchBar handles Back first and collapses, immediately dismantle overlay.
anchor = '''        BackHandler(enabled = true) { closeCatalogOverlay() }
        Surface(
'''
replacement = '''        BackHandler(enabled = true) { closeCatalogOverlay() }
        LaunchedEffect(catalogOverlaySearchState.targetValue) {
            if (catalogOverlaySearchState.targetValue == SearchBarValue.Collapsed) {
                closeCatalogOverlay()
            }
        }
        Surface(
'''
assert anchor in s
s = s.replace(anchor, replacement, 1)
p.write_text(s)

# --- Theme: keep dynamic hue, but make page background darker than cards. ---
p = Path('app/src/main/java/es/david/rumbo/ui/Theme.kt')
s = p.read_text()
old = '''private fun ColorScheme.deeperLightSurfaces(): ColorScheme = copy(
    background = surfaceContainerLow,
    surface = surfaceContainerLow,
    surfaceContainerLowest = surfaceContainerLow,
    surfaceContainerLow = surfaceContainer,
    surfaceContainer = surfaceContainerHigh,
    surfaceContainerHigh = surfaceContainerHighest,
    surfaceContainerHighest = surfaceDim
)
'''
new = '''private fun ColorScheme.deeperLightSurfaces(): ColorScheme = copy(
    // Keep Android's dynamic hue/chroma, but give the hierarchy visible depth:
    // page background is a stronger tonal surface; cards remain one step lighter.
    background = surfaceContainer,
    surface = surfaceContainerLow,
    surfaceVariant = surfaceContainer,
    surfaceContainerLowest = surfaceContainerLowest,
    surfaceContainerLow = surfaceContainerLow,
    surfaceContainer = surfaceContainer,
    surfaceContainerHigh = surfaceContainerHigh,
    surfaceContainerHighest = surfaceContainerHighest
)
'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

print('Applied stable COMPLETE progress, overlay close, and distinct dynamic surfaces')
