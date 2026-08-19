from pathlib import Path
p=Path('app/src/main/java/es/david/rumbo/logic/CulinarySatisfactionEvaluator.kt')
t=p.read_text()
old='''    private val preferAnyOf: Map<CulinaryRole, Set<CulinaryRole>> = mapOf(\n        CulinaryRole.PLATE_CENTER to setOf(CulinaryRole.PLATE_BASE, CulinaryRole.SIDE),\n        CulinaryRole.PLATE_BASE to setOf(CulinaryRole.PLATE_CENTER, CulinaryRole.SIDE),\n        CulinaryRole.SIDE to setOf(CulinaryRole.PLATE_CENTER, CulinaryRole.PLATE_BASE),\n        CulinaryRole.SANDWICH_BASE to setOf(CulinaryRole.SANDWICH_FILLING, CulinaryRole.SPREAD),\n        CulinaryRole.CEREAL_BASE to setOf(CulinaryRole.CEREAL_MIX_IN),\n        CulinaryRole.POWDER_BASE to setOf(CulinaryRole.POWDER_MIX_IN),\n        CulinaryRole.COOKING_MEDIUM to setOf(\n            CulinaryRole.PLATE_CENTER, CulinaryRole.PLATE_BASE, CulinaryRole.SIDE\n        )\n    )\n\n'''
if t.count(old)!=1: raise SystemExit(f'Bloque preferAnyOf inesperado: {t.count(old)}')
t=t.replace(old,'',1)
old2='''        val present = assignments.mapTo(mutableSetOf()) { it.role }\n        return assignments.mapNotNull { assignment ->\n            val targets = preferAnyOf[assignment.role] ?: return@mapNotNull null\n            (assignment to targets).takeIf { targets.none(present::contains) }\n        }\n'''
new2='''        val present = assignments.mapTo(mutableSetOf()) { it.role }\n        return assignments.mapNotNull { assignment ->\n            val targets = CulinarySoftPolicy.preferredCompanions(assignment.role)\n            (assignment to targets).takeIf { targets.isNotEmpty() && targets.none(present::contains) }\n        }\n'''
if t.count(old2)!=1: raise SystemExit(f'Bloque missingSoftRelations inesperado: {t.count(old2)}')
p.write_text(t.replace(old2,new2,1))
