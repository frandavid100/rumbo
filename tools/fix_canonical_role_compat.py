from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)

p = Path('app/src/main/java/es/david/rumbo/logic/WeeklyMenuGenerator.kt')
s = p.read_text()
s = replace_once(s, '''    ): List<Set<CulinaryRole>> = rules.flatMap { rule ->
        when (rule.itemKind) {
            PlannedItemKind.FOOD -> listOf(foodsById[rule.itemId]?.let(CulinaryPolicy::roles).orEmpty())
            PlannedItemKind.DISH -> dishesById[rule.itemId]?.ingredients.orEmpty().map { ingredient ->
                foodsById[ingredient.foodId]?.let(CulinaryPolicy::roles).orEmpty()
            }
        }
    }
''', '''    ): List<Set<CulinaryRole>> = rules.flatMap { rule ->
        when (rule.itemKind) {
            PlannedItemKind.FOOD -> listOfNotNull(
                foodsById[rule.itemId]?.let(CulinaryPolicy::roles)?.takeIf { it.isNotEmpty() }
            )
            PlannedItemKind.DISH -> dishesById[rule.itemId]?.ingredients.orEmpty().mapNotNull { ingredient ->
                foodsById[ingredient.foodId]?.let(CulinaryPolicy::roles)?.takeIf { it.isNotEmpty() }
            }
        }
    }
''', 'roleChoices legacy compatibility')
s = replace_once(s, '''        val choices = roleChoices(rules, foodsById, dishesById)
        if (choices.any { it.isEmpty() }) return false
        // A partial composition may still be completed later; only reject cardinality
''', '''        val choices = roleChoices(rules, foodsById, dishesById)
        // A partial composition may still be completed later; only reject cardinality
''', 'exclusive role empty rejection')
p.write_text(s)

p = Path('app/src/main/java/es/david/rumbo/logic/FoodSuggestionEngine.kt')
s = p.read_text()
s = replace_once(s, '''        val nutrient = functionalNutrient(source)
        val sourceScore = nutrientScore(source, nutrient)
        return common.asSequence()
            .filter {
                it.food.id != source.id &&
                    CulinaryPolicy.roles(it.food).intersect(CulinaryPolicy.roles(source)).isNotEmpty() &&
                    nutrient in efficientNutrients(it.food) &&
''', '''        val nutrient = functionalNutrient(source)
        val sourceScore = nutrientScore(source, nutrient)
        val sourceCulinaryRoles = CulinaryPolicy.roles(source)
        return common.asSequence()
            .filter {
                val candidateCulinaryRoles = CulinaryPolicy.roles(it.food)
                val sameCulinaryFunction =
                    sourceCulinaryRoles.intersect(candidateCulinaryRoles).isNotEmpty() ||
                    (sourceCulinaryRoles.isEmpty() && candidateCulinaryRoles.isEmpty())
                it.food.id != source.id && sameCulinaryFunction &&
                    nutrient in efficientNutrients(it.food) &&
''', 'suggestion legacy role fallback')
p.write_text(s)

print('Canonical role compatibility fixes applied')
