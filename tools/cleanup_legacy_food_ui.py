from pathlib import Path

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()

start_marker = '@Composable\nprivate fun FoodsScreen('
dialog_marker = '@Composable\nprivate fun FoodFilterDialog('

if s.count(start_marker) != 1:
    raise SystemExit(f'FoodsScreen definitions: {s.count(start_marker)}')
if s.count(dialog_marker) != 1:
    raise SystemExit(f'FoodFilterDialog definitions: {s.count(dialog_marker)}')

# Remove the obsolete FoodsScreen up to (but not including) its private dialog.
start = s.index(start_marker)
dialog = s.index(dialog_marker, start)
s = s[:start] + s[dialog:]

# Remove the now-unreferenced FoodFilterDialog through the next top-level composable function.
start = s.index(dialog_marker)
next_marker = '\n@Composable\nprivate fun '
next_pos = s.find(next_marker, start + len(dialog_marker))
if next_pos == -1:
    raise SystemExit('Could not locate next top-level composable after FoodFilterDialog')
s = s[:start] + s[next_pos + 1:]

if 'private fun FoodsScreen(' in s or 'private fun FoodFilterDialog(' in s:
    raise SystemExit('Legacy food UI remains after cleanup')

p.write_text(s)
print('Removed obsolete FoodsScreen and FoodFilterDialog')
