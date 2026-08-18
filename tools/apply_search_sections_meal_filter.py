from pathlib import Path
import re

APP = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
POLICY = Path('app/src/main/java/es/david/rumbo/logic/CulinaryPolicy.kt')

def exact(s, old, new, name):
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{name}: expected 1 match, got {n}')
    return s.replace(old, new, 1)

def sub1(s, pattern, repl, name, flags=re.S):
    out, n = re.subn(pattern, repl, s, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f'{name}: expected 1 regex match, got {n}')
    return out

# -------- central culinary policy: suggested meals belong to role policy --------
p = POLICY
s = p.read_text()
s = exact(s,
'''import es.david.rumbo.model.Food
import es.david.rumbo.model.PlanningRule
''',
'''import es.david.rumbo.model.Food
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlanningRule
''', 'MealType import')
s = exact(s,
'''    val standaloneAllowed: Boolean = true,
    val requiredRoles: Set<CulinaryRole> = emptySet(),
    val maxPerMeal: Int? = null
)''',
'''    val standaloneAllowed: Boolean = true,
    val requiredRoles: Set<CulinaryRole> = emptySet(),
    val maxPerMeal: Int? = null,
    val suggestedMealTypes: Set<MealType> = MealType.entries.toSet()
)''', 'policy model suggested meals')

# Add explicit role->meal defaults after policy map is built, without disturbing positional constructors.
anchor = '''    @Volatile private var profileOverrides: Map<CulinaryRole, CulinaryRolePolicy> = emptyMap()
'''
replacement = '''    private val suggestedMealsByRole: Map<CulinaryRole, Set<MealType>> = mapOf(
        CulinaryRole.CEREAL_BASE to setOf(MealType.BREAKFAST),
        CulinaryRole.CEREAL_MIX_IN to setOf(MealType.BREAKFAST),
        CulinaryRole.POWDER_BASE to setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        CulinaryRole.POWDER_MIX_IN to setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        CulinaryRole.SANDWICH_BASE to setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        CulinaryRole.SANDWICH_FILLING to setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        CulinaryRole.SPREAD to setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        CulinaryRole.BEVERAGE to setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        CulinaryRole.DESSERT to MealType.entries.toSet(),
        CulinaryRole.STANDALONE to MealType.entries.toSet(),
        CulinaryRole.PLATE_CENTER to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.PLATE_BASE to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.SIDE to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.TOPPING to MealType.entries.toSet(),
        CulinaryRole.SAUCE_DRESSING to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.COOKING_MEDIUM to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.BINDER to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.COATING to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.SEASONING to setOf(MealType.LUNCH, MealType.DINNER)
    )

    @Volatile private var profileOverrides: Map<CulinaryRole, CulinaryRolePolicy> = emptyMap()
'''
s = exact(s, anchor, replacement, 'suggested meal map')

s = exact(s,
'''    fun defaultPolicy(role: CulinaryRole): CulinaryRolePolicy = policies.getValue(role)
    fun policy(role: CulinaryRole): CulinaryRolePolicy = profileOverrides[role] ?: defaultPolicy(role)
''',
'''    fun defaultPolicy(role: CulinaryRole): CulinaryRolePolicy = policies.getValue(role).copy(
        suggestedMealTypes = suggestedMealsByRole[role] ?: MealType.entries.toSet()
    )
    fun policy(role: CulinaryRole): CulinaryRolePolicy = profileOverrides[role]
        ?.copy(suggestedMealTypes = suggestedMealsByRole[role] ?: MealType.entries.toSet())
        ?: defaultPolicy(role)
''', 'default role policy with meals')

s = exact(s,
'''    fun addresses(need: CulinaryNeed, food: Food): Boolean =
        roles(food).any { it in need.acceptedRoles }
''',
'''    fun addresses(need: CulinaryNeed, food: Food): Boolean =
        roles(food).any { it in need.acceptedRoles }

    fun isSuggestedForMeal(food: Food, mealType: MealType): Boolean =
        roles(food).any { role -> mealType in policy(role).suggestedMealTypes }
''', 'meal suggestion helper')
p.write_text(s)

# -------- App UI/search --------
p = APP
s = p.read_text()

# Request token must not survive process restoration and must never be reset to a reused value.
s = exact(s,
'''    var catalogSearchRequest by rememberSaveable { mutableStateOf(0) }
''',
'''    var catalogSearchRequest by remember { mutableIntStateOf(0) }
''', 'search request token')

# HomeScreen signature/call: remove consumed callback and pass planning rules.
s = exact(s,
'''    requestedSearchCulinaryRole: String?,
    searchOpenRequest: Int,
    onSearchRequestConsumed: () -> Unit,
''',
'''    requestedSearchCulinaryRole: String?,
    searchOpenRequest: Int,
''', 'HomeScreen request signature')
s = exact(s,
'''                    searchOpenRequest = catalogSearchRequest,
                    onSearchRequestConsumed = { catalogSearchRequest = 0 },
''',
'''                    searchOpenRequest = catalogSearchRequest,
''', 'HomeScreen request call')

# Search state: add meal filter and snap directly to expanded state.
s = exact(s,
'''    var searchCulinaryRole by rememberSaveable { mutableStateOf<String?>(null) }
    var searchMessage by remember { mutableStateOf<String?>(null) }
''',
'''    var searchCulinaryRole by rememberSaveable { mutableStateOf<String?>(null) }
    var searchMealTypeName by rememberSaveable { mutableStateOf<String?>(null) }
    val searchMealType = searchMealTypeName?.let { runCatching { MealType.valueOf(it) }.getOrNull() }
    var searchMessage by remember { mutableStateOf<String?>(null) }
''', 'meal filter state')
s = exact(s,
'''            searchCulinaryRole = requestedSearchCulinaryRole
            searchTextState.setTextAndPlaceCursorAtEnd("")
            searchListState.scrollToItem(0)
            searchBarState.animateToExpanded()
            onSearchRequestConsumed()
''',
'''            searchCulinaryRole = requestedSearchCulinaryRole
            searchMealTypeName = null
            searchTextState.setTextAndPlaceCursorAtEnd("")
            searchListState.scrollToItem(0)
            searchBarState.snapTo(1f)
''', 'direct expansion')

s = exact(s,
'''                repertoireFoodIds = data.activeProfileData?.repertoireFoodIds.orEmpty(),
                foodSuggestions = pinnedSuggestions,
''',
'''                repertoireFoodIds = data.activeProfileData?.repertoireFoodIds.orEmpty(),
                planningRules = data.activeProfileData?.planningRules.orEmpty(),
                foodSuggestions = pinnedSuggestions,
''', 'pass planning rules')
s = exact(s,
'''                culinaryRoleFilter = searchCulinaryRole,
                onCulinaryRoleFilterChange = { searchCulinaryRole = it },
                scanMessage = searchMessage,
''',
'''                culinaryRoleFilter = searchCulinaryRole,
                onCulinaryRoleFilterChange = { searchCulinaryRole = it },
                mealTypeFilter = searchMealType,
                onMealTypeFilterChange = { searchMealTypeName = it?.name },
                scanMessage = searchMessage,
''', 'pass meal filter')

# HomeCatalogSearch signature.
s = exact(s,
'''private fun HomeCatalogSearch(
    foods: List<Food>, dishes: List<Dish>, repertoireFoodIds: Set<Long>,
    foodSuggestions: List<FoodSuggestion>,
''',
'''private fun HomeCatalogSearch(
    foods: List<Food>, dishes: List<Dish>, repertoireFoodIds: Set<Long>,
    planningRules: List<PlanningRule>,
    foodSuggestions: List<FoodSuggestion>,
''', 'search signature rules')
s = exact(s,
'''    nutritionalRoleFilter: String?, onNutritionalRoleFilterChange: (String?) -> Unit,
    culinaryRoleFilter: String?, onCulinaryRoleFilterChange: (String?) -> Unit,
    scanMessage: String?, onScanMessageChange: (String?) -> Unit,
''',
'''    nutritionalRoleFilter: String?, onNutritionalRoleFilterChange: (String?) -> Unit,
    culinaryRoleFilter: String?, onCulinaryRoleFilterChange: (String?) -> Unit,
    mealTypeFilter: MealType?, onMealTypeFilterChange: (MealType?) -> Unit,
    scanMessage: String?, onScanMessageChange: (String?) -> Unit,
''', 'search signature meal filter')

# Replace result construction completely: foods only, strict intersection, own first.
result_pattern = r'''    val suggestionsByFoodId = remember\(foodSuggestions\) \{.*?\n    val leaveForDetail = \{'''
result_repl = '''    val suggestionsByFoodId = remember(foodSuggestions) {
        foodSuggestions.associateBy { it.food.id }
    }
    val personalizedScores = remember(foods, repertoireAssessment, recommendation) {
        foods.associate { food ->
            food.id to FoodSuggestionEngine.personalizedSearchScore(
                food, repertoireAssessment, recommendation
            )
        }
    }
    val activeFoodRules = remember(planningRules) {
        planningRules.filter {
            it.itemKind == PlannedItemKind.FOOD && it.isActive &&
                it.frequency != PlanningFrequency.NEVER
        }
    }
    val hasActiveFilters = retailerFilter != null || nutritionalRoleFilter != null ||
        culinaryRoleFilter != null || mealTypeFilter != null
    val entries = remember(
        foods, normalized, retailerFilter, nutritionalRoleFilter, culinaryRoleFilter,
        mealTypeFilter, repertoireFoodIds, activeFoodRules, personalizedScores
    ) {
        foods.asSequence().filter { food ->
            val isMine = food.id in repertoireFoodIds
            val searchText = normalizeSearch(
                listOfNotNull(
                    food.name, food.brand, food.family, food.subcategory,
                    food.barcode, food.retailer
                ).joinToString(" ")
            )
            val matchesText = normalized.isBlank() || matchesSearch(searchText, normalized)
            val matchesMeal = when {
                mealTypeFilter == null -> true
                isMine -> activeFoodRules.any { rule ->
                    rule.itemId == food.id &&
                        (mealTypeFilter in rule.allowedMealTypes ||
                            rule.requiredSlots().any { it.mealType == mealTypeFilter })
                }
                else -> CulinaryPolicy.isSuggestedForMeal(food, mealTypeFilter)
            }
            val matchesFilters =
                (retailerFilter == null || retailerFilter in food.retailerValues()) &&
                (nutritionalRoleFilter == null || nutritionalRoleFilter in food.nutritionalRoles) &&
                (culinaryRoleFilter == null || culinaryRoleFilter in food.culinaryRoles) &&
                matchesMeal
            val visibleByMode = if (normalized.isBlank() && !hasActiveFilters) isMine else true
            visibleByMode && matchesText && matchesFilters
        }.map { CatalogEntry(it.id, it.name, false) }
            .sortedWith(
                compareBy<CatalogEntry> { it.id !in repertoireFoodIds }
                    .thenBy { if (normalized.isBlank()) 0 else searchMatchRank(it.name, normalized) }
                    .thenByDescending { personalizedScores[it.id] ?: Double.NEGATIVE_INFINITY }
                    .thenBy { it.name.lowercase() }
            ).toList()
    }

    val leaveForDetail = {'''
s = sub1(s, result_pattern, result_repl, 'search result algorithm')

# Header adds fourth filter and copy only for totally blank state.
s = exact(s,
'''                        CatalogCanonicalFilterRow(
                            retailerFilter, onRetailerFilterChange, retailerOptions,
                            nutritionalRoleFilter, onNutritionalRoleFilterChange, nutritionalRoleOptions,
                            culinaryRoleFilter, onCulinaryRoleFilterChange, culinaryRoleOptions
                        )
                        if (query.isBlank()) {
''',
'''                        CatalogCanonicalFilterRow(
                            retailerFilter, onRetailerFilterChange, retailerOptions,
                            nutritionalRoleFilter, onNutritionalRoleFilterChange, nutritionalRoleOptions,
                            culinaryRoleFilter, onCulinaryRoleFilterChange, culinaryRoleOptions,
                            mealTypeFilter, onMealTypeFilterChange
                        )
                        if (query.isBlank() && !hasActiveFilters) {
''', 'header filters')

# Mode is now presentational only; blank search still has actual entries.
s = exact(s,
'''                mode = if (query.isBlank()) CatalogMode.REPERTOIRE else CatalogMode.SEARCH,
''',
'''                mode = CatalogMode.SEARCH,
''', 'search mode')

# Four-filter row plus reliable trailing edge spacer.
s = exact(s,
'''private fun CatalogCanonicalFilterRow(
    retailer: String?, onRetailerChange: (String?) -> Unit, retailerOptions: List<String>,
    nutritionalRole: String?, onNutritionalRoleChange: (String?) -> Unit, nutritionalRoleOptions: List<String>,
    culinaryRole: String?, onCulinaryRoleChange: (String?) -> Unit, culinaryRoleOptions: List<String>
) {
''',
'''private fun CatalogCanonicalFilterRow(
    retailer: String?, onRetailerChange: (String?) -> Unit, retailerOptions: List<String>,
    nutritionalRole: String?, onNutritionalRoleChange: (String?) -> Unit, nutritionalRoleOptions: List<String>,
    culinaryRole: String?, onCulinaryRoleChange: (String?) -> Unit, culinaryRoleOptions: List<String>,
    mealType: MealType?, onMealTypeChange: (MealType?) -> Unit
) {
''', 'canonical filter signature')
s = exact(s,
'''        CatalogStringFilterMenu(
            title = "Rol culinario", selected = culinaryRole, options = culinaryRoleOptions,
            label = ::culinaryRoleLabel, onChange = onCulinaryRoleChange
        )
    }
}
''',
'''        CatalogStringFilterMenu(
            title = "Rol culinario", selected = culinaryRole, options = culinaryRoleOptions,
            label = ::culinaryRoleLabel, onChange = onCulinaryRoleChange
        )
        CatalogMealTypeFilterMenu(mealType, onMealTypeChange)
        Spacer(Modifier.width(16.dp))
    }
}

@Composable
private fun CatalogMealTypeFilterMenu(
    selected: MealType?,
    onChange: (MealType?) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        FilterChip(
            selected = selected != null,
            onClick = { expanded = true },
            label = { Text(selected?.label ?: "Comidas") },
            trailingIcon = { Icon(Icons.Default.ArrowDropDown, contentDescription = null) }
        )
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(
                leadingIcon = { if (selected == null) Icon(Icons.Default.Check, contentDescription = null) },
                text = { Text("Todas") },
                onClick = { onChange(null); expanded = false }
            )
            MealType.entries.forEach { option ->
                DropdownMenuItem(
                    leadingIcon = { if (selected == option) Icon(Icons.Default.Check, contentDescription = null) },
                    text = { Text(option.label) },
                    onClick = { onChange(option); expanded = false }
                )
            }
        }
    }
}
''', 'meal filter menu')

# Compact sectioning: only Mis alimentos / Otros alimentos, never Recomendados.
section_pattern = r'''            if \(compactPresentation && normalizedQuery\.isBlank\(\)\) \{.*?            \}\n            if \(compactPresentation\) \{'''
section_repl = '''            if (compactPresentation) {
                val entryIndex = entries.indexOf(entry)
                val previous = entries.getOrNull(entryIndex - 1)
                val isMine = !entry.isDish && entry.id in repertoireFoodIds
                val previousWasMine = previous != null && !previous.isDish && previous.id in repertoireFoodIds
                val sectionTitle = when {
                    isMine && !previousWasMine -> "Mis alimentos"
                    !isMine && (previous == null || previousWasMine) -> "Otros alimentos"
                    else -> null
                }
                sectionTitle?.let {
                    Text(
                        it,
                        modifier = Modifier.padding(top = 16.dp, bottom = 6.dp),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
            if (compactPresentation) {'''
s = sub1(s, section_pattern, section_repl, 'compact section headers')

# Blank query should not show the old "type something" footer when own foods are already visible.
s = exact(s,
'''        if (mode == CatalogMode.SEARCH && normalizedQuery.isBlank()) {
            item {
                Text(
                    "Escribe el nombre de un alimento o plato, o escanea su código de barras.",
                    modifier = Modifier.padding(vertical = 24.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        } else if (entries.isEmpty()) {
''',
'''        if (entries.isEmpty()) {
''', 'remove obsolete blank footer')

# Detail chips: an explicit trailing spacer guarantees scrollable right padding.
s = exact(s,
'''            values.forEach { value ->
                FilterChip(
                    selected = false,
                    onClick = { onClick(value) },
                    label = { Text(label(value)) }
                )
            }
        }
''',
'''            values.forEach { value ->
                FilterChip(
                    selected = false,
                    onClick = { onClick(value) },
                    label = { Text(label(value)) }
                )
            }
            Spacer(Modifier.width(16.dp))
        }
''', 'detail chip trailing edge')

p.write_text(s)
print('search UI transformation prepared successfully')
