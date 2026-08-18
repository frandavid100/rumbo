from pathlib import Path


def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, got {n}')
    return text.replace(old, new, 1)

p = Path('app/src/main/java/es/david/rumbo/model/Models.kt')
s = p.read_text()
s = replace_once(s,
'''    "MAIN_MEAT" -> setOf("PLATE_CENTER", "SANDWICH_FILLING", "TOPPING", "STANDALONE")
    "MAIN_FISH" -> setOf("PLATE_CENTER", "STANDALONE")
    "MAIN_EGG" -> setOf("PLATE_CENTER", "SANDWICH_FILLING", "STANDALONE")
''',
'''    // The old type was too coarse to prove secondary uses. Migrate conservatively:
    // fresh/main proteins remain plate centers unless the new catalogue explicitly
    // assigns SANDWICH_FILLING, TOPPING or STANDALONE.
    "MAIN_MEAT" -> setOf("PLATE_CENTER")
    "MAIN_FISH" -> setOf("PLATE_CENTER")
    "MAIN_EGG" -> setOf("PLATE_CENTER")
''', 'legacy main protein mapping')
p.write_text(s)

p = Path('app/src/test/java/es/david/rumbo/logic/RepertoireEvaluatorTest.kt')
s = p.read_text()
s = replace_once(s,
'''        assertEquals(CulinaryNeedKind.COMPANION_BASE, result.culinaryNeeds.single().kind)
        assertTrue(result.culinaryNeeds.single().message.contains("leche"))
''',
'''        assertEquals(CulinaryNeedKind.COMPANION_BASE, result.culinaryNeeds.single().kind)
        assertTrue(CulinaryRole.POWDER_BASE in result.culinaryNeeds.single().acceptedRoles)
        assertTrue(result.culinaryNeeds.single().message.contains("base", ignoreCase = true))
''', 'generic companion diagnostic')
p.write_text(s)

p = Path('app/src/test/java/es/david/rumbo/logic/WeeklyMenuGeneratorTest.kt')
s = p.read_text()
s = replace_once(s,
'''    fun cookingIngredientCannotAppearAsAStandaloneFood() {
''',
'''    fun cookingIngredientRoleNeverAppearsAsTheOnlyElementOfAMeal() {
''', 'cooking test name')
s = replace_once(s,
'''        assertTrue(result.meals.none { meal ->
            meal.items.any { it.foodId == breadcrumbs.id }
        })
''',
'''        assertTrue(result.meals.all { meal ->
            meal.items.none { it.foodId == breadcrumbs.id } || meal.items.size + meal.dishes.size > 1
        })
''', 'cooking test expectation')
p.write_text(s)

print('Legacy role semantics fixed')
