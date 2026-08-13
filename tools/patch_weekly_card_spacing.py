from pathlib import Path
import re

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
t = p.read_text()
start = t.index('@Composable\nprivate fun WeeklyHomeMenuSection(')
end = t.index('\nprivate data class MenuItemLine', start)
section = t[start:end]

pattern = re.compile(r'''        Card\(\s*\n            Modifier\.fillMaxWidth\(\),\s*\n            colors = CardDefaults\.cardColors\(containerColor = MaterialTheme\.colorScheme\.surfaceContainer\)\s*\n        \) \{\s*\n            Column\(Modifier\.fillMaxWidth\(\)\) \{\s*\n                entries\.forEachIndexed \{ index, entry ->\s*\n                    if \(index > 0\) HorizontalDivider\(color = MaterialTheme\.colorScheme\.outlineVariant\)\s*\n                    val isExpanded = expandedSection == entry\.key\s*\n                    Column\(\s*\n                        Modifier\.fillMaxWidth\(\)\s*\n                    \) \{''')

replacement = '''        Column(\n            Modifier.fillMaxWidth(),\n            verticalArrangement = Arrangement.spacedBy(4.dp)\n        ) {\n            entries.forEach { entry ->\n                val isExpanded = expandedSection == entry.key\n                Card(\n                    Modifier.fillMaxWidth(),\n                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)\n                ) {\n                    Column(Modifier.fillMaxWidth()) {'''

section2, count = pattern.subn(replacement, section, count=1)
if count != 1:
    raise SystemExit('No se encontró la estructura actual del acordeón semanal')

t = t[:start] + section2 + t[end:]
p.write_text(t)
print('Tarjetas semanales separadas 4 dp')
