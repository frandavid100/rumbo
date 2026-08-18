from pathlib import Path

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()

old = '''    var catalogSearchOverlayOpen by remember { mutableStateOf(false) }
    var catalogSearchMealTypeName by rememberSaveable { mutableStateOf<String?>(null) }
'''
new = '''    var catalogSearchOverlayOpen by remember { mutableStateOf(false) }
    var catalogSearchMealTypeName by rememberSaveable { mutableStateOf<String?>(null) }
    var catalogSearchReturnPending by rememberSaveable { mutableStateOf(false) }
    var catalogSearchOriginScreenName by rememberSaveable { mutableStateOf<String?>(null) }
    var catalogSearchOriginFoodId by rememberSaveable { mutableStateOf<Long?>(null) }
    var catalogSearchSavedQuery by rememberSaveable { mutableStateOf("") }
    var catalogSearchSavedScrollIndex by rememberSaveable { mutableIntStateOf(0) }
    var catalogSearchSavedScrollOffset by rememberSaveable { mutableIntStateOf(0) }
'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new, 1)

old = '''            screen == Screen.FOOD_DETAIL && foodNavigationStack.isNotEmpty() -> {
                selectedFoodId = foodNavigationStack.last()
'''
new = '''            screen == Screen.FOOD_DETAIL && catalogSearchReturnPending -> {
                catalogSearchReturnPending = false
                if (catalogSearchOriginScreenName == Screen.FOOD_DETAIL.name) {
                    selectedFoodId = catalogSearchOriginFoodId
                }
                catalogSearchOverlayOpen = true
                catalogSearchOriginScreenName ?: Screen.HOME.name
            }
            screen == Screen.FOOD_DETAIL && foodNavigationStack.isNotEmpty() -> {
                selectedFoodId = foodNavigationStack.last()
'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new, 1)

old = '''                    onOpenProgressSearch = { nutritionalRole, culinaryRole, mealType ->
                        catalogRetailerFilter = null
                        catalogNutritionalRoleFilter = nutritionalRole
                        catalogCulinaryRoleFilter = culinaryRole
                        catalogSearchMealTypeName = mealType?.name
                        catalogSearchOverlayOpen = true
                    },'''
new = '''                    onOpenProgressSearch = { nutritionalRole, culinaryRole, mealType ->
                        catalogRetailerFilter = null
                        catalogNutritionalRoleFilter = nutritionalRole
                        catalogCulinaryRoleFilter = culinaryRole
                        catalogSearchMealTypeName = mealType?.name
                        catalogSearchOriginScreenName = Screen.HOME.name
                        catalogSearchOriginFoodId = null
                        catalogSearchReturnPending = false
                        catalogSearchSavedQuery = ""
                        catalogSearchSavedScrollIndex = 0
                        catalogSearchSavedScrollOffset = 0
                        catalogSearchOverlayOpen = true
                    },'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new, 1)

old = '''                            onOpenCatalogFilter = { retailer, nutritionalRole, culinaryRole ->
                                catalogRetailerFilter = retailer
                                catalogNutritionalRoleFilter = nutritionalRole
                                catalogCulinaryRoleFilter = culinaryRole
                                catalogSearchMealTypeName = null
                                catalogSearchOverlayOpen = true
                            },'''
new = '''                            onOpenCatalogFilter = { retailer, nutritionalRole, culinaryRole ->
                                catalogRetailerFilter = retailer
                                catalogNutritionalRoleFilter = nutritionalRole
                                catalogCulinaryRoleFilter = culinaryRole
                                catalogSearchMealTypeName = null
                                catalogSearchOriginScreenName = Screen.FOOD_DETAIL.name
                                catalogSearchOriginFoodId = selectedFoodId
                                catalogSearchReturnPending = false
                                catalogSearchSavedQuery = ""
                                catalogSearchSavedScrollIndex = 0
                                catalogSearchSavedScrollOffset = 0
                                catalogSearchOverlayOpen = true
                            },'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new, 1)

old = '''        var catalogOverlayMessage by remember { mutableStateOf<String?>(null) }
        var catalogOverlaySuppressKeyboard by remember { mutableStateOf(false) }
        Surface(
'''
new = '''        var catalogOverlayMessage by remember { mutableStateOf<String?>(null) }
        var catalogOverlaySuppressKeyboard by remember { mutableStateOf(false) }
        LaunchedEffect(Unit) {
            if (catalogSearchSavedQuery.isNotEmpty()) {
                catalogOverlayTextState.setTextAndPlaceCursorAtEnd(catalogSearchSavedQuery)
            }
            if (catalogSearchSavedScrollIndex > 0 || catalogSearchSavedScrollOffset > 0) {
                catalogOverlayListState.scrollToItem(
                    catalogSearchSavedScrollIndex,
                    catalogSearchSavedScrollOffset
                )
            }
        }
        Surface(
'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new, 1)

old = '''                onCloseSearch = {
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
                },'''
new = '''                onCloseSearch = {
                    catalogOverlayTextState.setTextAndPlaceCursorAtEnd("")
                    catalogOverlayMessage = null
                    catalogSearchReturnPending = false
                    catalogSearchSavedQuery = ""
                    catalogSearchSavedScrollIndex = 0
                    catalogSearchSavedScrollOffset = 0
                    catalogSearchOverlayOpen = false
                },
                onOpenFood = { foodId ->
                    catalogSearchSavedQuery = catalogOverlayTextState.text.toString()
                    catalogSearchSavedScrollIndex = catalogOverlayListState.firstVisibleItemIndex
                    catalogSearchSavedScrollOffset = catalogOverlayListState.firstVisibleItemScrollOffset
                    catalogSearchReturnPending = true
                    selectedFoodId = foodId
                    selectedFoodRecommendationReason = null
                    catalogSearchOverlayOpen = false
                    screenName = Screen.FOOD_DETAIL.name
                },'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new, 1)

p.write_text(s)
print('Catalog search detail back navigation now restores overlay state')
