from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)

root = Path('.')
app_path = root / 'app/src/main/java/es/david/rumbo/ui/App.kt'
gradle_path = root / 'app/build.gradle'
app = app_path.read_text()
gradle = gradle_path.read_text()

gradle = replace_once(gradle, 'versionCode = 72\n        versionName = "0.72.0"', 'versionCode = 73\n        versionName = "0.73.0"', 'version')

app = replace_once(
    app,
    '    var catalogCulinaryRoleFilter by rememberSaveable { mutableStateOf<String?>(null) }\n',
    '    var catalogCulinaryRoleFilter by rememberSaveable { mutableStateOf<String?>(null) }\n    var catalogSearchRequest by rememberSaveable { mutableStateOf(0) }\n',
    'root search request state'
)

app = replace_once(
    app,
    '''                screen == Screen.HOME -> HomeScreen(\n                    data = data,\n                    mealShares = mealShares,\n''',
    '''                screen == Screen.HOME -> HomeScreen(\n                    data = data,\n                    mealShares = mealShares,\n                    requestedSearchRetailer = catalogRetailerFilter,\n                    requestedSearchNutritionalRole = catalogNutritionalRoleFilter,\n                    requestedSearchCulinaryRole = catalogCulinaryRoleFilter,\n                    searchOpenRequest = catalogSearchRequest,\n                    onSearchRequestConsumed = { catalogSearchRequest = 0 },\n''',
    'home invocation'
)

app = replace_once(
    app,
    '''private fun HomeScreen(\n    data: AppData,\n    mealShares: Map<MealType, Double>,\n''',
    '''private fun HomeScreen(\n    data: AppData,\n    mealShares: Map<MealType, Double>,\n    requestedSearchRetailer: String?,\n    requestedSearchNutritionalRole: String?,\n    requestedSearchCulinaryRole: String?,\n    searchOpenRequest: Int,\n    onSearchRequestConsumed: () -> Unit,\n''',
    'home signature'
)

app = replace_once(
    app,
    '''    val searchBarState = rememberSearchBarState()\n    val searchListState = rememberLazyListState()\n    var suppressRestoredSearchKeyboard by rememberSaveable { mutableStateOf(false) }\n''',
    '''    val searchBarState = rememberSearchBarState()\n    val searchListState = rememberLazyListState()\n    var suppressRestoredSearchKeyboard by rememberSaveable { mutableStateOf(false) }\n    LaunchedEffect(searchOpenRequest) {\n        if (searchOpenRequest > 0) {\n            searchRetailer = requestedSearchRetailer\n            searchNutritionalRole = requestedSearchNutritionalRole\n            searchCulinaryRole = requestedSearchCulinaryRole\n            searchTextState.setTextAndPlaceCursorAtEnd("")\n            searchListState.scrollToItem(0)\n            searchBarState.animateToExpanded()\n            onSearchRequestConsumed()\n        }\n    }\n''',
    'home external search request effect'
)

app = replace_once(
    app,
    '''                            onOpenCatalogFilter = { retailer, nutritionalRole, culinaryRole ->\n                                catalogRetailerFilter = retailer\n                                catalogNutritionalRoleFilter = nutritionalRole\n                                catalogCulinaryRoleFilter = culinaryRole\n                                foodReturnScreenName = null\n                                screenName = Screen.FOODS.name\n                            },\n''',
    '''                            onOpenCatalogFilter = { retailer, nutritionalRole, culinaryRole ->\n                                catalogRetailerFilter = retailer\n                                catalogNutritionalRoleFilter = nutritionalRole\n                                catalogCulinaryRoleFilter = culinaryRole\n                                catalogSearchRequest += 1\n                                foodReturnScreenName = null\n                                screenName = Screen.HOME.name\n                            },\n''',
    'pill navigation'
)

app = replace_once(
    app,
    '''                        Row(\n                            modifier = Modifier.horizontalScroll(rememberScrollState()),\n                            horizontalArrangement = Arrangement.spacedBy(8.dp)\n                        ) {\n                            CatalogCanonicalFilterRow(\n                                retailerFilter, onRetailerFilterChange, retailerOptions,\n                                nutritionalRoleFilter, onNutritionalRoleFilterChange, nutritionalRoleOptions,\n                                culinaryRoleFilter, onCulinaryRoleFilterChange, culinaryRoleOptions\n                            )\n                        }\n''',
    '''                        CatalogCanonicalFilterRow(\n                            retailerFilter, onRetailerFilterChange, retailerOptions,\n                            nutritionalRoleFilter, onNutritionalRoleFilterChange, nutritionalRoleOptions,\n                            culinaryRoleFilter, onCulinaryRoleFilterChange, culinaryRoleOptions\n                        )\n''',
    'nested horizontal scroll'
)

old_strip = '''@Composable\nprivate fun FoodPrimaryNutritionStrip(food: Food) {\n    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n        NutrientIconValue(\n            Icons.Default.LocalFireDepartment, "Calorías", food.calories, "kcal",\n            MaterialTheme.colorScheme.onSurfaceVariant, Modifier.weight(1.25f)\n        )\n        NutrientIconValue(\n            Icons.Default.FitnessCenter, "Proteínas", food.proteinGrams, "g",\n            MaterialTheme.colorScheme.onSurface, Modifier.weight(1f)\n        )\n        NutrientIconValue(\n            Icons.Default.Grain, "Carbohidratos", food.carbohydrateGrams, "g",\n            MaterialTheme.colorScheme.onSurface, Modifier.weight(1f)\n        )\n        NutrientIconValue(\n            Icons.Default.Opacity, "Grasas", food.fatGrams, "g",\n            MaterialTheme.colorScheme.onSurface, Modifier.weight(1f)\n        )\n    }\n}\n'''
new_strip = '''@Composable\nprivate fun FoodPrimaryNutritionStrip(food: Food) {\n    val nutritionColor = MaterialTheme.colorScheme.onSurfaceVariant\n    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n        NutrientIconValue(\n            Icons.Default.LocalFireDepartment, "Calorías", food.calories, "kcal",\n            nutritionColor, Modifier.weight(1.25f)\n        )\n        NutrientIconValue(\n            Icons.Default.FitnessCenter, "Proteínas", food.proteinGrams, "g",\n            nutritionColor, Modifier.weight(1f)\n        )\n        NutrientIconValue(\n            Icons.Default.Grain, "Carbohidratos", food.carbohydrateGrams, "g",\n            nutritionColor, Modifier.weight(1f)\n        )\n        NutrientIconValue(\n            Icons.Default.Opacity, "Grasas", food.fatGrams, "g",\n            nutritionColor, Modifier.weight(1f)\n        )\n    }\n}\n'''
app = replace_once(app, old_strip, new_strip, 'macro colors')

app_path.write_text(app)
gradle_path.write_text(gradle)
print('Applied search/pill navigation and nutrition color fixes')
