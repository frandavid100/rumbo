from pathlib import Path

app = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
t = app.read_text()

# Search: the whole AppBarWithSearch surface must stay the normal surface color
# in both resting and scrolled states. This avoids transient mismatches with
# the status-bar inset while preserving the search pill's own scrolled color.
old_colors = '''    val appBarColors = SearchBarDefaults.appBarWithSearchColors(
        searchBarColors = SearchBarDefaults.containedColors(state = state),
        appBarContainerColor = MaterialTheme.colorScheme.surface,
        scrolledAppBarContainerColor = MaterialTheme.colorScheme.surfaceContainer,
        scrolledSearchBarContainerColor = MaterialTheme.colorScheme.surfaceContainerHighest
    )'''
new_colors = '''    val appBarColors = SearchBarDefaults.appBarWithSearchColors(
        searchBarColors = SearchBarDefaults.containedColors(state = state),
        appBarContainerColor = MaterialTheme.colorScheme.surface,
        scrolledAppBarContainerColor = MaterialTheme.colorScheme.surface,
        scrolledSearchBarContainerColor = MaterialTheme.colorScheme.surfaceContainerHighest
    )'''
assert old_colors in t, 'No se encontró la configuración de colores de AppBarWithSearch'
t = t.replace(old_colors, new_colors, 1)

old_appbar = '''        colors = appBarColors,
        actions = { trailingContent() },
        modifier = Modifier.fillMaxWidth(),
        contentPadding = PaddingValues(horizontal = 16.dp)
    )'''
new_appbar = '''        colors = appBarColors,
        actions = { trailingContent() },
        modifier = Modifier.fillMaxWidth(),
        contentPadding = PaddingValues(horizontal = 16.dp),
        tonalElevation = 0.dp
    )'''
assert old_appbar in t, 'No se encontró AppBarWithSearch'
t = t.replace(old_appbar, new_appbar, 1)

# Imports for the documented Compose size/visibility animation pattern.
if 'import androidx.compose.animation.expandVertically\n' not in t:
    t = t.replace(
        'import androidx.compose.animation.fadeOut\n',
        'import androidx.compose.animation.fadeOut\nimport androidx.compose.animation.expandVertically\nimport androidx.compose.animation.shrinkVertically\n',
        1
    )

# Replace the weekly home accordion. Every section keeps a stable position in
# one Material Card. Switching sections changes only expandedSection; the old
# body shrinks and the new one expands in place, so no item is reordered.
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

    fun toggleSection(key: String) {
        expandedSection = if (expandedSection == key) "" else key
    }

    @Composable
    fun SectionHeader(
        title: String,
        subtitle: String?,
        expanded: Boolean,
        onClick: () -> Unit
    ) {
        Row(
            Modifier.fillMaxWidth().clickable(onClick = onClick).padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                subtitle?.let {
                    Text(
                        it,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            Icon(
                if (expanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                contentDescription = if (expanded) "Contraer" else "Expandir"
            )
        }
    }

    @Composable
    fun SummarySection(expanded: Boolean) {
        Column(Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "Valoración nutricional",
                subtitle = if (expanded) null else "Calorías y macronutrientes de toda la semana",
                expanded = expanded,
                onClick = { toggleSection(summaryKey) }
            )
            AnimatedVisibility(
                visible = expanded,
                enter = expandVertically(expandFrom = Alignment.Top) + fadeIn(),
                exit = shrinkVertically(shrinkTowards = Alignment.Top) + fadeOut()
            ) {
                Column(
                    Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
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
    }

    @Composable
    fun DaySection(day: WeekDay, expanded: Boolean) {
        val dayMeals = meals.filter { day in it.days }.associateBy { it.type }
        val assessment = recommendation?.let {
            MealPlanEvaluator.assessDay(day, meals, foodsById, dishesById, it)
        }
        val count = dayMeals.values.count { it.items.isNotEmpty() || it.dishes.isNotEmpty() }
        val subtitle = buildString {
            append("$count comidas")
            assessment?.actual?.calories?.let { append(" · ${formatDecimal(it)} kcal") }
        }

        Column(Modifier.fillMaxWidth()) {
            SectionHeader(
                title = day.label,
                subtitle = if (expanded) null else subtitle,
                expanded = expanded,
                onClick = { toggleSection(day.name) }
            )
            AnimatedVisibility(
                visible = expanded,
                enter = expandVertically(expandFrom = Alignment.Top) + fadeIn(),
                exit = shrinkVertically(shrinkTowards = Alignment.Top) + fadeOut()
            ) {
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
                                MenuItemLine(
                                    dish.id, true, dish.name,
                                    meal.resolvedGrams(planned, day),
                                    dish.dominantCategory(foodsById)
                                )
                            }
                        } + meal.items.mapNotNull { planned ->
                            foodsById[planned.foodId]?.let { food ->
                                MenuItemLine(
                                    food.id, false, food.name,
                                    meal.resolvedGrams(planned, day), food.category
                                )
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
                                    Text(
                                        entry.name,
                                        Modifier.weight(1f),
                                        maxLines = 2,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                    Text("${formatDecimal(entry.grams)} g", fontWeight = FontWeight.SemiBold)
                                }
                            }
                        }
                        if (index < MealType.entries.lastIndex) {
                            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                        }
                    }
                }
            }
        }
    }

    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Tu menú de esta semana", style = MaterialTheme.typography.titleLarge)
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.fillMaxWidth()) {
                SummarySection(expandedSection == summaryKey)
                WeekDay.entries.forEach { day ->
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    DaySection(day, expandedSection == day.name)
                }
            }
        }
    }
}
'''
t = t[:start] + weekly + t[end:]

app.write_text(t)
print('Acordeón semanal y superficie de búsqueda actualizados')
