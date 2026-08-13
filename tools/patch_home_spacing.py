from pathlib import Path

path = Path("app/src/main/java/es/david/rumbo/ui/App.kt")
text = path.read_text()


def replace_section(source: str, start_marker: str, end_marker: str, transform):
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    section = source[start:end]
    updated = transform(section)
    if updated == section:
        raise RuntimeError(f"No se modificó la sección {start_marker}")
    return source[:start] + updated + source[end:]


def compact_grid(section: str) -> str:
    updated = section.replace(
        "Text(value, style = MaterialTheme.typography.bodySmall, color = color, maxLines = 1)",
        "Text(value, style = MaterialTheme.typography.bodyMedium, color = color, maxLines = 1)"
    )
    if updated.count("Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {") != 0:
        raise RuntimeError("El grid ya parece parcheado")
    updated = updated.replace(
        "Row(Modifier.fillMaxWidth()) {",
        "Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {"
    )
    updated = updated.replace("Modifier.weight(1f)", "Modifier")
    return updated


text = replace_section(
    text,
    "    @Composable\n    fun CompactNutritionGridValues(",
    "    @Composable\n    fun CompactNutritionGrid(",
    compact_grid,
)


def food_line(section: str) -> str:
    updated = section.replace(
        "style = MaterialTheme.typography.bodyLarge,\n                    maxLines = 1,",
        "style = MaterialTheme.typography.bodyMedium,\n                    fontWeight = FontWeight.SemiBold,\n                    maxLines = 1,",
        1,
    )
    updated = updated.replace("Modifier.width(132.dp)", "Modifier.width(112.dp)", 1)
    return updated


text = replace_section(
    text,
    "    @Composable\n    fun FoodNutritionLine(",
    "    fun dishAmountLabelForHome(",
    food_line,
)


def dish_card(_: str) -> str:
    return '''    @Composable
    fun DishNutritionCard(dish: Dish, grams: Double) {
        val totalWeight = dish.totalWeightGrams().takeIf { it > 0.0 } ?: 1.0
        val totals = dish.nutritionForGrams(foodsById, grams)
        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                Modifier.fillMaxWidth().clickable { onOpenDish(dish.id) }.padding(vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        dish.name,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        dishAmountLabelForHome(dish, grams),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1
                    )
                }
                CompactNutritionGridValues(
                    calories = totals.calories,
                    protein = totals.proteinGrams,
                    carbohydrates = totals.carbohydrateGrams,
                    fat = totals.fatGrams,
                    modifier = Modifier.width(112.dp)
                )
            }
            Column(
                Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surfaceContainer, RoundedCornerShape(12.dp))
                    .padding(vertical = 6.dp),
                verticalArrangement = Arrangement.spacedBy(2.dp)
            ) {
                dish.ingredients
                    .sortedWith(
                        compareBy<DishIngredient> { foodCategoryPriority(foodsById[it.foodId]?.category) }
                            .thenBy { foodsById[it.foodId]?.name.orEmpty().lowercase() }
                    )
                    .forEach ingredientLoop@ { ingredient ->
                        val food = foodsById[ingredient.foodId] ?: return@ingredientLoop
                        val ingredientGrams = ingredient.grams * grams / totalWeight
                        FoodNutritionLine(food, ingredientGrams)
                    }
            }
        }
    }

'''


text = replace_section(
    text,
    "    @Composable\n    fun DishNutritionCard(",
    "    @Composable\n    fun AbsoluteNutritionSummary(",
    dish_card,
)


def daily_summary(section: str) -> str:
    old = "horizontalArrangement = Arrangement.Center"
    if section.count(old) != 1:
        raise RuntimeError(f"Se esperaba un único centrado en el resumen diario y hay {section.count(old)}")
    return section.replace(old, "horizontalArrangement = Arrangement.Start", 1)


text = replace_section(
    text,
    "    @Composable\n    fun AbsoluteNutritionSummary(",
    "    @Composable\n    fun WeeklyPercentSummary(",
    daily_summary,
)

path.write_text(text)
