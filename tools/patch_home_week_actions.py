from pathlib import Path

path = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = path.read_text()

def rep(old: str, new: str, label: str):
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 occurrence, found {count}')
    s = s.replace(old, new, 1)

# Distinguish the shopping list opened from the avatar (current/next selector)
# from the current-week-only list opened from the weekly nutrition card.
rep(
    '    var shoppingWeekName by rememberSaveable { mutableStateOf(PlanWeek.CURRENT.name) }\n',
    '    var shoppingWeekName by rememberSaveable { mutableStateOf(PlanWeek.CURRENT.name) }\n'
    '    var shoppingCurrentOnly by rememberSaveable { mutableStateOf(false) }\n',
    'shopping mode state'
)

rep(
    '                    onOpenShoppingList = { shoppingWeekName = PlanWeek.CURRENT.name; screenName = Screen.SHOPPING_LIST.name },\n',
    '                    onOpenShoppingList = {\n'
    '                        shoppingCurrentOnly = false\n'
    '                        shoppingWeekName = PlanWeek.CURRENT.name\n'
    '                        screenName = Screen.SHOPPING_LIST.name\n'
    '                    },\n'
    '                    onOpenCurrentShoppingList = {\n'
    '                        shoppingCurrentOnly = true\n'
    '                        shoppingWeekName = PlanWeek.CURRENT.name\n'
    '                        screenName = Screen.SHOPPING_LIST.name\n'
    '                    },\n',
    'home shopping callbacks'
)

rep(
    '    onOpenShoppingList: () -> Unit,\n    onOpenSettings: () -> Unit,\n',
    '    onOpenShoppingList: () -> Unit,\n    onOpenCurrentShoppingList: () -> Unit,\n    onOpenSettings: () -> Unit,\n',
    'HomeScreen signature'
)

rep(
    '                recommendation = recommendation,\n                onOpenNextWeek = onOpenNextWeek,\n',
    '                recommendation = recommendation,\n                onOpenNextWeek = onOpenNextWeek,\n                onOpenCurrentShoppingList = onOpenCurrentShoppingList,\n',
    'weekly section call'
)

rep(
    '    recommendation: es.david.rumbo.model.Recommendation?,\n    onOpenNextWeek: () -> Unit,\n',
    '    recommendation: es.david.rumbo.model.Recommendation?,\n    onOpenNextWeek: () -> Unit,\n    onOpenCurrentShoppingList: () -> Unit,\n',
    'weekly section signature'
)

# The shopping list reached from the weekly summary is deliberately current-week-only.
rep(
    '                screen == Screen.SHOPPING_LIST -> ShoppingListScreen(\n'
    '                    data = data,\n'
    '                    week = PlanWeek.valueOf(shoppingWeekName),\n'
    '                    onWeekChange = { shoppingWeekName = it.name },\n'
    '                    onBack = { screenName = Screen.HOME.name }\n'
    '                )\n',
    '                screen == Screen.SHOPPING_LIST -> ShoppingListScreen(\n'
    '                    data = data,\n'
    '                    week = PlanWeek.valueOf(shoppingWeekName),\n'
    '                    onWeekChange = { shoppingWeekName = it.name },\n'
    '                    showWeekSelector = !shoppingCurrentOnly,\n'
    '                    onBack = { shoppingCurrentOnly = false; screenName = Screen.HOME.name }\n'
    '                )\n',
    'shopping screen call'
)

rep(
    'private fun ShoppingListScreen(\n'
    '    data: AppData,\n'
    '    week: PlanWeek,\n'
    '    onWeekChange: (PlanWeek) -> Unit,\n'
    '    onBack: () -> Unit\n'
    ') {\n',
    'private fun ShoppingListScreen(\n'
    '    data: AppData,\n'
    '    week: PlanWeek,\n'
    '    onWeekChange: (PlanWeek) -> Unit,\n'
    '    showWeekSelector: Boolean = true,\n'
    '    onBack: () -> Unit\n'
    ') {\n',
    'shopping screen signature'
)

segmented = '''            item {
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
'''
rep(
    segmented,
    '''            if (showWeekSelector) {
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
            }
''',
    'shopping week selector'
)

# Summary actions: rebuild + current week's shopping list.
rep(
    '                        FilledTonalButton(\n'
    '                            onClick = onOpenNextWeek,\n'
    '                            modifier = Modifier.weight(1f)\n'
    '                        ) { Text("Semana que viene") }\n',
    '                        FilledTonalButton(\n'
    '                            onClick = onOpenCurrentShoppingList,\n'
    '                            modifier = Modifier.weight(1f)\n'
    '                        ) { Text("Lista de la compra") }\n',
    'summary second action'
)

# Visually separate the whole-day totals from the first meal, just as meals are separated from each other.
rep(
    '                    Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 16.dp),\n'
    '                    verticalArrangement = Arrangement.spacedBy(10.dp)\n'
    '                ) {\n'
    '                    if (dayMeals.isEmpty()) {\n',
    '                    Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 16.dp),\n'
    '                    verticalArrangement = Arrangement.spacedBy(10.dp)\n'
    '                ) {\n'
    '                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)\n'
    '                    if (dayMeals.isEmpty()) {\n',
    'daily totals divider'
)

# The next-week action belongs after the whole current-week accordion, outside the cards.
marker = '        }\n    }\n}\n\nprivate data class MenuItemLine('
replacement = '''        }
        FilledTonalButton(
            onClick = onOpenNextWeek,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Ver menú de la semana que viene")
        }
    }
}

private data class MenuItemLine('''
rep(marker, replacement, 'next-week bottom action')

path.write_text(s)
print('Home weekly actions patched successfully')
