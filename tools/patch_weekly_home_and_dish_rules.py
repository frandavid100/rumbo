from pathlib import Path

app = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
models = Path('app/src/main/java/es/david/rumbo/model/Models.kt')
repo = Path('app/src/main/java/es/david/rumbo/data/AppRepository.kt')
gen = Path('app/src/main/java/es/david/rumbo/logic/WeeklyMenuGenerator.kt')

# ---- Models: hard suitability constraints on dishes ----
t = models.read_text()
old = '''data class Dish(
    val id: Long,
    val name: String,
    val ingredients: List<DishIngredient>,
    val unitName: String? = null,
    val unitPlural: String? = null,
    val unitGender: String = "MASCULINE",
    val unitAmount: Double? = null,
    val wholeUnitsOnly: Boolean = false,
    val unitDivisions: Int = 1
) {'''
new = '''data class Dish(
    val id: Long,
    val name: String,
    val ingredients: List<DishIngredient>,
    val unitName: String? = null,
    val unitPlural: String? = null,
    val unitGender: String = "MASCULINE",
    val unitAmount: Double? = null,
    val wholeUnitsOnly: Boolean = false,
    val unitDivisions: Int = 1,
    val allowedMealTypes: Set<MealType> = MealType.entries.toSet(),
    val allowedDays: Set<WeekDay> = WeekDay.entries.toSet()
) {'''
assert old in t
t = t.replace(old, new, 1)
models.write_text(t)

# ---- Persistence ----
t = repo.read_text()
old = '''                put("wholeUnitsOnly", dish.wholeUnitsOnly)
                put("unitDivisions", dish.unitDivisions)
                put("ingredients", JSONArray().apply {'''
new = '''                put("wholeUnitsOnly", dish.wholeUnitsOnly)
                put("unitDivisions", dish.unitDivisions)
                put("allowedMealTypes", JSONArray(dish.allowedMealTypes.map { it.name }))
                put("allowedDays", JSONArray(dish.allowedDays.map { it.name }))
                put("ingredients", JSONArray().apply {'''
assert old in t
t = t.replace(old, new, 1)
old = '''                    wholeUnitsOnly = item.optBoolean("wholeUnitsOnly", false),
                    unitDivisions = item.optInt("unitDivisions", 1).coerceIn(1, 100),
                    ingredients = buildList {'''
new = '''                    wholeUnitsOnly = item.optBoolean("wholeUnitsOnly", false),
                    unitDivisions = item.optInt("unitDivisions", 1).coerceIn(1, 100),
                    allowedMealTypes = item.optJSONArray("allowedMealTypes")?.let { values ->
                        buildSet {
                            for (valueIndex in 0 until values.length()) {
                                runCatching { MealType.valueOf(values.getString(valueIndex)) }.getOrNull()?.let(::add)
                            }
                        }
                    } ?: MealType.entries.toSet(),
                    allowedDays = item.optJSONArray("allowedDays")?.let { values ->
                        buildSet {
                            for (valueIndex in 0 until values.length()) {
                                runCatching { WeekDay.valueOf(values.getString(valueIndex)) }.getOrNull()?.let(::add)
                            }
                        }
                    } ?: WeekDay.entries.toSet(),
                    ingredients = buildList {'''
assert old in t
t = t.replace(old, new, 1)
repo.write_text(t)

# ---- Generator: constraints are hard, including fixed-slot dish substitution ----
t = gen.read_text()
old = '''            if (ingredientRules.isEmpty()) null else PlanningRule(
                itemKind = PlannedItemKind.DISH,
                itemId = dish.id,
                allowedMealTypes = ingredientRules.flatMapTo(mutableSetOf()) { it.allowedMealTypes },
                frequency = PlanningFrequency.NORMAL,
                preferredGrams = dish.totalWeightGrams().coerceAtLeast(1.0)
            )'''
new = '''            val allowedMealTypes = ingredientRules.flatMapTo(mutableSetOf()) { it.allowedMealTypes }
                .intersect(dish.allowedMealTypes)
            val allowedDays = ingredientRules.flatMapTo(mutableSetOf()) { it.allowedDays }
                .intersect(dish.allowedDays)
            if (ingredientRules.isEmpty() || allowedMealTypes.isEmpty() || allowedDays.isEmpty()) null else PlanningRule(
                itemKind = PlannedItemKind.DISH,
                itemId = dish.id,
                allowedMealTypes = allowedMealTypes,
                allowedDays = allowedDays,
                frequency = PlanningFrequency.NORMAL,
                preferredGrams = dish.totalWeightGrams().coerceAtLeast(1.0)
            )'''
assert old in t
t = t.replace(old, new, 1)
old = '''                val best = dishes.map { dish ->
                    dish to remaining.count { rule ->
                        slot.mealType in rule.allowedMealTypes &&
                            dish.ingredients.any { it.foodId == rule.itemId }
                    }
                }.maxByOrNull { it.second }?.takeIf { it.second >= 2 } ?: break'''
new = '''                val best = dishes.filter { dish ->
                    slot.mealType in dish.allowedMealTypes && slot.day in dish.allowedDays
                }.map { dish ->
                    dish to remaining.count { rule ->
                        slot.mealType in rule.allowedMealTypes && slot.day in rule.allowedDays &&
                            dish.ingredients.any { it.foodId == rule.itemId }
                    }
                }.maxByOrNull { it.second }?.takeIf { it.second >= 2 } ?: break'''
assert old in t
t = t.replace(old, new, 1)
gen.write_text(t)

# ---- UI ----
t = app.read_text()
# imports
for anchor, addition in [
    ('import androidx.compose.foundation.layout.width\n', 'import androidx.compose.foundation.layout.windowInsetsTopHeight\n'),
    ('import androidx.compose.animation.AnimatedContent\n', 'import androidx.compose.animation.AnimatedVisibility\n'),
    ('import androidx.compose.material.icons.filled.Home\n', 'import androidx.compose.material.icons.filled.KeyboardArrowDown\nimport androidx.compose.material.icons.filled.KeyboardArrowUp\n')
]:
    if addition.strip() not in t:
        assert anchor in t
        t = t.replace(anchor, anchor + addition, 1)

# Home callbacks
old = '''    onExplainBody: () -> Unit,
    onOpenPlanner: () -> Unit,
    onOpenMeal: (Long) -> Unit,'''
new = '''    onExplainBody: () -> Unit,
    onOpenNextWeek: () -> Unit,
    onRegenerateWeek: () -> String?,
    onOpenMeal: (Long) -> Unit,'''
assert old in t
t = t.replace(old, new, 1)

# Home topbar + body wrapper: same horizontal inset as cards and status-bar tint.
old = '''    Scaffold(
        modifier = Modifier.fillMaxSize().nestedScroll(searchScrollBehavior.nestedScrollConnection),
        contentWindowInsets = WindowInsets(0, 0, 0, 0),'''
new = '''    Box(Modifier.fillMaxSize()) {
    Scaffold(
        modifier = Modifier.fillMaxSize().nestedScroll(searchScrollBehavior.nestedScrollConnection),
        contentWindowInsets = WindowInsets(0, 0, 0, 0),'''
assert old in t
t = t.replace(old, new, 1)
old = '''        }
    }
}

@Composable
private fun MissingMeasurementCard'''
new = '''        }
    }
    Box(
        Modifier.fillMaxWidth()
            .windowInsetsTopHeight(WindowInsets.statusBars)
            .background(MaterialTheme.colorScheme.surfaceContainer)
    )
    }
}

@Composable
private fun MissingMeasurementCard'''
# this matches first end after HomeScreen because directly before MissingMeasurementCard
assert old in t
t = t.replace(old, new, 1)

# Replace Today's plan with weekly accordion.
old = '''        item {
            TodayPlanSection(
                meals = meals,
                foodsById = foodsById,
                dishesById = dishesById,
                recommendation = recommendation,
                onOpenPlanner = onOpenPlanner,
                onOpenMeal = onOpenMeal,
                onOpenFood = onOpenFood,
                onOpenDish = onOpenDish,
                onAddMissing = onAddMissingMeal,
                onApplyAdjustedMeals = onApplyAdjustedMeals
            )
        }'''
new = '''        item {
            WeeklyHomeMenuSection(
                meals = meals,
                foodsById = foodsById,
                dishesById = dishesById,
                recommendation = recommendation,
                onOpenNextWeek = onOpenNextWeek,
                onRegenerateWeek = onRegenerateWeek,
                onOpenMeal = onOpenMeal,
                onOpenFood = onOpenFood,
                onOpenDish = onOpenDish,
                onApplyAdjustedMeals = onApplyAdjustedMeals
            )
        }'''
assert old in t
t = t.replace(old, new, 1)

# Replace TodayPlanSection function completely with weekly accordion.
start = t.index('@Composable\nprivate fun TodayPlanSection(')
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
    var expandedDay by rememberSaveable { mutableStateOf(today.name) }
    var rebuildSheet by remember { mutableStateOf(false) }
    var optimizationPreview by remember { mutableStateOf<QuantityOptimizationResult?>(null) }
    var message by remember { mutableStateOf<String?>(null) }

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
                Text(
                    "Elige cuánto quieres cambiar.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
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

    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Tu semana", style = MaterialTheme.typography.headlineSmall)
        WeekDay.entries.forEach { day ->
            val dayMeals = meals.filter { day in it.days }.associateBy { it.type }
            val isExpanded = expandedDay == day.name
            val assessment = recommendation?.let {
                MealPlanEvaluator.assessDay(day, meals, foodsById, dishesById, it)
            }
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.fillMaxWidth()) {
                    Row(
                        Modifier.fillMaxWidth().clickable {
                            expandedDay = if (isExpanded) "" else day.name
                        }.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(day.label, style = MaterialTheme.typography.titleLarge)
                            if (!isExpanded) {
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
                        }
                        Icon(
                            if (isExpanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                            contentDescription = if (isExpanded) "Contraer" else "Expandir"
                        )
                    }
                    AnimatedVisibility(visible = isExpanded) {
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
        }
        OutlinedButton(onClick = { rebuildSheet = true }, Modifier.fillMaxWidth()) {
            Text("Rehacer menú semanal")
        }
        FilledTonalButton(onClick = onOpenNextWeek, Modifier.fillMaxWidth()) {
            Text("Ver la semana que viene")
        }
    }
}
'''
t = t[:start] + weekly + t[end:]

# Home router callbacks.
old = '''                    onExplainBody = { screenName = Screen.BODY_EXPLANATION.name },
                    onOpenPlanner = {
                        plannerWeekName = PlanWeek.CURRENT.name
                        screenName = Screen.PLANNER.name
                    },'''
new = '''                    onExplainBody = { screenName = Screen.BODY_EXPLANATION.name },
                    onOpenNextWeek = {
                        plannerWeekName = PlanWeek.NEXT.name
                        screenName = Screen.PLANNER.name
                    },
                    onRegenerateWeek = {
                        if (currentRecommendation == null) {
                            "Necesitas una recomendación nutricional antes de generar el menú."
                        } else {
                            runCatching {
                                WeeklyMenuGenerator.generate(
                                    currentMeals = data.activeProfileData?.plannedMeals.orEmpty().filter { it.planWeek == PlanWeek.CURRENT },
                                    rules = data.activeProfileData?.planningRules.orEmpty(),
                                    history = data.activeProfileData?.menuHistory.orEmpty(),
                                    foodsById = data.foods.associateBy { it.id },
                                    dishesById = data.dishes.associateBy { it.id },
                                    recommendation = currentRecommendation,
                                    mealShares = mealShares
                                )
                            }.fold(
                                onSuccess = { result ->
                                    data = repository.applyGeneratedMenu(result, PlanWeek.CURRENT)
                                    null
                                },
                                onFailure = { it.message ?: "No se pudo generar una semana válida." }
                            )
                        }
                    },'''
assert old in t
t = t.replace(old, new, 1)

# Weekly planner: no selector; it is now the next-week screen.
old = '''        item {
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                listOf(PlanWeek.CURRENT to "Esta semana", PlanWeek.NEXT to "La que viene").forEachIndexed { index, (week, label) ->
                    SegmentedButton(
                        selected = selectedWeek == week,
                        onClick = {
                            selectedWeek = week
                            onWeekChange(week)
                        },
                        shape = SegmentedButtonDefaults.itemShape(index, 2)
                    ) { Text(label) }
                }
            }
        }
'''
assert old in t
t = t.replace(old, '', 1)

# Search bar: same outer margins as cards; scanner only expanded; filter/info joins results scroll.
old = '''            trailingIcon = {
                IconButton(onClick = scan) {
                    Icon(Icons.Default.QrCodeScanner, "Escanear código de barras")
                }
            }
        )'''
new = '''            trailingIcon = {
                if (state.targetValue == SearchBarValue.Expanded) {
                    IconButton(onClick = scan) {
                        Icon(Icons.Default.QrCodeScanner, "Escanear código de barras")
                    }
                }
            }
        )'''
assert old in t
t = t.replace(old, new, 1)
old = '''    AppBarWithSearch(
        state = state,
        inputField = inputField,
        scrollBehavior = scrollBehavior,
        actions = { trailingContent() }
    )'''
new = '''    AppBarWithSearch(
        state = state,
        inputField = inputField,
        scrollBehavior = scrollBehavior,
        actions = { trailingContent() },
        modifier = Modifier.padding(horizontal = 16.dp)
    )'''
assert old in t
t = t.replace(old, new, 1)
old = '''    ) {
        Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
            Spacer(Modifier.height(8.dp))
            CatalogFilterMenu(filter, onFilterChange)
            if (query.isBlank()) {
                Text(
                    "Escribe el nombre de un alimento o plato, escanea su código de barras o elígelo de tu repertorio.",
                    Modifier.padding(vertical = 12.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            scanMessage?.let { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            CatalogEntries(
                entries = entries,
                foods = foods,
                foodsById = foodsById,
                dishes = dishes,
                repertoireFoodIds = repertoireFoodIds,
                mode = if (query.isBlank()) CatalogMode.REPERTOIRE else CatalogMode.SEARCH,
                normalizedQuery = normalized,
                onOpenFood = { id -> close(); onOpenFood(id) },
                onOpenDish = { id -> close(); onOpenDish(id) },
                onAddFood = {},
                onAddDish = {},
                modifier = Modifier.weight(1f)
            )
        }
    }'''
new = '''    ) {
        CatalogEntries(
            entries = entries,
            foods = foods,
            foodsById = foodsById,
            dishes = dishes,
            repertoireFoodIds = repertoireFoodIds,
            mode = if (query.isBlank()) CatalogMode.REPERTOIRE else CatalogMode.SEARCH,
            normalizedQuery = normalized,
            onOpenFood = { id -> close(); onOpenFood(id) },
            onOpenDish = { id -> close(); onOpenDish(id) },
            onAddFood = {},
            onAddDish = {},
            modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
            header = {
                Column(Modifier.fillMaxWidth()) {
                    Spacer(Modifier.height(8.dp))
                    CatalogFilterMenu(filter, onFilterChange)
                    if (query.isBlank()) {
                        Text(
                            "Escribe el nombre de un alimento o plato, escanea su código de barras o elígelo de tu repertorio.",
                            Modifier.padding(vertical = 12.dp),
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    scanMessage?.let { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
            }
        )
    }'''
assert old in t
t = t.replace(old, new, 1)

# CatalogEntries gets a scrolling header.
old = '''    onAddDish: () -> Unit,
    modifier: Modifier = Modifier
) {
    var addMenuExpanded by remember { mutableStateOf(false) }
    LazyColumn(modifier = modifier, contentPadding = PaddingValues(bottom = 32.dp)) {
        items(entries,'''
new = '''    onAddDish: () -> Unit,
    modifier: Modifier = Modifier,
    header: (@Composable () -> Unit)? = null
) {
    var addMenuExpanded by remember { mutableStateOf(false) }
    LazyColumn(modifier = modifier, contentPadding = PaddingValues(bottom = 32.dp)) {
        if (header != null) item { header() }
        items(entries,'''
assert old in t
t = t.replace(old, new, 1)

# Dish suitability card before ingredients.
anchor = '''        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Ingredientes", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)'''
suitability = '''        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Este plato es adecuado para…", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                HorizontalDivider()
                MultiSelectDishField(
                    label = "Comidas",
                    selectedLabels = MealType.entries.filter { it in dish.allowedMealTypes }.map { it.label },
                    options = MealType.entries.map { it.name to it.label },
                    selectedKeys = dish.allowedMealTypes.mapTo(mutableSetOf()) { it.name },
                    onSelectionChange = { keys ->
                        onSaveDish(dish.copy(allowedMealTypes = keys.mapNotNull { key -> runCatching { MealType.valueOf(key) }.getOrNull() }.toSet()))
                    }
                )
                MultiSelectDishField(
                    label = "Días",
                    selectedLabels = WeekDay.entries.filter { it in dish.allowedDays }.map { it.label },
                    options = WeekDay.entries.map { it.name to it.label },
                    selectedKeys = dish.allowedDays.mapTo(mutableSetOf()) { it.name },
                    onSelectionChange = { keys ->
                        onSaveDish(dish.copy(allowedDays = keys.mapNotNull { key -> runCatching { WeekDay.valueOf(key) }.getOrNull() }.toSet()))
                    }
                )
                Text(
                    "Las comidas y días que desmarques quedan excluidos del generador semanal.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

''' + anchor
assert anchor in t
t = t.replace(anchor, suitability, 1)

# Helper before AddToMealDialog.
anchor = '\n@Composable\nprivate fun AddToMealDialog('
helper = r'''
@Composable
private fun MultiSelectDishField(
    label: String,
    selectedLabels: List<String>,
    options: List<Pair<String, String>>,
    selectedKeys: Set<String>,
    onSelectionChange: (Set<String>) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    Box(Modifier.fillMaxWidth()) {
        OutlinedButton(onClick = { expanded = true }, Modifier.fillMaxWidth()) {
            Text(
                if (selectedLabels.size == options.size) "$label: todos" else if (selectedLabels.isEmpty()) "$label: ninguno" else "$label: ${selectedLabels.joinToString()}",
                Modifier.weight(1f),
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
            Icon(Icons.Default.ArrowDropDown, contentDescription = null)
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
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
assert anchor in t
t = t.replace(anchor, '\n' + helper + anchor, 1)

app.write_text(t)
print('Patch applied')
