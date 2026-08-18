from pathlib import Path
import re


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"Marker not found in {path}: {old[:120]!r}")
    text = text.replace(old, new, 1)
    p.write_text(text)


def regex_once(path, pattern, replacement, flags=re.S):
    p = Path(path)
    text = p.read_text()
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f"Expected one regex match in {path}, got {count}: {pattern[:100]}")
    p.write_text(updated)

# 1) Preserve canonical multiple roles in the compatibility Food model.
replace_once(
    "app/src/main/java/es/david/rumbo/model/Models.kt",
    '    val unitDivisions: Int = 1,\n    val culinaryType: CulinaryType = CulinaryType.UNKNOWN\n) {',
    '    val unitDivisions: Int = 1,\n    val culinaryType: CulinaryType = CulinaryType.UNKNOWN,\n'
    '    val nutritionalRoles: Set<String> = emptySet(),\n'
    '    val culinaryRoles: Set<String> = emptySet()\n) {'
)
replace_once(
    "app/src/main/java/es/david/rumbo/model/Models.kt",
    '        (!wholeUnitsOnly || unitName?.isNotBlank() == true) &&\n        links.size <= 10 &&',
    '        (!wholeUnitsOnly || unitName?.isNotBlank() == true) &&\n'
    '        nutritionalRoles.size <= 20 && culinaryRoles.size <= 30 &&\n'
    '        nutritionalRoles.all { it.length in 1..80 } &&\n'
    '        culinaryRoles.all { it.length in 1..80 } &&\n'
    '        links.size <= 10 &&'
)

# 2) Carry both role axes through the stable catalog adapter.
replace_once(
    "app/src/main/java/es/david/rumbo/data/catalog/CatalogModels.kt",
    '            source = product.provenance.catalogSource ?: nutrition.source,\n            culinaryType = legacyCulinaryType(classification.culinaryType)\n        ).takeIf',
    '            source = product.provenance.catalogSource ?: nutrition.source,\n'
    '            culinaryType = legacyCulinaryType(classification.culinaryType),\n'
    '            nutritionalRoles = classification.nutritionalRoles,\n'
    '            culinaryRoles = classification.culinaryRoles\n'
    '        ).takeIf'
)

# 3) This test APK uses Carrefour as its sole managed food catalog.
replace_once(
    "app/src/main/java/es/david/rumbo/data/AppRepository.kt",
    'import es.david.rumbo.model.MercadonaFoodCatalog\n',
    'import es.david.rumbo.data.catalog.CatalogBackedFoodCatalog\n'
)
replace_once(
    "app/src/main/java/es/david/rumbo/data/AppRepository.kt",
    'import es.david.rumbo.model.DefaultFoodCatalog\n',
    ''
)
replace_once(
    "app/src/main/java/es/david/rumbo/data/AppRepository.kt",
    '    private val baseFoods: List<Food> by lazy {\n        (DefaultFoodCatalog.items + MercadonaFoodCatalog.load(context))\n            .distinctBy { it.id }\n            .sortedWith(foodComparator)\n    }',
    '    private val baseFoods: List<Food> by lazy {\n'
    '        CatalogBackedFoodCatalog.load(context)\n'
    '            .distinctBy { it.id }\n'
    '            .sortedWith(foodComparator)\n'
    '    }'
)
# Legacy migration still needs an empty default baseline now that managed foods are Carrefour-only.
replace_once(
    "app/src/main/java/es/david/rumbo/data/AppRepository.kt",
    '        val defaultById = DefaultFoodCatalog.items.associateBy { it.id }',
    '        val defaultById = emptyMap<Long, Food>()'
)
replace_once(
    "app/src/main/java/es/david/rumbo/data/AppRepository.kt",
    '        val defaults = DefaultFoodCatalog.items.associateBy { it.id }',
    '        val defaults = emptyMap<Long, Food>()'
)

# Persist roles in user food overrides without breaking older backups.
replace_once(
    "app/src/main/java/es/david/rumbo/data/AppRepository.kt",
    '                put("culinaryType", food.culinaryType.name)\n',
    '                put("culinaryType", food.culinaryType.name)\n'
    '                put("nutritionalRoles", JSONArray(food.nutritionalRoles.toList()))\n'
    '                put("culinaryRoles", JSONArray(food.culinaryRoles.toList()))\n'
)
replace_once(
    "app/src/main/java/es/david/rumbo/data/AppRepository.kt",
    '                    culinaryType = item.optionalEnum("culinaryType", CulinaryType::valueOf)\n'
    '                        ?: baseFoodsById[item.getLong("id")]?.culinaryType\n'
    '                        ?: CulinaryType.UNKNOWN\n',
    '                    culinaryType = item.optionalEnum("culinaryType", CulinaryType::valueOf)\n'
    '                        ?: baseFoodsById[item.getLong("id")]?.culinaryType\n'
    '                        ?: CulinaryType.UNKNOWN,\n'
    '                    nutritionalRoles = item.optJSONArray("nutritionalRoles")?.let { values ->\n'
    '                        buildSet { for (i in 0 until values.length()) add(values.getString(i)) }\n'
    '                    } ?: baseFoodsById[item.getLong("id")]?.nutritionalRoles.orEmpty(),\n'
    '                    culinaryRoles = item.optJSONArray("culinaryRoles")?.let { values ->\n'
    '                        buildSet { for (i in 0 until values.length()) add(values.getString(i)) }\n'
    '                    } ?: baseFoodsById[item.getLong("id")]?.culinaryRoles.orEmpty()\n'
)

# 4) Tests: the bridge must preserve all role axes.
replace_once(
    "app/src/test/java/es/david/rumbo/data/catalog/CatalogFoodAdapterTest.kt",
    '        assertEquals(CulinaryType.MILK_BASE, CatalogFoodAdapter.toFood(product)!!.culinaryType)\n',
    '        val food = CatalogFoodAdapter.toFood(product)!!\n'
    '        assertEquals(CulinaryType.MILK_BASE, food.culinaryType)\n'
    '        assertEquals(product.classification!!.nutritionalRoles, food.nutritionalRoles)\n'
    '        assertEquals(product.classification!!.culinaryRoles, food.culinaryRoles)\n'
)

# 5) Version the installable test cut independently.
replace_once("app/build.gradle", '        versionCode = 71\n        versionName = "0.71.0"',
             '        versionCode = 72\n        versionName = "0.72.0"')

# 6) UI helpers for the canonical filter values and labels.
app = "app/src/main/java/es/david/rumbo/ui/App.kt"
replace_once(
    app,
    'private enum class CatalogFilter { ALL, FOODS, DISHES }\n',
    '''private enum class CatalogFilter { ALL, FOODS, DISHES }\n\nprivate fun Food.retailerValues(): Set<String> = retailer\n    ?.split(",")\n    ?.map { it.trim() }\n    ?.filter { it.isNotBlank() }\n    ?.toSet()\n    .orEmpty()\n\nprivate fun catalogRetailerLabel(value: String): String = value.lowercase()\n    .replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() }\n\nprivate fun nutritionalRoleLabel(value: String): String = when (value) {\n    "PRIMARY_PROTEIN" -> "Proteína principal"\n    "COMPLEMENTARY_PROTEIN" -> "Proteína complementaria"\n    "PRIMARY_CARBOHYDRATE" -> "Hidrato principal"\n    "COMPLEMENTARY_CARBOHYDRATE" -> "Hidrato complementario"\n    "CONCENTRATED_FAT" -> "Grasa concentrada"\n    "COMPLEMENTARY_FAT" -> "Grasa complementaria"\n    "VEGETABLE" -> "Verdura"\n    "FRUIT" -> "Fruta"\n    else -> value.replace('_', ' ').lowercase().replaceFirstChar { it.titlecase() }\n}\n\nprivate fun culinaryRoleLabel(value: String): String = when (value) {\n    "PLATE_CENTER" -> "Centro del plato"\n    "PLATE_BASE" -> "Base del plato"\n    "SIDE" -> "Acompañamiento"\n    "TOPPING" -> "Topping"\n    "SAUCE_DRESSING" -> "Salsa o aliño"\n    "CEREAL_BASE" -> "Base para cereal"\n    "CEREAL_MIX_IN" -> "Cereal para mezclar"\n    "POWDER_BASE" -> "Base para polvo"\n    "POWDER_MIX_IN" -> "Polvo para mezclar"\n    "SANDWICH_BASE" -> "Base de bocadillo"\n    "SANDWICH_FILLING" -> "Relleno de bocadillo"\n    "SPREAD" -> "Untable"\n    "COOKING_MEDIUM" -> "Medio de cocción"\n    "BINDER" -> "Ligante"\n    "COATING" -> "Rebozado"\n    "SEASONING" -> "Condimento"\n    "STANDALONE" -> "Puede tomarse solo"\n    "BEVERAGE" -> "Bebida"\n    "DESSERT" -> "Postre"\n    else -> value.replace('_', ' ').lowercase().replaceFirstChar { it.titlecase() }\n}\n'''
)

# Hoisted catalog filters let a detail pill open the catalog with one active filter.
replace_once(
    app,
    '    var selectedFoodId by rememberSaveable { mutableStateOf<Long?>(null) }\n',
    '    var selectedFoodId by rememberSaveable { mutableStateOf<Long?>(null) }\n'
    '    var catalogRetailerFilter by rememberSaveable { mutableStateOf<String?>(null) }\n'
    '    var catalogNutritionalRoleFilter by rememberSaveable { mutableStateOf<String?>(null) }\n'
    '    var catalogCulinaryRoleFilter by rememberSaveable { mutableStateOf<String?>(null) }\n'
)

# Food catalog call receives the three filters.
replace_once(
    app,
    '                    repertoireFoodIds = data.activeProfileData?.repertoireFoodIds.orEmpty(),\n                    onOpenFood = {\n',
    '                    repertoireFoodIds = data.activeProfileData?.repertoireFoodIds.orEmpty(),\n'
    '                    retailerFilter = catalogRetailerFilter,\n'
    '                    onRetailerFilterChange = { catalogRetailerFilter = it },\n'
    '                    nutritionalRoleFilter = catalogNutritionalRoleFilter,\n'
    '                    onNutritionalRoleFilterChange = { catalogNutritionalRoleFilter = it },\n'
    '                    culinaryRoleFilter = catalogCulinaryRoleFilter,\n'
    '                    onCulinaryRoleFilterChange = { catalogCulinaryRoleFilter = it },\n'
    '                    onOpenFood = {\n'
)

# Add detail-to-filter navigation callback.
replace_once(
    app,
    '                            onOpenFood = {\n                                selectedFoodId?.let { current ->\n',
    '                            onOpenCatalogFilter = { retailer, nutritionalRole, culinaryRole ->\n'
    '                                catalogRetailerFilter = retailer\n'
    '                                catalogNutritionalRoleFilter = nutritionalRole\n'
    '                                catalogCulinaryRoleFilter = culinaryRole\n'
    '                                foodReturnScreenName = null\n'
    '                                screenName = Screen.FOODS.name\n'
    '                            },\n'
    '                            onOpenFood = {\n                                selectedFoodId?.let { current ->\n'
)

# Detail signature.
replace_once(
    app,
    '    dishes: List<Dish>,\n    onOpenFood: (Long) -> Unit,\n    recommendationReason: String?,\n',
    '    dishes: List<Dish>,\n'
    '    onOpenCatalogFilter: (String?, String?, String?) -> Unit,\n'
    '    onOpenFood: (Long) -> Unit,\n'
    '    recommendationReason: String?,\n'
)

# Replace legacy one-category/one-type text with clickable standard Material 3 chips.
replace_once(
    app,
    '''                Text(\n                    food.category.label,\n                    color = foodCategoryColor(food.category),\n                    style = MaterialTheme.typography.bodyMedium\n                )\n                Text(\n                    "Tipo culinario: ${food.culinaryType.label}",\n                    color = MaterialTheme.colorScheme.onSurfaceVariant,\n                    style = MaterialTheme.typography.bodyMedium\n                )\n                HorizontalDivider()\n''',
    '''                CatalogAttributeChipRow(\n                    title = "Comercio",\n                    values = food.retailerValues().sorted(),\n                    label = ::catalogRetailerLabel,\n                    onClick = { onOpenCatalogFilter(it, null, null) }\n                )\n                CatalogAttributeChipRow(\n                    title = "Roles nutricionales",\n                    values = food.nutritionalRoles.sortedBy(::nutritionalRoleLabel),\n                    label = ::nutritionalRoleLabel,\n                    onClick = { onOpenCatalogFilter(null, it, null) }\n                )\n                CatalogAttributeChipRow(\n                    title = "Roles culinarios",\n                    values = food.culinaryRoles.sortedBy(::culinaryRoleLabel),\n                    label = ::culinaryRoleLabel,\n                    onClick = { onOpenCatalogFilter(null, null, it) }\n                )\n                HorizontalDivider()\n'''
)

# Insert reusable detail chip row before FoodDetailScreen.
replace_once(
    app,
    '@Composable\nprivate fun FoodDetailScreen(\n',
    '''@Composable\nprivate fun CatalogAttributeChipRow(\n    title: String,\n    values: List<String>,\n    label: (String) -> String,\n    onClick: (String) -> Unit\n) {\n    if (values.isEmpty()) return\n    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {\n        Text(\n            title,\n            style = MaterialTheme.typography.labelMedium,\n            color = MaterialTheme.colorScheme.onSurfaceVariant\n        )\n        Row(\n            modifier = Modifier.horizontalScroll(rememberScrollState()),\n            horizontalArrangement = Arrangement.spacedBy(8.dp)\n        ) {\n            values.forEach { value ->\n                FilterChip(\n                    selected = false,\n                    onClick = { onClick(value) },\n                    label = { Text(label(value)) }\n                )\n            }\n        }\n    }\n}\n\n@Composable\nprivate fun FoodDetailScreen(\n'''
)

# Replace FoodDishCatalogScreen state with the three hoisted canonical filters.
replace_once(
    app,
    '''    repertoireFoodIds: Set<Long>,\n    onOpenFood: (Long) -> Unit,\n''',
    '''    repertoireFoodIds: Set<Long>,\n    retailerFilter: String?,\n    onRetailerFilterChange: (String?) -> Unit,\n    nutritionalRoleFilter: String?,\n    onNutritionalRoleFilterChange: (String?) -> Unit,\n    culinaryRoleFilter: String?,\n    onCulinaryRoleFilterChange: (String?) -> Unit,\n    onOpenFood: (Long) -> Unit,\n'''
)
replace_once(
    app,
    '''    var filter by rememberSaveable { mutableStateOf(CatalogFilter.ALL) }\n    var categoryFilterName by rememberSaveable { mutableStateOf<String?>(null) }\n    val categoryFilter = categoryFilterName?.let { name ->\n        FoodCategory.entries.firstOrNull { it.name == name }\n    }\n    var culinaryTypeFilterName by rememberSaveable { mutableStateOf<String?>(null) }\n    val culinaryTypeFilter = culinaryTypeFilterName?.let { name ->\n        CulinaryType.entries.firstOrNull { it.name == name }\n    }\n''',
    ''
)
# Filter available options and entries.
replace_once(
    app,
    '    val foodsById = remember(foods) { foods.associateBy { it.id } }\n\n    LaunchedEffect(query) {',
    '''    val foodsById = remember(foods) { foods.associateBy { it.id } }\n    val retailerOptions = remember(foods) { foods.flatMap { it.retailerValues() }.distinct().sorted() }\n    val nutritionalRoleOptions = remember(foods) { foods.flatMap { it.nutritionalRoles }.distinct().sortedBy(::nutritionalRoleLabel) }\n    val culinaryRoleOptions = remember(foods) { foods.flatMap { it.culinaryRoles }.distinct().sortedBy(::culinaryRoleLabel) }\n\n    LaunchedEffect(query) {'''
)
regex_once(
    app,
    r'''    val entries = remember\(\n        foods, dishes, normalizedQuery, filter, categoryFilter,\n        culinaryTypeFilter, mode, repertoireFoodIds\n    \) \{\n        buildList \{.*?\n        \}\.sortedWith\(compareBy<CatalogEntry> \{ it\.name\.lowercase\(\) \}\)\n    \}\n''',
    '''    val entries = remember(\n        foods, dishes, normalizedQuery, retailerFilter, nutritionalRoleFilter,\n        culinaryRoleFilter, mode, repertoireFoodIds\n    ) {\n        buildList {\n            foods.forEach { food ->\n                val searchable = normalizeSearch(\n                    listOfNotNull(\n                        food.name, food.brand, food.family, food.subcategory,\n                        food.retailer, food.barcode\n                    ).joinToString(" ")\n                )\n                val belongs = food.id in repertoireFoodIds\n                val matchesFilters =\n                    (retailerFilter == null || retailerFilter in food.retailerValues()) &&\n                    (nutritionalRoleFilter == null || nutritionalRoleFilter in food.nutritionalRoles) &&\n                    (culinaryRoleFilter == null || culinaryRoleFilter in food.culinaryRoles)\n                if (matchesFilters &&\n                    ((mode == CatalogMode.SEARCH &&\n                        (normalizedQuery.isNotBlank() || retailerFilter != null ||\n                            nutritionalRoleFilter != null || culinaryRoleFilter != null) ||\n                        mode == CatalogMode.REPERTOIRE && belongs) &&\n                    (normalizedQuery.isBlank() || matchesSearch(searchable, normalizedQuery)))) {\n                    add(CatalogEntry(food.id, food.name, false))\n                }\n            }\n            // Dishes have no retailer or canonical food roles. Keep them searchable only\n            // when none of the three food filters is active.\n            if (retailerFilter == null && nutritionalRoleFilter == null && culinaryRoleFilter == null) {\n                dishes.forEach { dish ->\n                    val belongs = dish.ingredients.any { it.foodId in repertoireFoodIds }\n                    if (((mode == CatalogMode.SEARCH && normalizedQuery.isNotBlank()) ||\n                        (mode == CatalogMode.REPERTOIRE && belongs)) &&\n                        (normalizedQuery.isBlank() || matchesSearch(normalizeSearch(dish.name), normalizedQuery))) {\n                        add(CatalogEntry(dish.id, dish.name, true))\n                    }\n                }\n            }\n        }.sortedWith(compareBy<CatalogEntry> { it.name.lowercase() })\n    }\n'''
)

# Replace both visible filter groups in FoodDishCatalogScreen.
old_filters = '''                    CatalogFilterChips(filter = filter, onFilterChange = { filter = it })\n                    CatalogCategoryMenu(categoryFilter) { categoryFilterName = it?.name }\n                    CatalogCulinaryTypeMenu(culinaryTypeFilter) {\n                        culinaryTypeFilterName = it?.name\n                    }'''
new_filters = '''                    CatalogCanonicalFilterRow(\n                        retailerFilter, onRetailerFilterChange, retailerOptions,\n                        nutritionalRoleFilter, onNutritionalRoleFilterChange, nutritionalRoleOptions,\n                        culinaryRoleFilter, onCulinaryRoleFilterChange, culinaryRoleOptions\n                    )'''
replace_once(app, old_filters, new_filters)
replace_once(app, old_filters.replace('                    ', '                '), new_filters.replace('                    ', '                '))

# Standard Material 3 dropdown FilterChips: exactly retailer + nutritional role + culinary role.
insert_marker = '@Composable\nprivate fun CatalogFilterChips(\n'
insert = '''@Composable\nprivate fun CatalogCanonicalFilterRow(\n    retailer: String?, onRetailerChange: (String?) -> Unit, retailerOptions: List<String>,\n    nutritionalRole: String?, onNutritionalRoleChange: (String?) -> Unit, nutritionalRoleOptions: List<String>,\n    culinaryRole: String?, onCulinaryRoleChange: (String?) -> Unit, culinaryRoleOptions: List<String>\n) {\n    Row(\n        modifier = Modifier.horizontalScroll(rememberScrollState()),\n        horizontalArrangement = Arrangement.spacedBy(8.dp)\n    ) {\n        CatalogStringFilterMenu(\n            title = "Comercio", selected = retailer, options = retailerOptions,\n            label = ::catalogRetailerLabel, onChange = onRetailerChange\n        )\n        CatalogStringFilterMenu(\n            title = "Rol nutricional", selected = nutritionalRole, options = nutritionalRoleOptions,\n            label = ::nutritionalRoleLabel, onChange = onNutritionalRoleChange\n        )\n        CatalogStringFilterMenu(\n            title = "Rol culinario", selected = culinaryRole, options = culinaryRoleOptions,\n            label = ::culinaryRoleLabel, onChange = onCulinaryRoleChange\n        )\n    }\n}\n\n@Composable\nprivate fun CatalogStringFilterMenu(\n    title: String,\n    selected: String?,\n    options: List<String>,\n    label: (String) -> String,\n    onChange: (String?) -> Unit\n) {\n    var expanded by remember { mutableStateOf(false) }\n    Box {\n        FilterChip(\n            selected = selected != null,\n            onClick = { expanded = true },\n            label = { Text(selected?.let(label) ?: title) },\n            trailingIcon = { Icon(Icons.Default.ArrowDropDown, contentDescription = null) }\n        )\n        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {\n            DropdownMenuItem(\n                leadingIcon = { if (selected == null) Icon(Icons.Default.Check, contentDescription = null) },\n                text = { Text("Todos") },\n                onClick = { onChange(null); expanded = false }\n            )\n            options.forEach { option ->\n                DropdownMenuItem(\n                    leadingIcon = { if (selected == option) Icon(Icons.Default.Check, contentDescription = null) },\n                    text = { Text(label(option)) },\n                    onClick = { onChange(option); expanded = false }\n                )\n            }\n        }\n    }\n}\n\n'''
replace_once(app, insert_marker, insert + insert_marker)

print("Carrefour role/filter UI transformation applied")
