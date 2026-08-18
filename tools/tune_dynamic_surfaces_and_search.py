from pathlib import Path

# Tune dynamic light surfaces very slightly and keep search body aligned with cards.
p = Path('app/src/main/java/es/david/rumbo/ui/Theme.kt')
s = p.read_text()
if 'import androidx.compose.ui.graphics.lerp\n' not in s:
    s = s.replace('import androidx.compose.ui.graphics.Color\n', 'import androidx.compose.ui.graphics.Color\nimport androidx.compose.ui.graphics.lerp\n', 1)
old = '''private fun ColorScheme.deeperLightSurfaces(): ColorScheme {
    val sourceContainer = surfaceContainer
    val sourceHigh = surfaceContainerHigh
    val sourceHighest = surfaceContainerHighest
    return copy(
        // Keep Android's dynamic hue/chroma. The page background stays on the
        // same tone that already matches the system wallpaper picker.
        background = sourceContainer,
        surface = surfaceContainerLow,
        surfaceVariant = sourceContainer,
        surfaceContainerLowest = surfaceContainerLowest,
        surfaceContainerLow = surfaceContainerLow,
        surfaceContainer = sourceContainer,
        surfaceContainerHigh = sourceHigh,
        // Filled Card uses the highest container token. Move it one dynamic
        // step toward the page instead of leaving it near white.
        surfaceContainerHighest = sourceHigh
    )
}
'''
new = '''private fun ColorScheme.deeperLightSurfaces(): ColorScheme {
    val sourceLow = surfaceContainerLow
    val sourceContainer = surfaceContainer
    val sourceHigh = surfaceContainerHigh
    val sourceHighest = surfaceContainerHighest
    val pageTone = lerp(sourceContainer, sourceLow, 0.28f)
    val cardTone = lerp(sourceHigh, sourceHighest, 0.24f)
    return copy(
        // Preserve Android's dynamic hue/chroma. Move the page only slightly
        // lighter than before and filled cards only slightly darker.
        background = pageTone,
        surface = cardTone,
        surfaceVariant = pageTone,
        surfaceContainerLowest = surfaceContainerLowest,
        surfaceContainerLow = sourceLow,
        surfaceContainer = sourceContainer,
        surfaceContainerHigh = sourceHigh,
        surfaceContainerHighest = cardTone
    )
}
'''
if old not in s:
    raise SystemExit('Theme block not found')
s = s.replace(old, new, 1)
p.write_text(s)

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()
marker = '    if (catalogSearchOverlayOpen) {'
start = s.index(marker)
needle = '''        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background
        ) {
'''
pos = s.index(needle, start)
s = s[:pos] + s[pos:].replace(needle, '''        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.surfaceContainerHighest
        ) {
''', 1)
p.write_text(s)
print('Adjusted dynamic page/card tones and search body surface')
