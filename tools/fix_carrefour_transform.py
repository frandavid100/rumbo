from pathlib import Path

p = Path('tools/apply_carrefour_role_filters_ui.py')
text = p.read_text()
old = '''    if count != 1:\n        raise SystemExit(f"Expected one regex match in {path}, got {count}: {pattern[:100]}")\n    p.write_text(updated)\n'''
new = '''    if count != 1 and "val entries = remember" in pattern and path.endswith("App.kt"):\n        fallback = r''' + "'''" + r'''    val entries = remember\(\n        foods, dishes, normalizedQuery, filter, categoryFilter,\n        culinaryTypeFilter, mode, repertoireFoodIds\n    \) \{.*?\n    \}\n(?=\n    BackHandler\(enabled = searchExpanded\))''' + "'''" + '''\n        updated, count = re.subn(fallback, replacement, text, count=1, flags=re.S)\n    if count != 1:\n        raise SystemExit(f"Expected one regex match in {path}, got {count}: {pattern[:100]}")\n    p.write_text(updated)\n'''
if old not in text:
    raise SystemExit('regex_once marker missing')
p.write_text(text.replace(old, new, 1))
