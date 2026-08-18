from pathlib import Path

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()

def exact(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, got {n}')
    s = s.replace(old, new, 1)

# 1. Root search state is session-local. No collapsed state exists before the overlay opens.
exact(
'''    var catalogSearchOverlayOpen by remember { mutableStateOf(false) }
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
'''    var catalogSearchOverlayOpen by remember { mutableStateOf(false) }
    var catalogSearchMealTypeName by rememberSaveable { mutableStateOf<String?>(null) }
    val catalogSearchMealType = catalogSearchMealTypeName?.let {
        runCatching { MealType.valueOf(it) }.getOrNull()
    }
''',
'root persistent overlay state')

exact(
'''    if (catalogSearchOverlayOpen) {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background
        ) {
            HomeCatalogSearch(
''',
'''    if (catalogSearchOverlayOpen) {
        val catalogOverlayTextState = rememberTextFieldState()
        val catalogOverlaySearchState = rememberSearchBarState(
            initialValue = SearchBarValue.Expanded
        )
        val catalogOverlayListState = rememberLazyListState()
        val catalogOverlayScrollBehavior = SearchBarDefaults.enterAlwaysSearchBarScrollBehavior()
        var catalogOverlayMessage by remember { mutableStateOf<String?>(null) }
        var catalogOverlaySuppressKeyboard by remember { mutableStateOf(false) }
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background
        ) {
            HomeCatalogSearch(
''',
'overlay session state')

exact(
'''                trailingContent = {}
            )
''',
'''                trailingContent = {},
                showCollapsedBar = false
            )
''',
'root expanded-only search')

# 2. HomeCatalogSearch can render only the expanded destination for root overlay sessions.
exact(
'''    onCloseSearch: () -> Unit,
    onOpenFood: (Long) -> Unit, onOpenDish: (Long) -> Unit,
    trailingContent: @Composable () -> Unit
) {
''',
'''    onCloseSearch: () -> Unit,
    onOpenFood: (Long) -> Unit, onOpenDish: (Long) -> Unit,
    trailingContent: @Composable () -> Unit,
    showCollapsedBar: Boolean = true
) {
''',
'search signature')

exact(
'''    AppBarWithSearch(
        state = state,
        inputField = inputField,
        scrollBehavior = scrollBehavior,
        colors = appBarColors,
        actions = {},
        modifier = Modifier.fillMaxWidth(),
        contentPadding = PaddingValues(horizontal = 16.dp),
        tonalElevation = 0.dp
    )

    ExpandedFullScreenSearchBar(
''',
'''    if (showCollapsedBar) {
        AppBarWithSearch(
            state = state,
            inputField = inputField,
            scrollBehavior = scrollBehavior,
            colors = appBarColors,
            actions = {},
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 16.dp),
            tonalElevation = 0.dp
        )
    }

    ExpandedFullScreenSearchBar(
''',
'collapsed search conditional')

# 3. Search list goes edge-to-edge; compact rows keep their normal 16dp inset themselves.
exact(
'''                modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
''',
'''                modifier = Modifier.fillMaxSize(),
''',
'search outer padding')

exact(
'''                            Text(
                                "Escribe el nombre de un alimento o plato, escanea su código de barras o elígelo de tu repertorio.",
                                Modifier.padding(vertical = 12.dp),
''',
'''                            Text(
                                "Escribe el nombre de un alimento o plato, escanea su código de barras o elígelo de tu repertorio.",
                                Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
''',
'search helper text padding')

exact(
'''                        scanMessage?.let { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
''',
'''                        scanMessage?.let {
                            Text(
                                it,
                                modifier = Modifier.padding(horizontal = 16.dp),
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
''',
'scan message padding')

exact(
'''    LazyRow(
        contentPadding = PaddingValues(end = 16.dp),
''',
'''    LazyRow(
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp),
''',
'search filter edge padding')

exact(
'''                        modifier = Modifier.padding(top = 16.dp, bottom = 6.dp),
''',
'''                        modifier = Modifier.padding(start = 16.dp, top = 16.dp, end = 16.dp, bottom = 6.dp),
''',
'compact section heading padding')

exact(
'''                        .padding(vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
''',
'''                        .padding(horizontal = 16.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
''',
'compact result row padding')

exact(
'''            if (entry != entries.lastOrNull()) HorizontalDivider()
''',
'''            if (entry != entries.lastOrNull()) {
                HorizontalDivider(
                    modifier = if (compactPresentation) Modifier.padding(horizontal = 16.dp) else Modifier
                )
            }
''',
'compact divider padding')

# 4. Food detail itself goes edge-to-edge; ordinary content receives its own inset,
# while horizontal chip rows use the full screen width plus true 16dp contentPadding.
exact(
'''                .padding(
                    start = 16.dp,
                    end = 16.dp,
                    bottom = innerPadding.calculateBottomPadding() + 16.dp
                ),
''',
'''                .padding(bottom = innerPadding.calculateBottomPadding() + 16.dp),
''',
'food detail outer horizontal padding')

exact(
'''                Card(Modifier.fillMaxWidth()) {
''',
'''                Card(Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
''',
'recommendation card inset')

# Chip row titles should retain the standard left inset; list itself owns both edge paddings.
exact(
'''    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            title,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        LazyRow(
            contentPadding = PaddingValues(end = 16.dp),
''',
'''    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            title,
            modifier = Modifier.padding(horizontal = 16.dp),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        LazyRow(
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp),
''',
'detail chip true edge padding')

# The metadata/nutrition block remains visually inset. Chips stay full bleed.
exact(
'''                        Text(
                            it,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.bodyLarge
                        )
''',
'''                        Text(
                            it,
                            modifier = Modifier.padding(horizontal = 16.dp),
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.bodyLarge
                        )
''',
'food subtitle inset')

# From the first divider after the chips onward, wrap regular detail content in a padded Column.
exact(
'''                HorizontalDivider()
                Text(
                    "Valores por 100 g o 100 ml",
''',
'''                Column(
                    Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                HorizontalDivider()
                Text(
                    "Valores por 100 g o 100 ml",
''',
'open padded nutrition block')

# Close that padded block before the first section ends.
exact(
'''                        if (index < food.links.lastIndex) HorizontalDivider()
                    }
                }
            }

            Column(
''',
'''                        if (index < food.links.lastIndex) HorizontalDivider()
                    }
                }
                }
            }

            Column(
''',
'close padded nutrition block')

# Later full-width sections keep the normal screen inset.
exact(
'''            Column(
                Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                    Text("En qué platos puedes comerlo", style = MaterialTheme.typography.titleLarge)
''',
'''            Column(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                    Text("En qué platos puedes comerlo", style = MaterialTheme.typography.titleLarge)
''',
'containing dishes inset')

exact(
'''            Column(
                Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text("Alternativas más eficientes", style = MaterialTheme.typography.titleLarge)
''',
'''            Column(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text("Alternativas más eficientes", style = MaterialTheme.typography.titleLarge)
''',
'alternatives inset')

p.write_text(s)
print('first-open expanded search and full-bleed chip rows applied')
