from pathlib import Path

app_path = Path("app/src/main/java/es/david/rumbo/ui/App.kt")
build_path = Path("app/build.gradle")
text = app_path.read_text()

for line in [
    "import androidx.compose.material3.AppBarWithSearch\n",
    "import androidx.compose.material3.ExpandedFullScreenSearchBar\n",
    "import androidx.compose.material3.SearchBarScrollBehavior\n",
    "import androidx.compose.material3.SearchBarState\n",
    "import androidx.compose.material3.SearchBarValue\n",
    "import androidx.compose.material3.rememberSearchBarState\n",
]:
    text = text.replace(line, "")

home_fn = text.index("private fun HomeScreen(")
home_start = text.index("    var searchQuery by rememberSaveable", home_fn)
home_end_marker = "    ) { innerPadding ->\n"
home_end = text.index(home_end_marker, home_start) + len(home_end_marker)

home_replacement = '''    var searchExpanded by rememberSaveable { mutableStateOf(false) }
    var searchQuery by rememberSaveable { mutableStateOf("") }
    var searchFilter by rememberSaveable { mutableStateOf(CatalogFilter.ALL) }
    var searchMessage by remember { mutableStateOf<String?>(null) }
    val closeSearch = {
        searchQuery = ""
        searchMessage = null
        searchExpanded = false
    }

    if (searchExpanded) {
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
            expanded = true,
            onExpandedChange = { if (!it) closeSearch() },
            onOpenFood = { id -> closeSearch(); onOpenFood(id) },
            onOpenDish = { id -> closeSearch(); onOpenDish(id) }
        )
        return
    }

    val homeTopBarState = rememberTopAppBarState()
    val homeScrollBehavior = TopAppBarDefaults.enterAlwaysScrollBehavior(homeTopBarState)
    Scaffold(
        modifier = Modifier.fillMaxSize().nestedScroll(homeScrollBehavior.nestedScrollConnection),
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            TopAppBar(
                title = {
                    HomeCatalogSearch(
                        foods = data.foods,
                        dishes = data.dishes,
                        repertoireFoodIds = data.activeProfileData?.repertoireFoodIds.orEmpty(),
                        query = "",
                        onQueryChange = {
                            searchQuery = it
                            searchExpanded = true
                        },
                        filter = searchFilter,
                        onFilterChange = { searchFilter = it },
                        scanMessage = searchMessage,
                        onScanMessageChange = { searchMessage = it },
                        expanded = false,
                        onExpandedChange = { if (it) searchExpanded = true },
                        onOpenFood = onOpenFood,
                        onOpenDish = onOpenDish
                    )
                },
                actions = {
                    ProfileSwitcher(
                        profiles = data.profiles.map { it.profile },
                        activeProfile = data.profile,
                        onSelect = onSwitchProfile,
                        onManage = onManageProfiles,
                        onSettings = onOpenSettings,
                        avatarSize = 36
                    )
                },
                scrollBehavior = homeScrollBehavior,
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                    scrolledContainerColor = MaterialTheme.colorScheme.surface
                )
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
    expanded: Boolean, onExpandedChange: (Boolean) -> Unit,
    onOpenFood: (Long) -> Unit, onOpenDish: (Long) -> Unit
) {
    val context = LocalContext.current
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
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
        onQueryChange("")
        onScanMessageChange(null)
        onExpandedChange(false)
    }

    val scan = {
        onScanMessageChange(null)
        GmsBarcodeScanning.getClient(context).startScan().addOnSuccessListener { barcode ->
            val value = barcode.rawValue.orEmpty()
            foods.firstOrNull { it.barcode == value }?.let { food ->
                if (expanded) closeSearch()
                onOpenFood(food.id)
            } ?: run {
                onQueryChange(value)
                onScanMessageChange("No encuentro este producto en tus supermercados.")
                onExpandedChange(true)
            }
        }
        Unit
    }

    val input: @Composable () -> Unit = {
        SearchBarDefaults.InputField(
            query = query,
            onQueryChange = onQueryChange,
            onSearch = {},
            expanded = expanded,
            onExpandedChange = onExpandedChange,
            placeholder = { Text("Buscar alimentos y platos") },
            leadingIcon = {
                if (expanded) {
                    IconButton(onClick = closeSearch) {
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

    if (!expanded) {
        Surface(
            modifier = Modifier.fillMaxWidth().height(56.dp),
            shape = CircleShape,
            color = MaterialTheme.colorScheme.surfaceContainerHigh
        ) { input() }
        return
    }

    BackHandler { closeSearch() }
    val searchTopBarState = rememberTopAppBarState()
    val searchScrollBehavior = TopAppBarDefaults.enterAlwaysScrollBehavior(searchTopBarState)
    Scaffold(
        modifier = Modifier.fillMaxSize().nestedScroll(searchScrollBehavior.nestedScrollConnection),
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            TopAppBar(
                title = {
                    Surface(
                        modifier = Modifier.fillMaxWidth().height(56.dp),
                        shape = CircleShape,
                        color = MaterialTheme.colorScheme.surfaceContainerHigh
                    ) { input() }
                },
                scrollBehavior = searchScrollBehavior,
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                    scrolledContainerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { innerPadding ->
        Column(
            Modifier.fillMaxSize().padding(innerPadding).padding(horizontal = 16.dp)
        ) {
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
                modifier = Modifier.weight(1f)
            )
        }
    }
}
'''
text = text[:search_start] + search_replacement + text[search_end:]
app_path.write_text(text)

build = build_path.read_text()
build = build.replace(
    '    implementation "androidx.compose.material3:material3:1.5.0-alpha25"\n',
    '    implementation "androidx.compose.material3:material3"\n',
    1,
)
build_path.write_text(build)
Path(__file__).unlink()
print("Corrección estable aplicada")
