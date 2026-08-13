from pathlib import Path

path = Path("app/src/main/java/es/david/rumbo/ui/App.kt")
text = path.read_text()

# Standard delete icon for directly editable dish ingredients.
anchor = "import androidx.compose.material.icons.filled.Edit\n"
if "import androidx.compose.material.icons.filled.Delete\n" not in text:
    text = text.replace(anchor, anchor + "import androidx.compose.material.icons.filled.Delete\n", 1)

# The shopping list owns its one and only app bar; suppress the outer Rumbo bar for this destination.
old = "            if (screen != Screen.HOME && screen !in setOf(Screen.ADD, Screen.EDIT_MEASUREMENT)) TopAppBar(\n"
new = "            if (screen != Screen.HOME && screen !in setOf(Screen.ADD, Screen.EDIT_MEASUREMENT, Screen.SHOPPING_LIST)) TopAppBar(\n"
if old not in text:
    raise SystemExit("No encuentro condición de TopAppBar global")
text = text.replace(old, new, 1)

# Expanded search: keep its input row fixed. Also make the input consume the full width so the scanner sits at the trailing edge.
old = '''        SearchBarDefaults.InputField(
            textFieldState = textFieldState,
            searchBarState = state,
            onSearch = {},
'''
new = '''        SearchBarDefaults.InputField(
            textFieldState = textFieldState,
            searchBarState = state,
            onSearch = {},
            modifier = Modifier.fillMaxWidth(),
'''
if old not in text:
    raise SystemExit("No encuentro InputField de búsqueda")
text = text.replace(old, new, 1)

old = '''    ExpandedFullScreenSearchBar(
        state = state,
        inputField = {
            Box(with(scrollBehavior) { Modifier.searchBarScrollBehavior() }) {
                inputField()
            }
        }
    ) {
'''
new = '''    ExpandedFullScreenSearchBar(
        state = state,
        inputField = {
            Box(Modifier.fillMaxWidth()) {
                inputField()
            }
        }
    ) {
'''
if old not in text:
    raise SystemExit("No encuentro ExpandedFullScreenSearchBar")
text = text.replace(old, new, 1)
text = text.replace(
    "                modifier = Modifier.weight(1f).nestedScroll(scrollBehavior.nestedScrollConnection)\n",
    "                modifier = Modifier.weight(1f)\n",
    1
)

# Shopping list: two plain sections, no duplicate title and no cards.
shopping_start = text.index("@Composable\nprivate fun HomeShoppingSection(")
shopping_end = text.index("\n@Composable\nprivate fun HomeShoppingEntry(", shopping_start)
old_block = text[shopping_start:shopping_end]
new_block = r'''@Composable
private fun HomeShoppingSection(
    meals: List<PlannedMeal>,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    profileId: Long?,
    onOpenFoods: () -> Unit
) {
    val amounts = remember(meals, dishesById) {
        MealPlanEvaluator.weeklyFoodAmounts(meals, dishesById)
    }
    val entries = remember(amounts, foodsById) {
        amounts.mapNotNull { (foodId, grams) -> foodsById[foodId]?.let { it to grams } }
            .sortedBy { it.first.name.lowercase() }
    }
    val context = LocalContext.current
    val shoppingPreferences = remember { context.getSharedPreferences("shopping_state", 0) }
    val preferenceKey = "available_foods_${profileId ?: 0L}"
    var availableFoodIds by remember(profileId) {
        mutableStateOf(
            shoppingPreferences.getStringSet(preferenceKey, emptySet())
                .orEmpty()
                .mapNotNull(String::toLongOrNull)
        )
    }
    fun saveAvailableFoods(updated: List<Long>) {
        availableFoodIds = updated
        shoppingPreferences.edit()
            .putStringSet(preferenceKey, updated.map(Long::toString).toSet())
            .apply()
    }
    val neededEntries = entries.filterNot { (food, _) -> food.id in availableFoodIds }
    val notNeededEntries = entries.filter { (food, _) -> food.id in availableFoodIds }

    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Hace falta comprar", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        if (neededEntries.isEmpty()) {
            Text(
                if (entries.isEmpty()) "El plan todavía no contiene alimentos." else "No falta ningún alimento.",
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        } else {
            neededEntries.forEach { (food, grams) ->
                HomeShoppingEntry(
                    food = food,
                    grams = grams,
                    checked = false,
                    onCheckedChange = { available ->
                        if (available) saveAvailableFoods(availableFoodIds + food.id)
                    }
                )
            }
        }

        HorizontalDivider(Modifier.padding(vertical = 8.dp))
        Text("No hace falta comprar", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        if (notNeededEntries.isEmpty()) {
            Text("Todavía no has marcado ningún alimento.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            notNeededEntries.forEach { (food, grams) ->
                HomeShoppingEntry(
                    food = food,
                    grams = grams,
                    checked = true,
                    onCheckedChange = { available ->
                        if (!available) saveAvailableFoods(availableFoodIds - food.id)
                    }
                )
            }
        }
    }
}
'''
text = text[:shopping_start] + new_block + text[shopping_end:]

# Weekly menu tabs: same segmented control as shopping list.
old = '''        item {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                PlanWeek.entries.forEach { week ->
                    FilterChip(
                        selected = selectedWeek == week,
                        onClick = {
                            selectedWeek = week
                            onWeekChange(week)
                        },
                        label = { Text(week.label) },
                        modifier = Modifier.weight(1f)
                    )
                }
            }
        }
'''
new = '''        item {
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
if old not in text:
    raise SystemExit("No encuentro selector semanal antiguo")
text = text.replace(old, new, 1)

# Dish detail: remove now-obsolete weekly usage computations.
usage_start = text.index("    val menuUsages = remember(dish.id, plannedMeals) {", text.index("private fun DishDetailScreen("))
usage_end = text.index("\n\n    if (confirmDelete)", usage_start)
text = text[:usage_start] + text[usage_end:]

# State for directly editing ingredient grams and adding ingredients.
dish_state_anchor = "    var unitError by remember { mutableStateOf<String?>(null) }\n"
addition = '''    var ingredientAmounts by remember(dish.id, dish.ingredients) {
        mutableStateOf(dish.ingredients.associate { it.foodId to formatDecimal(it.grams) })
    }
    var addingIngredient by remember { mutableStateOf(false) }
    var ingredientError by remember { mutableStateOf<String?>(null) }
'''
pos = text.index(dish_state_anchor, text.index("private fun DishDetailScreen("))
text = text[:pos] + text[pos:].replace(dish_state_anchor, dish_state_anchor + addition, 1)

# Add ingredient bottom sheet before main DishDetail column.
anchor = '''    if (creatingUnit) {
        NewFoodUnitDialog(
'''
start = text.index(anchor, text.index("private fun DishDetailScreen("))
# Find the end of creatingUnit block by using the following Column marker.
column_marker = '''

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
'''
end = text.index(column_marker, start)
addition = r'''

    if (addingIngredient) {
        ModalBottomSheet(onDismissRequest = { addingIngredient = false }) {
            Column(
                Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text("Añadir ingrediente", style = MaterialTheme.typography.headlineSmall)
                val availableFoods = foods.filter { candidate -> dish.ingredients.none { it.foodId == candidate.id } }
                if (availableFoods.isEmpty()) {
                    Text("No quedan alimentos del catálogo por añadir.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    LazyColumn(Modifier.fillMaxWidth().heightIn(max = 420.dp)) {
                        items(availableFoods, key = { it.id }) { food ->
                            Row(
                                Modifier.fillMaxWidth().clickable {
                                    val updated = dish.ingredients + DishIngredient(food.id, 100.0)
                                    ingredientAmounts = ingredientAmounts + (food.id to "100")
                                    onSaveDish(dish.copy(ingredients = updated))
                                    addingIngredient = false
                                }.padding(vertical = 12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(10.dp)
                            ) {
                                SmallFoodCategoryBadge(food.category)
                                Text(food.name, Modifier.weight(1f), maxLines = 2, overflow = TextOverflow.Ellipsis)
                                Icon(Icons.Default.Add, contentDescription = null)
                            }
                            HorizontalDivider()
                        }
                    }
                }
                TextButton(onClick = { addingIngredient = false }, Modifier.fillMaxWidth()) { Text("Cancelar") }
                Spacer(Modifier.height(16.dp))
            }
        }
    }
'''
text = text[:end] + addition + text[end:]

# Replace ingredient display card with direct editing controls.
ing_start = text.index('''        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Ingredientes"''', text.index("private fun DishDetailScreen("))
ing_end = text.index('''

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("En el menú de esta semana"''', ing_start)
new_ing = r'''        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Ingredientes", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                HorizontalDivider()
                dish.ingredients.forEachIndexed { index, ingredient ->
                    val food = foodsById[ingredient.foodId]
                    Row(
                        Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        if (food != null) {
                            SmallFoodCategoryBadge(food.category)
                            Text(
                                food.name,
                                Modifier.weight(1f).clickable { onOpenFood(food.id) },
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis
                            )
                        } else {
                            Spacer(Modifier.size(24.dp))
                            Text("Alimento eliminado", Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        OutlinedTextField(
                            value = ingredientAmounts[ingredient.foodId] ?: formatDecimal(ingredient.grams),
                            onValueChange = { raw ->
                                val filtered = raw.filter { it.isDigit() || it == ',' || it == '.' }.take(8)
                                ingredientAmounts = ingredientAmounts + (ingredient.foodId to filtered)
                                val grams = parseDecimal(filtered)
                                if (grams != null && grams in 0.1..5000.0) {
                                    ingredientError = null
                                    onSaveDish(dish.copy(ingredients = dish.ingredients.map {
                                        if (it.foodId == ingredient.foodId) it.copy(grams = grams) else it
                                    }))
                                } else if (filtered.isNotBlank()) {
                                    ingredientError = "Los gramos deben estar entre 0,1 y 5.000."
                                }
                            },
                            modifier = Modifier.width(104.dp),
                            suffix = { Text("g") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            singleLine = true
                        )
                        IconButton(
                            onClick = {
                                if (dish.ingredients.size > 1) {
                                    ingredientAmounts = ingredientAmounts - ingredient.foodId
                                    onSaveDish(dish.copy(ingredients = dish.ingredients.filterNot { it.foodId == ingredient.foodId }))
                                } else {
                                    ingredientError = "Un plato debe tener al menos un ingrediente."
                                }
                            }
                        ) {
                            Icon(Icons.Default.Delete, "Quitar ingrediente")
                        }
                    }
                    if (index < dish.ingredients.lastIndex) HorizontalDivider()
                }
                ingredientError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                OutlinedButton(onClick = { addingIngredient = true }, Modifier.fillMaxWidth()) {
                    Icon(Icons.Default.Add, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Añadir ingrediente")
                }
            }
        }
'''
text = text[:ing_start] + new_ing + text[ing_end:]

# Remove both weekly-menu cards from dish detail entirely.
first_week = text.index('''        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("En el menú de esta semana"''', text.index("private fun DishDetailScreen("))
# Both cards are the last content before the closing of DishDetailScreen.
dish_end_marker = "\n\n    }\n}\n\n@Composable\nprivate fun AddToMealDialog("
dish_end = text.index(dish_end_marker, first_week)
text = text[:first_week] + text[dish_end:]

path.write_text(text)
print("Ajustes de interfaz aplicados")
