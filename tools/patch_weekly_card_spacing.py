from pathlib import Path

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
t = p.read_text()
old = '''    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Tu menú de esta semana", style = MaterialTheme.typography.titleLarge)
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.fillMaxWidth()) {
                SummarySection(expandedSection == summaryKey)
                WeekDay.entries.forEach { day ->
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    DaySection(day, expandedSection == day.name)
                }
            }
        }
    }
'''
new = '''    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Tu menú de esta semana", style = MaterialTheme.typography.titleLarge)
        Column(
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
    }
'''
if old not in t:
    raise SystemExit('No se encontró el bloque semanal esperado')
t = t.replace(old, new, 1)
p.write_text(t)
print('Tarjetas semanales separadas 4 dp')
