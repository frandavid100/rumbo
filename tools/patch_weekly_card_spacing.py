from pathlib import Path

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
t = p.read_text()

old = '''    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Tu menú de esta semana", style = MaterialTheme.typography.titleLarge)
        Card(
            Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)
        ) {
            Column(Modifier.fillMaxWidth()) {
                entries.forEachIndexed { index, entry ->
                    if (index > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    val isExpanded = expandedSection == entry.key
                    Column(
                        Modifier.fillMaxWidth()
                    ) {
'''
new = '''    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Tu menú de esta semana", style = MaterialTheme.typography.titleLarge)
        Column(
            Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            entries.forEach { entry ->
                val isExpanded = expandedSection == entry.key
                Card(
                    Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)
                ) {
                    Column(Modifier.fillMaxWidth()) {
'''
if old not in t:
    raise SystemExit('No se encontró el bloque del acordeón semanal')
t = t.replace(old, new, 1)

old_tail = '''                    }
                }
            }
        }
    }
}

private data class MenuItemLine'''
new_tail = '''                    }
                }
            }
        }
    }
}

private data class MenuItemLine'''
if old_tail not in t:
    raise SystemExit('No se encontró el cierre del acordeón semanal')
t = t.replace(old_tail, new_tail, 1)

p.write_text(t)
print('Tarjetas semanales separadas 4 dp')
