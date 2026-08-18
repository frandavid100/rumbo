from pathlib import Path

# 1) Dynamic surface hierarchy: keep search bar token unchanged, cards/search body lighter than page.
p = Path('app/src/main/java/es/david/rumbo/ui/Theme.kt')
s = p.read_text()
old = '''    val pageTone = lerp(sourceContainer, sourceLow, 0.22f)\n    val cardTone = lerp(sourceLow, pageTone, 0.38f)\n    return copy(\n        // Preserve Android's dynamic hue/chroma. Move the page only slightly\n        // lighter than before and filled cards only slightly darker.\n        background = pageTone,\n        surface = cardTone,\n        surfaceVariant = pageTone,\n        surfaceContainerLowest = surfaceContainerLowest,\n        surfaceContainerLow = sourceLow,\n        surfaceContainer = sourceContainer,\n        surfaceContainerHigh = sourceHigh,\n        surfaceContainerHighest = cardTone\n    )\n'''
new = '''    val pageTone = lerp(sourceContainer, sourceLow, 0.22f)\n    val cardTone = lerp(sourceLow, surfaceContainerLowest, 0.28f)\n    return copy(\n        // Preserve Android's dynamic hue/chroma. Page is softly tinted; cards\n        // are visibly but gently lighter. Keep the highest token untouched so\n        // the search bar retains the system-derived tone it had before.\n        background = pageTone,\n        surface = cardTone,\n        surfaceVariant = pageTone,\n        surfaceContainerLowest = surfaceContainerLowest,\n        surfaceContainerLow = sourceLow,\n        surfaceContainer = sourceContainer,\n        surfaceContainerHigh = sourceHigh,\n        surfaceContainerHighest = sourceHighest\n    )\n'''
assert old in s, 'theme block not found'
s = s.replace(old, new, 1)
p.write_text(s)

# 2) Level 2 must never ask again for level-1 nutritional roles.
p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()
old = '''            if (!diagnostic.viable) {\n                val role = when (diagnostic.deficientNutrient) {\n                    NutrientKind.PROTEIN -> "PRIMARY_PROTEIN"\n                    NutrientKind.CARBOHYDRATES -> "PRIMARY_CARBOHYDRATE"\n                    NutrientKind.FAT -> "COMPLEMENTARY_FAT"\n                    else -> null\n                }\n                val label = role?.let(::nutritionalRoleLabel)?.lowercase()\n                val limitingLabel = when (diagnostic.limitingNutrient) {\n                    NutrientKind.PROTEIN -> "proteína"\n                    NutrientKind.CARBOHYDRATES -> "hidratos"\n                    NutrientKind.FAT -> "grasa"\n                    NutrientKind.CALORIES -> "calorías"\n                    null -> "nutrientes"\n                }\n                val direction = when {\n                    (diagnostic.limitingDifference ?: 0.0) > 0.0 -> "por encima"\n                    (diagnostic.limitingDifference ?: 0.0) < 0.0 -> "por debajo"\n                    else -> "fuera"\n                }\n                return 1 to RepertoireProgressTarget(\n                    message = if (role != null) {\n                        "Rumbo consigue colocar fruta, verdura y fibra suficientes, pero el mejor día encontrado deja $limitingLabel $direction del objetivo. El mayor margen de mejora está en añadir una opción eficiente de ${label ?: "otro nutriente"} para que el generador pueda redistribuir las cantidades."\n                    } else {\n                        "Rumbo consigue colocar fruta, verdura y fibra suficientes, pero el mejor día encontrado deja $limitingLabel $direction del objetivo. No necesitas añadir más de ese mismo tipo: Rumbo necesita encontrar una combinación que reduzca ese exceso."\n                    },\n                    buttonLabel = label?.let { "Añadir $it" },\n                    nutritionalRole = role\n                )\n            }\n'''
new = '''            if (!diagnostic.viable) {\n                val limitingLabel = when (diagnostic.limitingNutrient) {\n                    NutrientKind.PROTEIN -> "proteína"\n                    NutrientKind.CARBOHYDRATES -> "hidratos"\n                    NutrientKind.FAT -> "grasa"\n                    NutrientKind.CALORIES -> "calorías"\n                    null -> "los objetivos nutricionales"\n                }\n                val direction = when {\n                    (diagnostic.limitingDifference ?: 0.0) > 0.0 -> "por encima"\n                    (diagnostic.limitingDifference ?: 0.0) < 0.0 -> "por debajo"\n                    else -> "fuera"\n                }\n                return 1 to RepertoireProgressTarget(\n                    message = "Rumbo ya dispone de los alimentos necesarios para el nivel 2: consigue colocar fruta, verdura y fibra suficientes. El mejor intento deja $limitingLabel $direction del objetivo, así que el problema ahora es encontrar una combinación compatible con los alimentos que ya tienes; no necesitas volver a añadir alimentos de los requisitos del nivel 1."\n                )\n            }\n'''
assert old in s, 'level2 macro guidance block not found'
s = s.replace(old, new, 1)
p.write_text(s)

# 3) Deepen COMPLETE search only after the quick deterministic seeds would fail.
p = Path('app/src/main/java/es/david/rumbo/logic/CertifiedDayWitnessEvaluator.kt')
s = p.read_text()
old = '''        val seeds = listOf(11L, 37L, 89L, 131L, 197L, 251L, 313L, 401L, 509L, 607L, 701L, 809L)\n'''
new = '''        // Daily COMPLETE search is cheap enough to explore more deterministic\n        // paths than VIABLE. This avoids asking the user for foods from a lower\n        // level merely because a small heuristic sample missed the combination.\n        val seeds = listOf(\n            11L, 37L, 89L, 131L, 197L, 251L, 313L, 401L, 509L, 607L, 701L, 809L,\n            907L, 1009L, 1103L, 1201L, 1301L, 1409L, 1511L, 1601L, 1709L, 1801L,\n            1901L, 2003L, 2111L, 2203L, 2309L, 2411L, 2503L, 2609L, 2707L, 2801L\n        )\n'''
assert old in s, 'seed list not found'
s = s.replace(old, new, 1)
p.write_text(s)

print('Fixed level-2 non-regression guidance, deep search, and surface hierarchy')
