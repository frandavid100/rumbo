from pathlib import Path

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()

def exact(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, got {n}')
    s = s.replace(old, new, 1)

# LazyRow is the canonical horizontally scrolling container with edge content padding.
exact(
'''import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
''',
'''import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.LazyListState
''',
'lazy row import')

# Root overlay state. It deliberately lives above screen navigation so a food-detail chip
# does not navigate to HOME before showing search.
exact(
'''    var catalogRetailerFilter by rememberSaveable { mutableStateOf<String?>(null) }
    var catalogNutritionalRoleFilter by rememberSaveable { mutableStateOf<String?>(null) }
    var catalogCulinaryRoleFilter by rememberSaveable { mutableStateOf<String?>(null) }
    var catalogSearchRequest by remember { mutableStateOf(0) }
''',
'''    var catalogRetailerFilter by rememberSaveable { mutableStateOf<String?>(null) }
    var catalogNutritionalRoleFilter by rememberSaveable { mutableStateOf<String?>(null) }
    var catalogCulinaryRoleFilter by rememberSaveable { mutableStateOf<String?>(null) }
    var catalogSearchRequest by remember { mutableStateOf(0) }
    var catalogSearchOverlayOpen by remember { mutableStateOf(false) }
    var catalogSearchMealTypeName by rememberSaveable { mutableStateOf<String?>(null) }
    val catalogSearchMealType = catalogSearchMealTypeName?.let {
        runCatching { MealType.valueOf(it) }.getOrNull()
    }
    val catalogOverlayTextState = rememberTextFieldState()
    val catalogOverlaySearchState = rememberSearchBarState()
    val catalogOverlayListState = rememberLazyListState()
    val catalogOverlayScrollBehavior = SearchBarDefaults.enterAlwaysSearchBarScrollBehavior()
    var catalogOverlayMessage by remember { mutableStateOf<String?>(null) }
    var catalogOverlaySuppressKeyboard by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(catalogSearchOverlayOpen) {
        if (catalogSearchOverlayOpen) {
            catalogOverlayTextState.setTextAndPlaceCursorAtEnd("")
            catalogOverlayListState.scrollToItem(0)
            catalogOverlaySearchState.snapTo(1f)
        }
    }
''',
'root search state')

# Chips now open the root overlay directly. FOOD_DETAIL remains the underlying destination.
exact(
'''                            onOpenCatalogFilter = { retailer, nutritionalRole, culinaryRole ->
                                catalogRetailerFilter = retailer
                                catalogNutritionalRoleFilter = nutritionalRole
                                catalogCulinaryRoleFilter = culinaryRole
                                catalogSearchRequest += 1
                                foodReturnScreenName = null
                                screenName = Screen.HOME.name
                            },
''',
'''                            onOpenCatalogFilter = { retailer, nutritionalRole, culinaryRole ->
                                catalogRetailerFilter = retailer
                                catalogNutritionalRoleFilter = nutritionalRole
                                catalogCulinaryRoleFilter = culinaryRole
                                catalogSearchMealTypeName = null
                                catalogSearchOverlayOpen = true
                            },
''',
'chip direct navigation')

# Root overlay is drawn after the normal navigation scaffold, so it is a true full-screen
# search destination while preserving the current detail screen underneath.
exact(
'''    if (addingMeasurement) {
''',
'''    if (catalogSearchOverlayOpen) {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background
        ) {
            HomeCatalogSearch(
                foods = data.foods,
                dishes = data.dishes,
                repertoireFoodIds = data.activeProfileData?.repertoireFoodIds.orEmpty(),
                planningRules = data.activeProfileData?.planningRules.orEmpty(),
                foodSuggestions = emptyList(),
                repertoireAssessment = null,
                recommendation = currentRecommendation,
                textFieldState = catalogOverlayTextState,
                retailerFilter = catalogRetailerFilter,
                onRetailerFilterChange = { catalogRetailerFilter = it },
                nutritionalRoleFilter = catalogNutritionalRoleFilter,
                onNutritionalRoleFilterChange = { catalogNutritionalRoleFilter = it },
                culinaryRoleFilter = catalogCulinaryRoleFilter,
                onCulinaryRoleFilterChange = { catalogCulinaryRoleFilter = it },
                mealTypeFilter = catalogSearchMealType,
                onMealTypeFilterChange = { catalogSearchMealTypeName = it?.name },
                scanMessage = catalogOverlayMessage,
                onScanMessageChange = { catalogOverlayMessage = it },
                state = catalogOverlaySearchState,
                listState = catalogOverlayListState,
                suppressRestoredKeyboard = catalogOverlaySuppressKeyboard,
                onRestoredKeyboardSuppressed = { catalogOverlaySuppressKeyboard = false },
                scrollBehavior = catalogOverlayScrollBehavior,
                onCloseSearch = {
                    catalogOverlayTextState.setTextAndPlaceCursorAtEnd("")
                    catalogOverlayMessage = null
                    catalogSearchOverlayOpen = false
                },
                onOpenFood = { foodId ->
                    selectedFoodId?.let { current ->
                        if (screenName == Screen.FOOD_DETAIL.name && current != foodId) {
                            foodNavigationStack = foodNavigationStack + current
                            foodRecommendationReasonStack = foodRecommendationReasonStack +
                                selectedFoodRecommendationReason.orEmpty()
                        }
                    }
                    selectedFoodId = foodId
                    selectedFoodRecommendationReason = null
                    catalogSearchOverlayOpen = false
                    screenName = Screen.FOOD_DETAIL.name
                },
                onOpenDish = { dishId ->
                    selectedDishId = dishId
                    dishReturnScreenName = screenName
                    catalogSearchOverlayOpen = false
                    screenName = Screen.DISH_DETAIL.name
                },
                trailingContent = {}
            )
        }
    }

    if (addingMeasurement) {
''',
'root search overlay')

# True edge padding for the four search filters.
exact(
'''    Row(
        modifier = Modifier.horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        CatalogStringFilterMenu(
            title = "Comercio", selected = retailer, options = retailerOptions,
            label = ::catalogRetailerLabel, onChange = onRetailerChange
        )
        CatalogStringFilterMenu(
            title = "Rol nutricional", selected = nutritionalRole, options = nutritionalRoleOptions,
            label = ::nutritionalRoleLabel, onChange = onNutritionalRoleChange
        )
        CatalogStringFilterMenu(
            title = "Rol culinario", selected = culinaryRole, options = culinaryRoleOptions,
            label = ::culinaryRoleLabel, onChange = onCulinaryRoleChange
        )
        CatalogMealTypeFilterMenu(mealType, onMealTypeChange)
        Spacer(Modifier.width(16.dp))
    }
''',
'''    LazyRow(
        contentPadding = PaddingValues(end = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        item {
            CatalogStringFilterMenu(
                title = "Comercio", selected = retailer, options = retailerOptions,
                label = ::catalogRetailerLabel, onChange = onRetailerChange
            )
        }
        item {
            CatalogStringFilterMenu(
                title = "Rol nutricional", selected = nutritionalRole, options = nutritionalRoleOptions,
                label = ::nutritionalRoleLabel, onChange = onNutritionalRoleChange
            )
        }
        item {
            CatalogStringFilterMenu(
                title = "Rol culinario", selected = culinaryRole, options = culinaryRoleOptions,
                label = ::culinaryRoleLabel, onChange = onCulinaryRoleChange
            )
        }
        item { CatalogMealTypeFilterMenu(mealType, onMealTypeChange) }
    }
''',
'search filters lazy row')

# True edge padding for attribute chips in food detail.
exact(
'''        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            values.forEach { value ->
                FilterChip(
                    selected = false,
                    onClick = { onClick(value) },
                    label = { Text(label(value)) }
                )
            }
            Spacer(Modifier.width(16.dp))
        }
''',
'''        LazyRow(
            contentPadding = PaddingValues(end = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(values, key = { it }) { value ->
                FilterChip(
                    selected = false,
                    onClick = { onClick(value) },
                    label = { Text(label(value)) }
                )
            }
        }
''',
'detail chips lazy row')

# Nutritional-role filter defines an efficiency sort inside each section.
# Efficiency is grams of the corresponding macro per 100 kcal, matching Rumbo's
# recommendation efficiency convention. VEGETABLE/FRUIT are not macro roles and
# therefore keep the ordinary relevance ordering.
exact(
'''private fun culinaryRoleLabel(value: String): String = when (value) {
''',
'''private fun nutritionalRoleEfficiency(food: Food, role: String): Double? {
    val calories = food.calories?.takeIf { it > 0.0 } ?: return null
    val grams = when (role) {
        "PRIMARY_PROTEIN", "COMPLEMENTARY_PROTEIN" -> food.proteinGrams
        "PRIMARY_CARBOHYDRATE", "COMPLEMENTARY_CARBOHYDRATE" -> food.carbohydrateGrams
        "CONCENTRATED_FAT", "COMPLEMENTARY_FAT" -> food.fatGrams
        else -> null
    } ?: return null
    return grams * 100.0 / calories
}

private fun culinaryRoleLabel(value: String): String = when (value) {
''',
'efficiency helper')

exact(
'''            .sortedWith(
                compareBy<CatalogEntry> { it.id !in repertoireFoodIds }
                    .thenBy { if (normalized.isBlank()) 0 else searchMatchRank(it.name, normalized) }
                    .thenByDescending { personalizedScores[it.id] ?: Double.NEGATIVE_INFINITY }
                    .thenBy { it.name.lowercase() }
            ).toList()
''',
'''            .sortedWith(
                compareBy<CatalogEntry> { it.id !in repertoireFoodIds }
                    .thenByDescending { entry ->
                        nutritionalRoleFilter?.let { role ->
                            foodsById[entry.id]?.let { nutritionalRoleEfficiency(it, role) }
                        } ?: Double.NEGATIVE_INFINITY
                    }
                    .thenBy { if (normalized.isBlank()) 0 else searchMatchRank(it.name, normalized) }
                    .thenByDescending { personalizedScores[it.id] ?: Double.NEGATIVE_INFINITY }
                    .thenBy { it.name.lowercase() }
            ).toList()
''',
'efficiency sort')

p.write_text(s)
print('root search overlay, LazyRow edge padding and macro efficiency sort applied')
