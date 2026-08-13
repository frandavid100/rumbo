from pathlib import Path

app_path = Path("app/src/main/java/es/david/rumbo/ui/App.kt")
build_path = Path("app/build.gradle")
text = app_path.read_text()

import_anchor = "import androidx.compose.material3.AlertDialog\n"
imports = """import androidx.compose.material3.AppBarWithSearch
import androidx.compose.material3.ExpandedFullScreenSearchBar
import androidx.compose.material3.SearchBarScrollBehavior
import androidx.compose.material3.SearchBarState
import androidx.compose.material3.SearchBarValue
import androidx.compose.material3.rememberSearchBarState
"""
if "import androidx.compose.material3.AppBarWithSearch\n" not in text:
    if import_anchor not in text:
        raise SystemExit("No se encontró el ancla de imports")
    text = text.replace(import_anchor, import_anchor + imports, 1)

home_start_anchor = "    var searchExpanded by rememberSaveable { mutableStateOf(false) }"
home_start = text.index(home_start_anchor, text.index("private fun HomeScreen("))
home_end_marker = "    ) { innerPadding ->\n"
home_end = text.index(home_end_marker, home_start) + len(home_end_marker)

home_replacement = '''    var searchQuery by rememberSaveable { mutableStateOf("") }
    var searchFilter by rememberSaveable { mutableStateOf(CatalogFilter.ALL) }
    var searchMessage by remember { mutableStateOf<String?>(null) }
    val searchBarState = rememberSearchBarState()
    val searchScrollBehavior = SearchBarDefaults.enterAlwaysSearchBarScrollBehavior()
    val searchScope = rememberCoroutineScope()
    val openSearch = {
        searchScrollBehavior.scrollOffset = 0f
        searchScrollBehavior.contentOffset = 0f
        searchScope.launch { searchBarState.animateToExpanded() }
        Unit
    }
    val closeSearch = {
        searchQuery = ""
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
                query = searchQuery,
                onQueryChange = { searchQuery = it },
                filter = searchFilter,
                onFilterChange = { searchFilter = it },
                scanMessage = searchMessage,
                onScanMessageChange = { searchMessage = it },
                state = searchBarState,
                scrollBehavior = searchScrollBehavior,
                onOpenSearch = openSearch,
                onCloseSearch = closeSearch,
                onOpenFood = onOpenFood,
                onOpenDish = onOpenDish,
                trailingContent = {
                    ProfileSwitcher(
                        profiles = data.profiles.map { it.profile },
                        activeProfile = data.profile,
                        onSelect = onSwitchProfile,
                        onManage = onManageProfiles,
                        onSettings = onOpenSettings,
                        avatarSize = 36
                    )
                }
            )
        }
    ) { innerPadding ->
'''
text = text[:home_start] + home_replacement + text[home_end:]

search_start = text.index("@Composable\nprivate fun HomeCatalogSearch(")
search_end = text.index("\n@Composable\nprivate fun FoodDishCatalogScreen(", search_start)

search_replacement = r'''@Composable
private fun HomeCatalogSearch(
    foods: List<Food>, dishes: List<Dish>, repertoireFoodIds: Set<Long>,
    query: String, onQueryChange: (String) -> Unit,
    filter: CatalogFilter, onFilterChange: (CatalogFilter) -> Unit,
    scanMessage: String?, onScanMessageChange: (String?) -> Unit,
    state: SearchBarState,
    scrollBehavior: SearchBarScrollBehavior,
    onOpenSearch: () -> Unit,
    onCloseSearch: () -> Unit,
    onOpenFood: (Long) -> Unit, onOpenDish: (Long) -> Unit,
    trailingContent: @Composable () -> Unit
) {
    val context = LocalContext.current
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    val expanded = state.targetValue == SearchBarValue.Expanded
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

    val closeSearch = {
        focusManager.clearFocus(force = true)
        keyboard?.hide()
        onCloseSearch()
    }

    LaunchedEffect(state.targetValue) {
        if (state.targetValue == SearchBarValue.Collapsed) {
            focusManager.clearFocus(force = true)
            keyboard?.hide()
            onQueryChange("")
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
                closeSearch()
                onOpenFood(food.id)
            } ?: run {
                onQueryChange(value)
                onScanMessageChange("No encuentro este producto en tus supermercados.")
                onOpenSearch()
            }
        }
        Unit
    }

    val collapsedInput: @Composable () -> Unit = {
        SearchBarDefaults.InputField(
            query = "",
            onQueryChange = { value ->
                onQueryChange(value)
                onOpenSearch()
            },
            onSearch = {},
            expanded = expanded,
            onExpandedChange = { shouldExpand ->
                if (shouldExpand) onOpenSearch() else closeSearch()
            },
            placeholder = { Text("Buscar alimentos y platos") },
            leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
            trailingIcon = {
                IconButton(onClick = scan) {
                    Icon(Icons.Default.QrCodeScanner, "Escanear código de barras")
                }
            }
        )
    }

    val expandedInput: @Composable () -> Unit = {
        SearchBarDefaults.InputField(
            query = query,
            onQueryChange = onQueryChange,
            onSearch = {},
            expanded = expanded,
            onExpandedChange = { shouldExpand ->
                if (shouldExpand) onOpenSearch() else closeSearch()
            },
            modifier = with(scrollBehavior) { Modifier.searchBarScrollBehavior() },
            placeholder = { Text("Buscar alimentos y platos") },
            leadingIcon = {
                IconButton(onClick = closeSearch) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, "Cerrar búsqueda")
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
        inputField = collapsedInput,
        scrollBehavior = scrollBehavior,
        actions = { trailingContent() }
    )

    ExpandedFullScreenSearchBar(
        state = state,
        inputField = expandedInput
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
                onOpenFood = { id -> closeSearch(); onOpenFood(id) },
                onOpenDish = { id -> closeSearch(); onOpenDish(id) },
                onAddFood = {},
                onAddDish = {},
                modifier = Modifier.weight(1f).nestedScroll(scrollBehavior.nestedScrollConnection)
            )
        }
    }

    BackHandler(enabled = expanded) { closeSearch() }
}
'''
text = text[:search_start] + search_replacement + text[search_end:]
app_path.write_text(text)

build = build_path.read_text()
old_dep = '    implementation "androidx.compose.material3:material3"\n'
new_dep = '    implementation "androidx.compose.material3:material3:1.5.0-alpha25"\n'
if old_dep not in build and new_dep not in build:
    raise SystemExit("No se encontró la dependencia Material 3")
build = build.replace(old_dep, new_dep, 1)
build_path.write_text(build)

Path(__file__).unlink()
print("Corrección Material 3 aplicada")
