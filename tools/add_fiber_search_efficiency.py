from pathlib import Path
p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()
old = '''private fun nutritionalRoleEfficiency(food: Food, role: String): Double? {
    val calories = food.calories?.takeIf { it > 0.0 } ?: return null
    val grams = when (role) {
        "PRIMARY_PROTEIN", "COMPLEMENTARY_PROTEIN" -> food.proteinGrams
        "PRIMARY_CARBOHYDRATE", "COMPLEMENTARY_CARBOHYDRATE" -> food.carbohydrateGrams
        "CONCENTRATED_FAT", "COMPLEMENTARY_FAT" -> food.fatGrams
        else -> null
    } ?: return null
    return grams * 100.0 / calories
}
'''
new = '''private fun nutritionalRoleEfficiency(food: Food, role: String): Double? {
    val calories = food.calories?.takeIf { it > 0.0 } ?: return null
    val grams = when (role) {
        "PRIMARY_PROTEIN", "COMPLEMENTARY_PROTEIN" -> food.proteinGrams
        "PRIMARY_CARBOHYDRATE", "COMPLEMENTARY_CARBOHYDRATE" -> food.carbohydrateGrams
        "CONCENTRATED_FAT", "COMPLEMENTARY_FAT" -> food.fatGrams
        "VEGETABLE", "FRUIT" -> food.fiberGrams
        else -> null
    } ?: return null
    return grams * 100.0 / calories
}
'''
if s.count(old) != 1:
    raise SystemExit(f'expected one nutritionalRoleEfficiency block, found {s.count(old)}')
p.write_text(s.replace(old, new, 1))
print('Fruit and vegetable search now sort by fibre per 100 kcal')
