from pathlib import Path

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
t = p.read_text()

old = '''    Card(Modifier.fillMaxWidth().clickable(onClick = onExplain)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            HomeCardHeader("Situación y objetivo")
'''
new = '''    Text("Situación y objetivo", style = MaterialTheme.typography.titleLarge)
    Spacer(Modifier.height(12.dp))
    Card(Modifier.fillMaxWidth().clickable(onClick = onExplain)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
'''
if old not in t:
    raise SystemExit('No se encontró la cabecera de Situación y objetivo')
t = t.replace(old, new, 1)

old = '''        Column(
            Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Card(Modifier.fillMaxWidth()) {
                SummarySection(expandedSection == summaryKey)
            }
            WeekDay.entries.forEach { day ->
                Card(Modifier.fillMaxWidth()) {
                    DaySection(day, expandedSection == day.name)
                }
            }
        }
'''
new = '''        Column(
            Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Card(
                Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(
                    topStart = 12.dp,
                    topEnd = 12.dp,
                    bottomStart = 4.dp,
                    bottomEnd = 4.dp
                )
            ) {
                SummarySection(expandedSection == summaryKey)
            }
            WeekDay.entries.forEachIndexed { index, day ->
                val isLast = index == WeekDay.entries.lastIndex
                Card(
                    Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(
                        topStart = 4.dp,
                        topEnd = 4.dp,
                        bottomStart = if (isLast) 12.dp else 4.dp,
                        bottomEnd = if (isLast) 12.dp else 4.dp
                    )
                ) {
                    DaySection(day, expandedSection == day.name)
                }
            }
        }
'''
if old not in t:
    raise SystemExit('No se encontró el grupo de tarjetas semanales')
t = t.replace(old, new, 1)

# En las tiras donde calorías comparten fila con macros, usa el mismo color de énfasis.
t = t.replace(
    'Icons.Default.LocalFireDepartment, MaterialTheme.colorScheme.onSurface, Modifier.weight(1f)',
    'Icons.Default.LocalFireDepartment, MaterialTheme.colorScheme.onSurfaceVariant, Modifier.weight(1f)'
)
t = t.replace(
    'Icons.Default.LocalFireDepartment, MaterialTheme.colorScheme.onSurface\n                    )',
    'Icons.Default.LocalFireDepartment, MaterialTheme.colorScheme.onSurfaceVariant\n                    )'
)
t = t.replace(
    'Icons.Default.LocalFireDepartment, "Calorías", food.calories, "kcal",\n            MaterialTheme.colorScheme.onSurface, Modifier.weight(1.25f)',
    'Icons.Default.LocalFireDepartment, "Calorías", food.calories, "kcal",\n            MaterialTheme.colorScheme.onSurfaceVariant, Modifier.weight(1.25f)'
)

p.write_text(t)
print('Pulido visual aplicado')
