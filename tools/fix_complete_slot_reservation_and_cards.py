from pathlib import Path

# 1) Reserve COMPLETE slots for fruit/vegetable before generic macro filling.
p = Path('app/src/main/java/es/david/rumbo/logic/WeeklyMenuGenerator.kt')
s = p.read_text()
old = '''            if (candidates.isEmpty()) break
            if (chosen.isEmpty() && candidates.any { it.itemKind == PlannedItemKind.DISH }) {
                candidates = candidates.filter { it.itemKind == PlannedItemKind.DISH }
            }

            // Evaluate every adjustable item at its minimum. If even its
'''
new = '''            if (candidates.isEmpty()) break

            // COMPLETE is not just a scoring preference. While the day still
            // needs fruit/vegetable coverage, reserve a slot for a compatible
            // candidate that can satisfy the missing category. Otherwise the
            // generic macro composition may fill all positions first and make
            // COMPLETE impossible even when the repertoire has suitable foods.
            if (objective == MenuGenerationObjective.COMPLETE) {
                fun needsCategory(category: es.david.rumbo.model.FoodCategory): Boolean {
                    if (chosen.any { it.containsCategory(category, foodsById, dishesById) }) return false
                    val previousMeals = assigned.entries.count { (assignedSlot, assignedRules) ->
                        assignedSlot.day == slot.day && assignedRules.any {
                            it.containsCategory(category, foodsById, dishesById)
                        }
                    }
                    return previousMeals < 2
                }
                val pendingCategories = listOf(
                    es.david.rumbo.model.FoodCategory.FRUIT,
                    es.david.rumbo.model.FoodCategory.VEGETABLE
                ).filter(::needsCategory)
                val requiredCandidates = candidates.filter { candidate ->
                    pendingCategories.any { category ->
                        candidate.containsCategory(category, foodsById, dishesById)
                    }
                }
                if (requiredCandidates.isNotEmpty()) {
                    candidates = requiredCandidates
                } else if (chosen.isEmpty() && candidates.any { it.itemKind == PlannedItemKind.DISH }) {
                    candidates = candidates.filter { it.itemKind == PlannedItemKind.DISH }
                }
            } else if (chosen.isEmpty() && candidates.any { it.itemKind == PlannedItemKind.DISH }) {
                candidates = candidates.filter { it.itemKind == PlannedItemKind.DISH }
            }

            // Evaluate every adjustable item at its minimum. If even its
'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

# 2) Darken filled cards slightly without moving the now-good page background.
p = Path('app/src/main/java/es/david/rumbo/ui/Theme.kt')
s = p.read_text()
old = '''private fun ColorScheme.deeperLightSurfaces(): ColorScheme = copy(
    // Keep Android's dynamic hue/chroma, but give the hierarchy visible depth:
    // page background is a stronger tonal surface; cards remain one step lighter.
    background = surfaceContainer,
    surface = surfaceContainerLow,
    surfaceVariant = surfaceContainer,
    surfaceContainerLowest = surfaceContainerLowest,
    surfaceContainerLow = surfaceContainerLow,
    surfaceContainer = surfaceContainer,
    surfaceContainerHigh = surfaceContainerHigh,
    surfaceContainerHighest = surfaceContainerHighest
)
'''
new = '''private fun ColorScheme.deeperLightSurfaces(): ColorScheme {
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
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

print('Reserved COMPLETE produce slots and deepened dynamic cards')
