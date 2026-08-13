from pathlib import Path

app_path = Path("app/src/main/java/es/david/rumbo/ui/App.kt")
module_path = Path("app/build.gradle")
root_path = Path("build.gradle")
wrapper_path = Path("gradle/wrapper/gradle-wrapper.properties")
props_path = Path("gradle.properties")

text = app_path.read_text()

# Imports for the new Material 3 search APIs and shopping-list destination.
anchor = "import androidx.compose.material.icons.filled.Search\n"
if "import androidx.compose.material.icons.filled.ShoppingCart\n" not in text:
    text = text.replace(anchor, anchor + "import androidx.compose.material.icons.filled.ShoppingCart\n", 1)

anchor = "import androidx.compose.material3.AlertDialog\n"
imports = """import androidx.compose.material3.AppBarWithSearch
import androidx.compose.material3.ExpandedFullScreenSearchBar
import androidx.compose.material3.SearchBarScrollBehavior
import androidx.compose.material3.SearchBarState
import androidx.compose.material3.SearchBarValue
import androidx.compose.material3.rememberSearchBarState
"""
if "import androidx.compose.material3.AppBarWithSearch\n" not in text:
    text = text.replace(anchor, anchor + imports, 1)

anchor = "import androidx.compose.foundation.text.KeyboardOptions\n"
imports = """import androidx.compose.foundation.text.input.TextFieldState
import androidx.compose.foundation.text.input.rememberTextFieldState
import androidx.compose.foundation.text.input.setTextAndPlaceCursorAtEnd
"""
if "import androidx.compose.foundation.text.input.TextFieldState\n" not in text:
    text = text.replace(anchor, anchor + imports, 1)

# Destination and state for shopping lists.
old = '    SETTINGS("Opciones", Icons.Default.Person, false),\n'
new = '    SHOPPING_LIST("Lista de la compra", Icons.Default.ShoppingCart, false),\n' + old
if "SHOPPING_LIST(" not in text:
    text = text.replace(old, new, 1)

old = "    var plannerWeekName by rememberSaveable { mutableStateOf(PlanWeek.CURRENT.name) }\n"
new = old + "    var shoppingWeekName by rememberSaveable { mutableStateOf(PlanWeek.CURRENT.name) }\n"
if "var shoppingWeekName" not in text:
    text = text.replace(old, new, 1)

# Add the shopping-list screen before settings in the main router.
router_anchor = "                screen == Screen.SETTINGS -> SettingsScreen(\n"
router_block = '''                screen == Screen.SHOPPING_LIST -> ShoppingListScreen(
                    data = data,
                    week = PlanWeek.valueOf(shoppingWeekName),
                    onWeekChange = { shoppingWeekName = it.name },
                    onBack = { screenName = Screen.HOME.name }
                )
'''
if "screen == Screen.SHOPPING_LIST -> ShoppingListScreen" not in text:
    text = text.replace(router_anchor, router_block + router_anchor, 1)

# Home callback from avatar menu.
old = "                    onManageProfiles = { screenName = Screen.PROFILE.name },\n                    onOpenSettings = { screenName = Screen.SETTINGS.name },\n"
new = "                    onManageProfiles = { screenName = Screen.PROFILE.name },\n                    onOpenShoppingList = { shoppingWeekName = PlanWeek.CURRENT.name; screenName = Screen.SHOPPING_LIST.name },\n                    onOpenSettings = { screenName = Screen.SETTINGS.name },\n"
if "onOpenShoppingList = { shoppingWeekName" not in text:
    text = text.replace(old, new, 1)

old = "    onManageProfiles: () -> Unit,\n    onOpenSettings: () -> Unit,\n"
new = "    onManageProfiles: () -> Unit,\n    onOpenShoppingList: () -> Unit,\n    onOpenSettings: () -> Unit,\n"
# First occurrence is HomeScreen signature.
if "private fun HomeScreen(" in text and "onOpenShoppingList: () -> Unit" not in text[text.index("private fun HomeScreen("):text.index("private fun HomeScreen(")+800]:
    start = text.index("private fun HomeScreen(")
    tail = text[start:]
    tail = tail.replace(old, new, 1)
    text = text[:start] + tail

# Replace HomeScreen's old stable search setup with AppBarWithSearch architecture.
home_start_anchor = "    var searchExpanded by rememberSaveable { mutableStateOf(false) }"
home_start = text.index(home_start_anchor, text.index("private fun HomeScreen("))
home_end_marker = "    ) { innerPadding ->\n"
home_end = text.index(home_end_marker, home_start) + len(home_end_marker)

home_replacement = '''    val searchTextState = rememberTextFieldState()
    var searchFilter by rememberSaveable { mutableStateOf(CatalogFilter.ALL) }
    var searchMessage by remember { mutableStateOf<String?>(null) }
    val searchBarState = rememberSearchBarState()
    val searchScrollBehavior = SearchBarDefaults.enterAlwaysSearchBarScrollBehavior()
    val searchScope = rememberCoroutineScope()
    val closeSearch = {
        searchTextState.setTextAndPlaceCursorAtEnd("")
        searchMessage = null
        searchScrollBehavior.scrollOffset = 0f
        searchScrollBehavior.contentOffset = 0f
        searchScope.launch { searchBarState.animateToCollapsed() }
        Unit
    }

    Scaffold(
        modifier = Modifier.fillMaxSize().nestedScroll(searchScrollBehavior.nestedScrollConnection),
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            HomeCatalogSearch(
                foods = data.foods,
                dishes = data.dishes,
                repertoireFoodIds = data.activeProfileData?.repertoireFoodIds.orEmpty(),
                textFieldState = searchTextState,
                filter = searchFilter,
                onFilterChange = { searchFilter = it },
                scanMessage = searchMessage,
                onScanMessageChange = { searchMessage = it },
                state = searchBarState,
                scrollBehavior = searchScrollBehavior,
                onCloseSearch = closeSearch,
                onOpenFood = { id -> closeSearch(); onOpenFood(id) },
                onOpenDish = { id -> closeSearch(); onOpenDish(id) },
                trailingContent = {
                    ProfileSwitcher(
                        profiles = data.profiles.map { it.profile },
                        activeProfile = data.profile,
                        onSelect = onSwitchProfile,
                        onManage = onManageProfiles,
                        onShoppingList = onOpenShoppingList,
                        onSettings = onOpenSettings,
                        avatarSize = 36
                    )
                }
            )
        }
    ) { innerPadding ->
'''
text = text[:home_start] + home_replacement + text[home_end:]

# Remove the shopping list from Home.
shopping_item = '''            item {
                HomeShoppingSection(
                    meals = meals,
                    foodsById = foodsById,
                    dishesById = dishesById,
                    profileId = profile?.id,
                    onOpenFoods = onOpenFoods
                )
            }
'''
text = text.replace(shopping_item, "", 1)

# Replace HomeCatalogSearch with the new state-based Material 3 APIs.
search_start = text.index("@Composable\nprivate fun HomeCatalogSearch(")
search_end = text.index("\n@Composable\nprivate fun FoodDishCatalogScreen(", search_start)
search_replacement = r'''@Composable
private fun HomeCatalogSearch(
    foods: List<Food>, dishes: List<Dish>, repertoireFoodIds: Set<Long>,
    textFieldState: TextFieldState,
    filter: CatalogFilter, onFilterChange: (CatalogFilter) -> Unit,
    scanMessage: String?, onScanMessageChange: (String?) -> Unit,
    state: SearchBarState,
    scrollBehavior: SearchBarScrollBehavior,
    onCloseSearch: () -> Unit,
    onOpenFood: (Long) -> Unit, onOpenDish: (Long) -> Unit,
    trailingContent: @Composable () -> Unit
) {
    val context = LocalContext.current
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    val scope = rememberCoroutineScope()
    val query = textFieldState.text.toString()
    val normalized = normalizeSearch(query)
    val foodsById = remember(foods) { foods.associateBy { it.id } }
    val entries = remember(foods, dishes, normalized, filter, repertoireFoodIds) {
        buildList {
            if (filter != CatalogFilter.DISHES) foods.forEach { food ->
                val searchText = normalizeSearch(listOfNotNull(food.name, food.brand, food.barcode).joinToString(" "))
                if (normalized.isBlank() && food.id in repertoireFoodIds || normalized.isNotBlank() && searchText.contains(normalized)) {
                    add(CatalogEntry(food.id, food.name, false))
                }
            }
            if (filter != CatalogFilter.FOODS) dishes.forEach { dish ->
                val favorite = dish.ingredients.any { it.foodId in repertoireFoodIds }
                if (normalized.isBlank() && favorite || normalized.isNotBlank() && normalizeSearch(dish.name).contains(normalized)) {
                    add(CatalogEntry(dish.id, dish.name, true))
                }
            }
        }.sortedBy { it.name.lowercase() }
    }

    val close = {
        focusManager.clearFocus(force = true)
        keyboard?.hide()
        onCloseSearch()
    }

    LaunchedEffect(state.targetValue) {
        if (state.targetValue == SearchBarValue.Collapsed) {
            focusManager.clearFocus(force = true)
            keyboard?.hide()
            if (textFieldState.text.isNotEmpty()) textFieldState.setTextAndPlaceCursorAtEnd("")
            onScanMessageChange(null)
            scrollBehavior.scrollOffset = 0f
            scrollBehavior.contentOffset = 0f
        }
    }

    val scan = {
        onScanMessageChange(null)
        GmsBarcodeScanning.getClient(context).startScan().addOnSuccessListener { barcode ->
            val value = barcode.rawValue.orEmpty()
            foods.firstOrNull { it.barcode == value }?.let { food ->
                close()
                onOpenFood(food.id)
            } ?: run {
                textFieldState.setTextAndPlaceCursorAtEnd(value)
                onScanMessageChange("No encuentro este producto en tus supermercados.")
                scope.launch { state.animateToExpanded() }
            }
        }
        Unit
    }

    val inputField: @Composable () -> Unit = {
        SearchBarDefaults.InputField(
            textFieldState = textFieldState,
            searchBarState = state,
            onSearch = {},
            placeholder = { Text("Buscar alimentos y platos") },
            leadingIcon = {
                if (state.targetValue == SearchBarValue.Expanded) {
                    IconButton(onClick = close) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Cerrar búsqueda")
                    }
                } else {
                    Icon(Icons.Default.Search, contentDescription = null)
                }
            },
            trailingIcon = {
                IconButton(onClick = scan) {
                    Icon(Icons.Default.QrCodeScanner, "Escanear código de barras")
                }
            }
        )
    }

    AppBarWithSearch(
        state = state,
        inputField = inputField,
        scrollBehavior = scrollBehavior,
        actions = { trailingContent() }
    )

    ExpandedFullScreenSearchBar(
        state = state,
        inputField = {
            Box(with(scrollBehavior) { Modifier.searchBarScrollBehavior() }) {
                inputField()
            }
        }
    ) {
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
                modifier = Modifier.weight(1f).nestedScroll(scrollBehavior.nestedScrollConnection)
            )
        }
    }

    BackHandler(enabled = state.targetValue == SearchBarValue.Expanded) { close() }
}
'''
text = text[:search_start] + search_replacement + text[search_end:]

# Add shopping-list item to avatar menu, immediately above Options.
profile_start = text.index("@Composable\nprivate fun ProfileSwitcher(")
profile_end = text.index("\n@Composable", profile_start + 20)
profile = text[profile_start:profile_end]
if "onShoppingList: () -> Unit" not in profile:
    profile = profile.replace(
        "    onManage: () -> Unit,\n    onSettings: () -> Unit,\n",
        "    onManage: () -> Unit,\n    onShoppingList: () -> Unit,\n    onSettings: () -> Unit,\n",
        1
    )
    options_anchor = '''            DropdownMenuItem(
                text = { Text("Opciones") },
'''
    shopping_menu = '''            DropdownMenuItem(
                leadingIcon = { Icon(Icons.Default.ShoppingCart, contentDescription = null) },
                text = { Text("Lista de la compra") },
                onClick = {
                    expanded = false
                    onShoppingList()
                }
            )
'''
    profile = profile.replace(options_anchor, shopping_menu + options_anchor, 1)
    text = text[:profile_start] + profile + text[profile_end:]

# Standalone shopping-list screen with current/next week selector.
insert_at = text.index("\n@Composable\nprivate fun HomeShoppingSection(")
shopping_screen = r'''
@Composable
private fun ShoppingListScreen(
    data: AppData,
    week: PlanWeek,
    onWeekChange: (PlanWeek) -> Unit,
    onBack: () -> Unit
) {
    val foodsById = remember(data.foods) { data.foods.associateBy { it.id } }
    val dishesById = remember(data.dishes) { data.dishes.associateBy { it.id } }
    val meals = data.activeProfileData?.plannedMeals.orEmpty().filter { it.planWeek == week }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Lista de la compra") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Volver")
                    }
                }
            )
        }
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(innerPadding),
            contentPadding = PaddingValues(start = 16.dp, top = 12.dp, end = 16.dp, bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            item {
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    listOf(PlanWeek.CURRENT to "Esta semana", PlanWeek.NEXT to "La que viene").forEachIndexed { index, (value, label) ->
                        SegmentedButton(
                            selected = week == value,
                            onClick = { onWeekChange(value) },
                            shape = SegmentedButtonDefaults.itemShape(index, 2)
                        ) { Text(label) }
                    }
                }
            }
            item {
                HomeShoppingSection(
                    meals = meals,
                    foodsById = foodsById,
                    dishesById = dishesById,
                    profileId = data.profile?.id,
                    onOpenFoods = {}
                )
            }
        }
    }
}
'''
text = text[:insert_at] + shopping_screen + text[insert_at:]

app_path.write_text(text)

# Material 3 alpha with AppBarWithSearch enter-always behavior; API 37 toolchain.
module = module_path.read_text()
module = module.replace("    compileSdk = 36", "    compileSdk = 37", 1)
module = module.replace('    implementation "androidx.compose.material3:material3"', '    implementation "androidx.compose.material3:material3:1.5.0-alpha25"', 1)
module_path.write_text(module)

root = root_path.read_text().replace('classpath "com.android.tools.build:gradle:8.13.0"', 'classpath "com.android.tools.build:gradle:9.1.1"', 1)
root_path.write_text(root)

wrapper = wrapper_path.read_text().replace("gradle-8.13-bin.zip", "gradle-9.3.1-bin.zip", 1)
wrapper_path.write_text(wrapper)

props = props_path.read_text()
if "android.builtInKotlin=" not in props:
    props += "android.builtInKotlin=false\n"
if "android.newDsl=" not in props:
    props += "android.newDsl=false\n"
props_path.write_text(props)

print("Búsqueda nueva y lista de la compra aplicadas")
