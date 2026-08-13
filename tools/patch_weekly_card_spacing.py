from pathlib import Path

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
t = p.read_text()
start = t.index('@Composable\nprivate fun WeeklyHomeMenuSection(')
end = t.index('\nprivate data class MenuItemLine', start)
section = t[start:end]
print(section[-7000:])
raise SystemExit('MOSTRADO')
