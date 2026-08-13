from pathlib import Path

path = Path("app/src/main/java/es/david/rumbo/ui/App.kt")
text = path.read_text()


def replace_between(source: str, start: str, end: str, replacement: str) -> str:
    i = source.index(start)
    j = source.index(end, i)
    return source[:i] + replacement + source[j:]

# Formato nutricional compacto y rejilla desplazada a la derecha para dejar más sitio al nombre.
start = "    fun nutrientAmount(valuePer100: Double?, grams: Double): String =\n"
end = "    @Composable\n    fun FoodNutritionLine(food: Food, grams: Double) {\n"
replacement = '''    fun compactNutritionNumber(value: Double): String =
        if (abs(value) < 10.0) formatOneDecimal(value) else value.roundToInt().toString()

    fun nutrientAmount(valuePer100: Double?, grams: Double): String =
        valuePer100?.let { compactNutritionNumber(it * grams / 100.0) } ?: "—"

    @Composable
    fun CompactNutritionGridValues(
        calories: Double?,
        protein: Double?,
        carbohydrates: Double?,
        fat: Double?,
        modifier: Modifier = Modifier
    ) {
        val color = MaterialTheme.colorScheme.onSurfaceVariant

        @Composable
        fun LeftMetric(icon: ImageVector, label: String, value: String, modifier: Modifier) {
            Row(
                modifier,
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Start
            ) {
                Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(17.dp))
                Spacer(Modifier.width(3.dp))
                Text(value, style = MaterialTheme.typography.bodySmall, color = color, maxLines = 1)
            }
        }

        @Composable
        fun RightMetric(icon: ImageVector, label: String, value: String, modifier: Modifier) {
            Row(
                modifier,
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.End
            ) {
                Text(value, style = MaterialTheme.typography.bodySmall, color = color, maxLines = 1)
                Spacer(Modifier.width(3.dp))
                Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(17.dp))
            }
        }

        fun display(value: Double?): String = value?.let(::compactNutritionNumber) ?: "—"

        Column(modifier, verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Row(Modifier.fillMaxWidth()) {
                LeftMetric(
                    Icons.Default.LocalFireDepartment,
                    "Calorías",
                    display(calories),
                    Modifier.weight(1f)
                )
                RightMetric(
                    foodCategoryIcon(FoodCategory.PROTEIN),
                    "Proteínas",
                    display(protein),
                    Modifier.weight(1f)
                )
            }
            Row(Modifier.fillMaxWidth()) {
                LeftMetric(
                    foodCategoryIcon(FoodCategory.CARBOHYDRATE),
                    "Carbohidratos",
                    display(carbohydrates),
                    Modifier.weight(1f)
                )
                RightMetric(
                    foodCategoryIcon(FoodCategory.FAT),
                    "Grasas",
                    display(fat),
                    Modifier.weight(1f)
                )
            }
        }
    }

    @Composable
    fun CompactNutritionGrid(food: Food, grams: Double, modifier: Modifier = Modifier) {
        val factor = grams / 100.0
        CompactNutritionGridValues(
            calories = food.calories?.times(factor),
            protein = food.proteinGrams?.times(factor),
            carbohydrates = food.carbohydrateGrams?.times(factor),
            fat = food.fatGrams?.times(factor),
            modifier = modifier
        )
    }

'''
text = replace_between(text, start, end, replacement)

# Más aire en los alimentos; el plato usa la misma cabecera y reserva la subtarjeta a sus ingredientes.
start = "    @Composable\n    fun FoodNutritionLine(food: Food, grams: Double) {\n"
end = "    @Composable\n    fun AbsoluteNutritionSummary(assessment: PlanNutritionAssessment?) {\n"
replacement = '''    @Composable
    fun FoodNutritionLine(food: Food, grams: Double) {
        Row(
            Modifier.fillMaxWidth().clickable { onOpenFood(food.id) }.padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(
                    food.name,
                    style = MaterialTheme.typography.bodyLarge,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    foodAmountLabel(food, grams),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1
                )
            }
            CompactNutritionGrid(food, grams, Modifier.width(132.dp))
        }
    }

    fun dishAmountLabelForHome(dish: Dish, grams: Double): String {
        val unitAmount = dish.unitAmount?.takeIf { it > 0.0 }
        val singular = dish.unitName?.trim()?.takeIf { it.isNotEmpty() }
        if (unitAmount != null && singular != null) {
            val count = grams / unitAmount
            val countLabel = if (abs(count - count.roundToInt()) < 0.01) {
                count.roundToInt().toString()
            } else compactNutritionNumber(count)
            val name = if (abs(count - 1.0) < 0.01) singular
            else dish.unitPlural?.trim()?.takeIf { it.isNotEmpty() } ?: singular
            return "$countLabel $name · ${formatDecimal(grams)} g"
        }
        return "${formatDecimal(grams)} g"
    }

    fun foodCategoryPriority(category: FoodCategory?): Int = when (category) {
        FoodCategory.PROTEIN -> 0
        FoodCategory.CARBOHYDRATE -> 1
        FoodCategory.FAT -> 2
        FoodCategory.VEGETABLE -> 3
        FoodCategory.FRUIT -> 4
        FoodCategory.OTHER, null -> 5
    }

    @Composable
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
                        style = MaterialTheme.typography.bodyLarge,
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
                    modifier = Modifier.width(132.dp)
                )
            }
            Card(
                Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)
            ) {
                Column(
                    Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp),
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
    }

'''
text = replace_between(text, start, end, replacement)

# Totales diarios sin decimales innecesarios.
old = '''                actual?.calories?.let { "${formatDecimal(it)} kcal" } ?: "—",
'''
new = '''                actual?.calories?.let { "${compactNutritionNumber(it)} kcal" } ?: "—",
'''
assert old in text
text = text.replace(old, new, 1)
for field in ("proteinGrams", "carbohydrateGrams", "fatGrams"):
    old = f'''                actual?.{field}?.let {{ "${{formatDecimal(it)}} g" }} ?: "—",\n'''
    new = f'''                actual?.{field}?.let {{ "${{compactNutritionNumber(it)}} g" }} ?: "—",\n'''
    assert old in text, field
    text = text.replace(old, new, 1)

# Resumen semanal propio: primera métrica anclada al borde izquierdo.
summary_marker = "    @Composable\n    fun SummarySection(expanded: Boolean) {\n"
assert summary_marker in text
percent_summary = '''    @Composable
    fun WeeklyPercentSummary(assessment: PlanNutritionAssessment) {
        val color = MaterialTheme.colorScheme.onSurfaceVariant
        fun percentage(actual: Double, target: Double): String =
            if (target <= 0.0) "—" else "${(actual / target * 100.0).roundToInt()} %"

        @Composable
        fun Metric(
            icon: ImageVector,
            label: String,
            value: String,
            arrangement: Arrangement.Horizontal,
            modifier: Modifier
        ) {
            Row(
                modifier,
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = arrangement
            ) {
                Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(4.dp))
                Text(
                    value,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = color,
                    maxLines = 1
                )
            }
        }

        Row(Modifier.fillMaxWidth()) {
            Metric(
                Icons.Default.LocalFireDepartment,
                "Calorías",
                percentage(assessment.actual.calories, assessment.target.calories),
                Arrangement.Start,
                Modifier.weight(1f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.PROTEIN),
                "Proteínas",
                percentage(assessment.actual.proteinGrams, assessment.target.proteinGrams),
                Arrangement.Center,
                Modifier.weight(1f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.CARBOHYDRATE),
                "Carbohidratos",
                percentage(assessment.actual.carbohydrateGrams, assessment.target.carbohydrateGrams),
                Arrangement.Center,
                Modifier.weight(1f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.FAT),
                "Grasas",
                percentage(assessment.actual.fatGrams, assessment.target.fatGrams),
                Arrangement.End,
                Modifier.weight(1f)
            )
        }
    }

'''
text = text.replace(summary_marker, percent_summary + summary_marker, 1)
old = '''                    TodayNutritionSummary(it)
'''
new = '''                    WeeklyPercentSummary(it)
'''
assert old in text
text = text.replace(old, new, 1)

# En cada comida: platos primero; después alimentos por proteína, carbohidrato, grasa, verdura, fruta y otros.
old = '''                            meal.items.forEach foodLoop@ { planned ->
                                val food = foodsById[planned.foodId] ?: return@foodLoop
                                FoodNutritionLine(food, meal.resolvedGrams(planned, day))
                            }
                            meal.dishes.forEach dishLoop@ { planned ->
                                val dish = dishesById[planned.dishId] ?: return@dishLoop
                                DishNutritionCard(dish, meal.resolvedGrams(planned, day))
                            }
'''
new = '''                            meal.dishes.forEach dishLoop@ { planned ->
                                val dish = dishesById[planned.dishId] ?: return@dishLoop
                                DishNutritionCard(dish, meal.resolvedGrams(planned, day))
                            }
                            meal.items
                                .sortedWith(
                                    compareBy<PlannedFood> { foodCategoryPriority(foodsById[it.foodId]?.category) }
                                        .thenBy { foodsById[it.foodId]?.name.orEmpty().lowercase() }
                                )
                                .forEach foodLoop@ { planned ->
                                    val food = foodsById[planned.foodId] ?: return@foodLoop
                                    FoodNutritionLine(food, meal.resolvedGrams(planned, day))
                                }
'''
assert old in text
text = text.replace(old, new, 1)

path.write_text(text)
print("Pulido nutricional y orden de alimentos aplicado")
