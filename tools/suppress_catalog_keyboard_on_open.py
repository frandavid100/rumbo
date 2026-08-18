from pathlib import Path
p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()
old = 'var catalogOverlaySuppressKeyboard by remember { mutableStateOf(false) }'
new = 'var catalogOverlaySuppressKeyboard by remember { mutableStateOf(true) }'
if s.count(old) != 1:
    raise SystemExit(f'expected one overlay keyboard state, found {s.count(old)}')
p.write_text(s.replace(old, new, 1))
print('Catalog overlay now opens without keyboard focus')
