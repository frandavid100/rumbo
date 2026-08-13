from pathlib import Path

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
t = p.read_text()

# 1. Situación y objetivo: dos filas, nombres explícitos e iconos en los extremos.
old_metrics = '''                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    NutritionGoalMetric(
                        "Calorías", "${recommendation.calories} kcal",
                        Icons.Default.LocalFireDepartment, MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    NutritionGoalMetric(
                        "Proteína", "${recommendation.proteinGrams} g",
                        foodCategoryIcon(FoodCategory.PROTEIN), foodCategoryColor(FoodCategory.PROTEIN)
                    )
                    NutritionGoalMetric(
                        "Hidratos", "${recommendation.carbohydrateGrams} g",
                        foodCategoryIcon(FoodCategory.CARBOHYDRATE), foodCategoryColor(FoodCategory.CARBOHYDRATE)
                    )
                    NutritionGoalMetric(
                        "Grasa", "${recommendation.fatGrams} g",
                        foodCategoryIcon(FoodCategory.FAT), foodCategoryColor(FoodCategory.FAT)
                    )
                }
'''
new_metrics = '''                Column(
                    Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Row(Modifier.fillMaxWidth()) {
                        HomeNutritionLegendMetric(
                            label = "Calorías",
                            value = "${recommendation.calories} kcal",
                            icon = Icons.Default.LocalFireDepartment,
                            modifier = Modifier.weight(1f)
                        )
                        HomeNutritionLegendMetric(
                            label = "Proteínas",
                            value = "${recommendation.proteinGrams} g",
                            icon = foodCategoryIcon(FoodCategory.PROTEIN),
                            reverse = true,
                            modifier = Modifier.weight(1f)
                        )
                    }
                    Row(Modifier.fillMaxWidth()) {
                        HomeNutritionLegendMetric(
                            label = "Carbohidratos",
                            value = "${recommendation.carbohydrateGrams} g",
                            icon = foodCategoryIcon(FoodCategory.CARBOHYDRATE),
                            modifier = Modifier.weight(1f)
                        )
                        HomeNutritionLegendMetric(
                            label = "Grasas",
                            value = "${recommendation.fatGrams} g",
                            icon = foodCategoryIcon(FoodCategory.FAT),
                            reverse = true,
                            modifier = Modifier.weight(1f)
                        )
                    }
                }
'''
if old_metrics not in t:
    raise SystemExit('No se encontró la tira nutricional de Situación y objetivo')
t = t.replace(old_metrics, new_metrics, 1)

legend_marker = '@Composable\nprivate fun NutritionGoalMetric('
legend_helper = '''@Composable
private fun HomeNutritionLegendMetric(
    label: String,
    value: String,
    icon: ImageVector,
    reverse: Boolean = false,
    modifier: Modifier = Modifier
) {
    val color = MaterialTheme.colorScheme.onSurfaceVariant
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = if (reverse) Arrangement.End else Arrangement.Start
    ) {
        if (!reverse) {
            Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(6.dp))
        }
        Text(
            if (reverse) "$value  $label" else "$label  $value",
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            color = color,
            maxLines = 1
        )
        if (reverse) {
            Spacer(Modifier.width(6.dp))
            Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(20.dp))
        }
    }
}

'''
if legend_marker not in t:
    raise SystemExit('No se encontró NutritionGoalMetric')
t = t.replace(legend_marker, legend_helper + legend_marker, 1)

# 2. Cambios localizados dentro del acordeón semanal. No sustituimos el bloque completo:
#    así conservamos todas las demás pantallas y helpers del archivo.
weekly_start = t.index('@Composable\nprivate fun WeeklyHomeMenuSection(')
summary_start = t.index('    @Composable\n    fun SummarySection(', weekly_start)
day_start = t.index('    @Composable\n    fun DaySection(', summary_start)
layout_start = t.index('    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {', day_start)

new_summary = r'''    fun nutrientAmount(valuePer100: Double?, grams: Double): String =
        valuePer100?.let { formatDecimal(it * grams / 100.0) } ?: "—"

    @Composable
    fun CompactNutritionGrid(food: Food, grams: Double, modifier: Modifier = Modifier) {
        val color = MaterialTheme.colorScheme.onSurfaceVariant

        @Composable
        fun LeftMetric(icon: ImageVector, label: String, value: String, modifier: Modifier) {
            Row(
                modifier,
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Start
            ) {
                Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(3.dp))
                Text(value, style = MaterialTheme.typography.labelMedium, color = color, maxLines = 1)
            }
        }

        @Composable
        fun RightMetric(icon: ImageVector, label: String, value: String, modifier: Modifier) {
            Row(
                modifier,
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.End
            ) {
                Text(value, style = MaterialTheme.typography.labelMedium, color = color, maxLines = 1)
                Spacer(Modifier.width(3.dp))
                Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(16.dp))
            }
        }

        Column(modifier, verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Row(Modifier.fillMaxWidth()) {
                LeftMetric(
                    Icons.Default.LocalFireDepartment,
                    "Calorías",
                    nutrientAmount(food.calories, grams),
                    Modifier.weight(1f)
                )
                RightMetric(
                    foodCategoryIcon(FoodCategory.PROTEIN),
                    "Proteínas",
                    nutrientAmount(food.proteinGrams, grams),
                    Modifier.weight(1f)
                )
            }
            Row(Modifier.fillMaxWidth()) {
                LeftMetric(
                    foodCategoryIcon(FoodCategory.CARBOHYDRATE),
                    "Carbohidratos",
                    nutrientAmount(food.carbohydrateGrams, grams),
                    Modifier.weight(1f)
                )
                RightMetric(
                    foodCategoryIcon(FoodCategory.FAT),
                    "Grasas",
                    nutrientAmount(food.fatGrams, grams),
                    Modifier.weight(1f)
                )
            }
        }
    }

    @Composable
    fun FoodNutritionLine(food: Food, grams: Double) {
        Row(
            Modifier.fillMaxWidth().clickable { onOpenFood(food.id) }.padding(vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    food.name,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    foodAmountLabel(food, grams),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1
                )
            }
            CompactNutritionGrid(food, grams, Modifier.width(156.dp))
        }
    }

    @Composable
    fun DishNutritionCard(dish: Dish, grams: Double) {
        val totalWeight = dish.totalWeightGrams().takeIf { it > 0.0 } ?: 1.0
        Card(
            Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)
        ) {
            Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row(
                    Modifier.fillMaxWidth().clickable { onOpenDish(dish.id) },
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        dish.name,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.weight(1f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "${formatDecimal(grams)} g",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                dish.ingredients.forEach ingredientLoop@ { ingredient ->
                    val food = foodsById[ingredient.foodId] ?: return@ingredientLoop
                    val ingredientGrams = ingredient.grams * grams / totalWeight
                    FoodNutritionLine(food, ingredientGrams)
                }
            }
        }
    }

    @Composable
    fun AbsoluteNutritionSummary(assessment: PlanNutritionAssessment?) {
        val color = MaterialTheme.colorScheme.onSurfaceVariant
        val actual = assessment?.actual

        @Composable
        fun Metric(icon: ImageVector, label: String, text: String, modifier: Modifier) {
            Row(
                modifier,
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Center
            ) {
                Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(4.dp))
                Text(
                    text,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = color,
                    maxLines = 1
                )
            }
        }

        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
            Metric(
                Icons.Default.LocalFireDepartment,
                "Calorías",
                actual?.calories?.let { "${formatDecimal(it)} kcal" } ?: "—",
                Modifier.weight(1.2f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.PROTEIN),
                "Proteínas",
                actual?.proteinGrams?.let { "${formatDecimal(it)} g" } ?: "—",
                Modifier.weight(1f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.CARBOHYDRATE),
                "Carbohidratos",
                actual?.carbohydrateGrams?.let { "${formatDecimal(it)} g" } ?: "—",
                Modifier.weight(1f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.FAT),
                "Grasas",
                actual?.fatGrams?.let { "${formatDecimal(it)} g" } ?: "—",
                Modifier.weight(1f)
            )
        }
    }

    @Composable
    fun SummarySection(expanded: Boolean) {
        Column(Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "Valoración nutricional",
                subtitle = null,
                expanded = expanded,
                onClick = { toggleSection(summaryKey) }
            )
            weeklyAssessment?.let {
                Box(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 14.dp)) {
                    TodayNutritionSummary(it)
                }
            }
            AnimatedVisibility(
                visible = expanded,
                enter = expandVertically(expandFrom = Alignment.Top) + fadeIn(),
                exit = shrinkVertically(shrinkTowards = Alignment.Top) + fadeOut()
            ) {
                Column(
                    Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text(
                        weeklyAssessmentText(weeklyAssessment),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        OutlinedButton(
                            onClick = { rebuildSheet = true },
                            modifier = Modifier.weight(1f)
                        ) { Text("Rehacer menú") }
                        FilledTonalButton(
                            onClick = onOpenNextWeek,
                            modifier = Modifier.weight(1f)
                        ) { Text("Semana que viene") }
                    }
                }
            }
        }
    }

'''
t = t[:summary_start] + new_summary + t[day_start:]

# Recalcular índices después de sustituir SummarySection.
weekly_start = t.index('@Composable\nprivate fun WeeklyHomeMenuSection(')
day_start = t.index('    @Composable\n    fun DaySection(', weekly_start)
layout_start = t.index('    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {', day_start)

new_day = r'''    @Composable
    fun DaySection(day: WeekDay, expanded: Boolean) {
        val dayMeals = meals.filter { day in it.days }.associateBy { it.type }
        val assessment = recommendation?.let {
            MealPlanEvaluator.assessDay(day, meals, foodsById, dishesById, it)
        }

        Column(Modifier.fillMaxWidth()) {
            SectionHeader(
                title = day.label,
                subtitle = null,
                expanded = expanded,
                onClick = { toggleSection(day.name) }
            )
            Box(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 14.dp)) {
                AbsoluteNutritionSummary(assessment)
            }
            AnimatedVisibility(
                visible = expanded,
                enter = expandVertically(expandFrom = Alignment.Top) + fadeIn(),
                exit = shrinkVertically(shrinkTowards = Alignment.Top) + fadeOut()
            ) {
                Column(
                    Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    if (dayMeals.isEmpty()) {
                        Text("No hay comidas planificadas.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    val visibleTypes = MealType.entries.filter { dayMeals[it] != null }
                    visibleTypes.forEachIndexed { index, type ->
                        val meal = dayMeals[type] ?: return@forEachIndexed
                        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(
                                type.label,
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.clickable { onOpenMeal(meal.id) }
                            )
                            meal.items.forEach foodLoop@ { planned ->
                                val food = foodsById[planned.foodId] ?: return@foodLoop
                                FoodNutritionLine(food, meal.resolvedGrams(planned, day))
                            }
                            meal.dishes.forEach dishLoop@ { planned ->
                                val dish = dishesById[planned.dishId] ?: return@dishLoop
                                DishNutritionCard(dish, meal.resolvedGrams(planned, day))
                            }
                        }
                        if (index < visibleTypes.lastIndex) {
                            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                        }
                    }
                }
            }
        }
    }

'''
t = t[:day_start] + new_day + t[layout_start:]

p.write_text(t)
print('Corrección localizada de Inicio aplicada')
