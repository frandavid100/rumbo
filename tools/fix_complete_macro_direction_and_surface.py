from pathlib import Path

# Diagnostic: keep the direction of the macro mismatch instead of only its kind.
p = Path('app/src/main/java/es/david/rumbo/logic/CertifiedDayWitnessEvaluator.kt')
s = p.read_text()
s = s.replace(
'''        val viable: Boolean,\n        val limitingNutrient: NutrientKind? = null,\n        val availableFruitMeals: Int = 0,\n''',
'''        val viable: Boolean,\n        val limitingNutrient: NutrientKind? = null,\n        val limitingDifference: Double? = null,\n        val deficientNutrient: NutrientKind? = null,\n        val deficientDifference: Double? = null,\n        val availableFruitMeals: Int = 0,\n''', 1)

old = '''            val limiting = assessment.evaluations\n                .filter { it.fit == TargetFit.OUTSIDE }\n                .maxByOrNull { kotlin.math.abs(it.difference / it.target.coerceAtLeast(1.0)) }\n                ?.kind\n            val diagnostic = CompleteDayDiagnostic(\n                fruitMeals = fruitMeals,\n                vegetableMeals = vegetableMeals,\n                fiberGrams = assessment.actual.fiberGrams,\n                viable = true,\n                limitingNutrient = limiting,\n                availableFruitMeals = availableFruitMeals,\n'''
new = '''            val limitingEvaluation = assessment.evaluations\n                .filter { it.fit == TargetFit.OUTSIDE }\n                .maxByOrNull { kotlin.math.abs(it.difference / it.target.coerceAtLeast(1.0)) }\n            val deficientEvaluation = assessment.evaluations\n                .filter { it.kind != NutrientKind.CALORIES && it.difference < 0.0 }\n                .minByOrNull { it.difference / it.target.coerceAtLeast(1.0) }\n            val diagnostic = CompleteDayDiagnostic(\n                fruitMeals = fruitMeals,\n                vegetableMeals = vegetableMeals,\n                fiberGrams = assessment.actual.fiberGrams,\n                viable = true,\n                limitingNutrient = limitingEvaluation?.kind,\n                limitingDifference = limitingEvaluation?.difference,\n                deficientNutrient = deficientEvaluation?.kind,\n                deficientDifference = deficientEvaluation?.difference,\n                availableFruitMeals = availableFruitMeals,\n'''
assert old in s
s = s.replace(old, new, 1)

old = '''            val limiting = assessment.evaluations\n                .filter { it.fit == TargetFit.OUTSIDE }\n                .maxByOrNull { kotlin.math.abs(it.difference / it.target.coerceAtLeast(1.0)) }\n                ?.kind\n            val diagnostic = CompleteDayDiagnostic(\n                fruitMeals = fruitMeals,\n                vegetableMeals = vegetableMeals,\n                fiberGrams = assessment.actual.fiberGrams,\n                viable = viable,\n                limitingNutrient = limiting,\n                availableFruitMeals = availableFruitMeals,\n'''
new = '''            val limitingEvaluation = assessment.evaluations\n                .filter { it.fit == TargetFit.OUTSIDE }\n                .maxByOrNull { kotlin.math.abs(it.difference / it.target.coerceAtLeast(1.0)) }\n            val deficientEvaluation = assessment.evaluations\n                .filter { it.kind != NutrientKind.CALORIES && it.difference < 0.0 }\n                .minByOrNull { it.difference / it.target.coerceAtLeast(1.0) }\n            val diagnostic = CompleteDayDiagnostic(\n                fruitMeals = fruitMeals,\n                vegetableMeals = vegetableMeals,\n                fiberGrams = assessment.actual.fiberGrams,\n                viable = viable,\n                limitingNutrient = limitingEvaluation?.kind,\n                limitingDifference = limitingEvaluation?.difference,\n                deficientNutrient = deficientEvaluation?.kind,\n                deficientDifference = deficientEvaluation?.difference,\n                availableFruitMeals = availableFruitMeals,\n'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

# UI: recommend a role based on a deficit, never on an excess of that same macro.
p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()
old = '''            if (!diagnostic.viable) {\n                val role = when (diagnostic.limitingNutrient) {\n                    NutrientKind.PROTEIN -> "PRIMARY_PROTEIN"\n                    NutrientKind.CARBOHYDRATES -> "PRIMARY_CARBOHYDRATE"\n                    NutrientKind.FAT -> "COMPLEMENTARY_FAT"\n                    else -> null\n                }\n                val label = role?.let(::nutritionalRoleLabel)?.lowercase()\n                return 1 to RepertoireProgressTarget(\n                    message = "Rumbo consigue colocar fruta, verdura y fibra suficientes, pero ese día todavía queda fuera de los objetivos nutricionales. Añade otra opción eficiente para que pueda cuadrar ambas cosas a la vez.",\n                    buttonLabel = label?.let { "Añadir $it" } ?: "Añadir otro alimento",\n                    nutritionalRole = role\n                )\n            }\n'''
new = '''            if (!diagnostic.viable) {\n                val role = when (diagnostic.deficientNutrient) {\n                    NutrientKind.PROTEIN -> "PRIMARY_PROTEIN"\n                    NutrientKind.CARBOHYDRATES -> "PRIMARY_CARBOHYDRATE"\n                    NutrientKind.FAT -> "COMPLEMENTARY_FAT"\n                    else -> null\n                }\n                val label = role?.let(::nutritionalRoleLabel)?.lowercase()\n                val limitingLabel = when (diagnostic.limitingNutrient) {\n                    NutrientKind.PROTEIN -> "proteína"\n                    NutrientKind.CARBOHYDRATES -> "hidratos"\n                    NutrientKind.FAT -> "grasa"\n                    NutrientKind.CALORIES -> "calorías"\n                    null -> "nutrientes"\n                }\n                val direction = when {\n                    (diagnostic.limitingDifference ?: 0.0) > 0.0 -> "por encima"\n                    (diagnostic.limitingDifference ?: 0.0) < 0.0 -> "por debajo"\n                    else -> "fuera"\n                }\n                return 1 to RepertoireProgressTarget(\n                    message = if (role != null) {\n                        "Rumbo consigue colocar fruta, verdura y fibra suficientes, pero el mejor día encontrado deja $limitingLabel $direction del objetivo. El mayor margen de mejora está en añadir una opción eficiente de ${label ?: "otro nutriente"} para que el generador pueda redistribuir las cantidades."\n                    } else {\n                        "Rumbo consigue colocar fruta, verdura y fibra suficientes, pero el mejor día encontrado deja $limitingLabel $direction del objetivo. No necesitas añadir más de ese mismo tipo: Rumbo necesita encontrar una combinación que reduzca ese exceso."\n                    },\n                    buttonLabel = label?.let { "Añadir $it" },\n                    nutritionalRole = role\n                )\n            }\n'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

# Theme: cards/search body slightly lighter than page, not darker.
p = Path('app/src/main/java/es/david/rumbo/ui/Theme.kt')
s = p.read_text()
old = '''    val pageTone = lerp(sourceContainer, sourceLow, 0.28f)\n    val cardTone = lerp(sourceHigh, sourceHighest, 0.24f)\n'''
new = '''    val pageTone = lerp(sourceContainer, sourceLow, 0.22f)\n    val cardTone = lerp(sourceLow, pageTone, 0.38f)\n'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

print('Applied directional COMPLETE macro diagnosis and lighter cards')
