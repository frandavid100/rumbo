from pathlib import Path

app = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
evaluator = Path('app/src/main/java/es/david/rumbo/logic/MealPlanEvaluator.kt')

t = app.read_text()

# --- Search app bar: let AppBarWithSearch own the full top surface and its insets. ---
t = t.replace('import androidx.compose.foundation.layout.statusBars\n', '')
t = t.replace('import androidx.compose.foundation.layout.windowInsetsTopHeight\n', '')

t = t.replace(
'''    Box(Modifier.fillMaxSize()) {
    Scaffold(
        modifier = Modifier.fillMaxSize().nestedScroll(searchScrollBehavior.nestedScrollConnection),''',
'''    Scaffold(
        modifier = Modifier.fillMaxSize().nestedScroll(searchScrollBehavior.nestedScrollConnection),''',
1
)

t = t.replace(
'''        }
    }
    Box(
        Modifier.fillMaxWidth()
            .windowInsetsTopHeight(WindowInsets.statusBars)
            .background(MaterialTheme.colorScheme.surfaceContainer)
    )
    }
}

@Composable
private fun MissingMeasurementCard''',
'''        }
    }
}

@Composable
private fun MissingMeasurementCard''',
1
)

search_anchor = '''    val query = textFieldState.text.toString()
    val normalized = normalizeSearch(query)
'''
search_colors = '''    val query = textFieldState.text.toString()
    val normalized = normalizeSearch(query)
    val appBarColors = SearchBarDefaults.appBarWithSearchColors(
        searchBarColors = SearchBarDefaults.containedColors(state = state),
        appBarContainerColor = MaterialTheme.colorScheme.surface,
        scrolledAppBarContainerColor = MaterialTheme.colorScheme.surfaceContainer,
        scrolledSearchBarContainerColor = MaterialTheme.colorScheme.surfaceContainerHighest
    )
'''
assert search_anchor in t
t = t.replace(search_anchor, search_colors, 1)

input_anchor = '''            searchBarState = state,
            onSearch = {},
            modifier = Modifier.fillMaxWidth(),'''
input_new = '''            searchBarState = state,
            colors = appBarColors.searchBarColors.inputFieldColors,
            onSearch = {},
            modifier = Modifier.fillMaxWidth(),'''
assert input_anchor in t
t = t.replace(input_anchor, input_new, 1)

appbar_old = '''    AppBarWithSearch(
        state = state,
        inputField = inputField,
        scrollBehavior = scrollBehavior,
        actions = { trailingContent() },
        modifier = Modifier.padding(horizontal = 16.dp)
    )'''
appbar_new = '''    AppBarWithSearch(
        state = state,
        inputField = inputField,
        scrollBehavior = scrollBehavior,
        colors = appBarColors,
        actions = { trailingContent() },
        modifier = Modifier.fillMaxWidth(),
        contentPadding = PaddingValues(horizontal = 16.dp)
    )'''
assert appbar_old in t
t = t.replace(appbar_old, appbar_new, 1)

# --- Weekly menu: section title + grouped collapsed rows + highlighted active card. ---
start = t.index('@Composable\nprivate fun WeeklyHomeMenuSection(')
end = t.index('\nprivate data class MenuItemLine(', start)
weekly = r'''@Composable
private fun WeeklyHomeMenuSection(
    meals: List<PlannedMeal>,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    recommendation: es.david.rumbo.model.Recommendation?,
    onOpenNextWeek: () -> Unit,
    onRegenerateWeek: () -> String?,
    onOpenMeal: (Long) -> Unit,
    onOpenFood: (Long) -> Unit,
    onOpenDish: (Long) -> Unit,
    onApplyAdjustedMeals: (List<PlannedMeal>) -> Unit
) {
    val today = WeekDay.entries[LocalDate.now().dayOfWeek.value - 1]
    val summaryKey = "WEEKLY_SUMMARY"
    var expandedSection by rememberSaveable { mutableStateOf(today.name) }
    var rebuildSheet by remember { mutableStateOf(false) }
    var optimizationPreview by remember { mutableStateOf<QuantityOptimizationResult?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    val weeklyAssessment = recommendation?.let {
        MealPlanEvaluator.assessWeek(meals, foodsById, dishesById, it)
    }

    optimizationPreview?.let { result ->
        QuantityOptimizationPreviewDialog(
            result = result,
            onApply = {
                onApplyAdjustedMeals(result.meals)
                optimizationPreview = null
            },
            onDismiss = { optimizationPreview = null }
        )
    }
    message?.let { value ->
        AlertDialog(
            onDismissRequest = { message = null },
            title = { Text("Menú semanal") },
            text = { Text(value) },
            confirmButton = { TextButton(onClick = { message = null }) { Text("Entendido") } }
        )
    }
    if (rebuildSheet) {
        ModalBottomSheet(onDismissRequest = { rebuildSheet = false }) {
            Column(
                Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text("Rehacer menú semanal", style = MaterialTheme.typography.headlineSmall)
                Text("Elige cuánto quieres cambiar.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                FilledTonalButton(
                    onClick = {
                        rebuildSheet = false
                        if (recommendation == null) {
                            message = "Necesitas una recomendación nutricional antes de ajustar el menú."
                        } else {
                            val result = MealQuantityOptimizer.optimize(meals, foodsById, dishesById, recommendation)
                            if (result.changes.isNotEmpty()) optimizationPreview = result
                            else message = "Las cantidades actuales ya son la mejor combinación encontrada dentro de los límites indicados."
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Cambiar solo las cantidades") }
                OutlinedButton(
                    onClick = {
                        rebuildSheet = false
                        message = onRegenerateWeek()
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Cambiar también los platos") }
                TextButton(onClick = { rebuildSheet = false }, Modifier.fillMaxWidth()) { Text("Cancelar") }
                Spacer(Modifier.height(12.dp))
            }
        }
    }

    @Composable
    fun SummaryCard() {
        Card(
            Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)
        ) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(
                    Modifier.fillMaxWidth().clickable { expandedSection = "" },
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Valoración nutricional", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
                    Icon(Icons.Default.KeyboardArrowUp, contentDescription = "Contraer")
                }
                weeklyAssessment?.let { TodayNutritionSummary(it) }
                Text(
                    weeklyAssessmentText(weeklyAssessment),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface
                )
                OutlinedButton(onClick = { rebuildSheet = true }, Modifier.fillMaxWidth()) {
                    Text("Rehacer menú semanal")
                }
                FilledTonalButton(onClick = onOpenNextWeek, Modifier.fillMaxWidth()) {
                    Text("Ver la semana que viene")
                }
            }
        }
    }

    @Composable
    fun DayCard(day: WeekDay) {
        val dayMeals = meals.filter { day in it.days }.associateBy { it.type }
        val assessment = recommendation?.let {
            MealPlanEvaluator.assessDay(day, meals, foodsById, dishesById, it)
        }
        Card(
            Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)
        ) {
            Column(Modifier.fillMaxWidth()) {
                Row(
                    Modifier.fillMaxWidth().clickable { expandedSection = "" }.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(day.label, Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
                    Icon(Icons.Default.KeyboardArrowUp, contentDescription = "Contraer")
                }
                Column(
                    Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    assessment?.let { TodayNutritionSummary(it) }
                    if (dayMeals.isEmpty()) {
                        Text("No hay comidas planificadas.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    MealType.entries.forEachIndexed { index, type ->
                        val meal = dayMeals[type] ?: return@forEachIndexed
                        val entries = meal.dishes.mapNotNull { planned ->
                            dishesById[planned.dishId]?.let { dish ->
                                MenuItemLine(dish.id, true, dish.name, meal.resolvedGrams(planned, day), dish.dominantCategory(foodsById))
                            }
                        } + meal.items.mapNotNull { planned ->
                            foodsById[planned.foodId]?.let { food ->
                                MenuItemLine(food.id, false, food.name, meal.resolvedGrams(planned, day), food.category)
                            }
                        }
                        Column(
                            Modifier.fillMaxWidth().clickable { onOpenMeal(meal.id) }.padding(vertical = 2.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Text(type.label, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                            entries.forEach { entry ->
                                Row(
                                    Modifier.fillMaxWidth().clickable {
                                        if (entry.isDish) onOpenDish(entry.id) else onOpenFood(entry.id)
                                    },
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    SmallFoodCategoryBadge(entry.category)
                                    Text(entry.name, Modifier.weight(1f), maxLines = 2, overflow = TextOverflow.Ellipsis)
                                    Text("${formatDecimal(entry.grams)} g", fontWeight = FontWeight.SemiBold)
                                }
                            }
                        }
                        if (index < MealType.entries.lastIndex) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    }
                }
            }
        }
    }

    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Tu menú de esta semana", style = MaterialTheme.typography.titleLarge)

        if (expandedSection == summaryKey) SummaryCard()

        val collapsedKeys = buildList {
            if (expandedSection != summaryKey) add(summaryKey)
            WeekDay.entries.filter { it.name != expandedSection }.forEach { add(it.name) }
        }
        if (collapsedKeys.isNotEmpty()) {
            Card(
                Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow)
            ) {
                Column(Modifier.fillMaxWidth()) {
                    collapsedKeys.forEachIndexed { index, key ->
                        if (index > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                        if (key == summaryKey) {
                            Row(
                                Modifier.fillMaxWidth().clickable { expandedSection = summaryKey }.padding(16.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                    Text("Valoración nutricional", style = MaterialTheme.typography.titleMedium)
                                    Text(
                                        "Calorías y macronutrientes de toda la semana",
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                Icon(Icons.Default.KeyboardArrowDown, contentDescription = "Expandir")
                            }
                        } else {
                            val day = WeekDay.valueOf(key)
                            val dayMeals = meals.filter { day in it.days }.associateBy { it.type }
                            val assessment = recommendation?.let {
                                MealPlanEvaluator.assessDay(day, meals, foodsById, dishesById, it)
                            }
                            Row(
                                Modifier.fillMaxWidth().clickable { expandedSection = day.name }.padding(16.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                    Text(day.label, style = MaterialTheme.typography.titleMedium)
                                    val count = dayMeals.values.count { it.items.isNotEmpty() || it.dishes.isNotEmpty() }
                                    val calories = assessment?.actual?.calories
                                    Text(
                                        buildString {
                                            append("$count comidas")
                                            if (calories != null) append(" · ${formatDecimal(calories)} kcal")
                                        },
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                Icon(Icons.Default.KeyboardArrowDown, contentDescription = "Expandir")
                            }
                        }
                    }
                }
            }
        }

        if (expandedSection != summaryKey && expandedSection.isNotBlank()) {
            runCatching { WeekDay.valueOf(expandedSection) }.getOrNull()?.let { DayCard(it) }
        }
    }
}
'''
t = t[:start] + weekly + t[end:]

# Weekly assessment wording.
assessment_anchor = '''private fun todayAssessmentText(assessment: PlanNutritionAssessment?): String {
'''
assert assessment_anchor in t
insert_pos = t.index('\n@Composable\nprivate fun ShoppingListScreen(', t.index(assessment_anchor))
weekly_text = r'''

private fun weeklyAssessmentText(assessment: PlanNutritionAssessment?): String {
    if (assessment == null) return "Añade una medición para poder valorar este menú."
    if (!assessment.actual.isComplete) return "Faltan datos nutricionales para valorar el menú completo."
    val names = listOf("calorías", "proteína", "hidratos", "grasa")
    val outside = assessment.evaluations.withIndex().filter { it.value.fit == TargetFit.OUTSIDE }
    val below = outside.filter { it.value.difference < 0.0 }.map { names[it.index] }
    val above = outside.filter { it.value.difference > 0.0 }.map { names[it.index] }
    if (below.isEmpty() && above.isEmpty()) return "El menú semanal está bien ajustado a tus objetivos."
    return buildList {
        if (below.isNotEmpty()) add("Por debajo del objetivo semanal: ${below.joinToString()}.")
        if (above.isNotEmpty()) add("Por encima del objetivo semanal: ${above.joinToString()}.")
    }.joinToString(" ")
}
'''
t = t[:insert_pos] + weekly_text + t[insert_pos:]

# --- Standard exposed dropdown fields for dish suitability, matching unit selector. ---
ms_start = t.index('@Composable\nprivate fun MultiSelectDishField(')
ms_end = t.index('\n@Composable\nprivate fun AddToMealDialog(', ms_start)
multiselect = r'''@Composable
private fun MultiSelectDishField(
    label: String,
    selectedLabels: List<String>,
    options: List<Pair<String, String>>,
    selectedKeys: Set<String>,
    onSelectionChange: (Set<String>) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    val displayValue = when {
        selectedLabels.size == options.size -> "Todos"
        selectedLabels.isEmpty() -> "Ninguno"
        else -> selectedLabels.joinToString()
    }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = displayValue,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth(),
            maxLines = 2
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { (key, optionLabel) ->
                DropdownMenuItem(
                    leadingIcon = { Checkbox(checked = key in selectedKeys, onCheckedChange = null) },
                    text = { Text(optionLabel) },
                    onClick = {
                        onSelectionChange(if (key in selectedKeys) selectedKeys - key else selectedKeys + key)
                    }
                )
            }
        }
    }
}
'''
t = t[:ms_start] + multiselect + t[ms_end:]

app.write_text(t)

# --- Evaluator: aggregate the whole week so UI uses the same tolerance policy. ---
e = evaluator.read_text()
anchor = '''    fun weeklyFoodAmounts(
'''
assert anchor in e
week_method = '''    fun assessWeek(
        meals: List<PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation
    ): PlanNutritionAssessment {
        val actual = WeekDay.entries.fold(NutritionTotals()) { total, day ->
            val dayMeals = meals.filter { day in it.days }
            total + dayMeals.fold(NutritionTotals()) { dayTotal, meal ->
                dayTotal + meal.nutrition(foodsById, dishesById, day)
            }
        }
        return assess(actual, dailyTarget(recommendation).scaled(WeekDay.entries.size.toDouble()))
    }

'''
e = e.replace(anchor, week_method + anchor, 1)
evaluator.write_text(e)

print('Final UI feedback patch applied')
