from pathlib import Path
p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()
old1 = 'var catalogSearchSavedScrollIndex by rememberSaveable { mutableIntStateOf(0) }'
old2 = 'var catalogSearchSavedScrollOffset by rememberSaveable { mutableIntStateOf(0) }'
assert s.count(old1) == 1, s.count(old1)
assert s.count(old2) == 1, s.count(old2)
s = s.replace(old1, 'var catalogSearchSavedScrollIndex by rememberSaveable { mutableStateOf(0) }', 1)
s = s.replace(old2, 'var catalogSearchSavedScrollOffset by rememberSaveable { mutableStateOf(0) }', 1)
p.write_text(s)
print('Scroll state uses regular mutableStateOf for compatibility')
