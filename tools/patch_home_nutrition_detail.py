from pathlib import Path

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
t = p.read_text()

# 1. La tarjeta de situación enseña explícitamente la leyenda de los cuatro nutrientes,
#    en dos filas y con los iconos en los extremos exteriores.
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
if 'private fun HomeNutritionLegendMetric(' not in t:
    t = t.replace(legend_marker, legend_helper + legend_marker, 1)

# 2. Rehacer el bloque semanal manteniendo el acordeón animado, pero mostrando
#    nutrición absoluta por día y detalle por alimento/ingrediente.
start = t.index('@Composable\nprivate fun WeeklyHomeMenuSection(')
end = t.index('@Composable\nprivate fun QuantityOptimizationPreviewDialog(', start)
new_weekly = r'''@Composable
private fun WeeklyHomeMenuSection(
    meals: List<PlannedMeal>,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    recommendation: es.david.rumbo.model.Recommendation?,
    onOpenNextWeek: () -> Unit,
    onRegenerateWeek: () -> String?,
    onOpenMeal: (Long) -> Unit,
    onOpenFood: (Long) -> Unit,
    onOpenDish: (Long) -> Unit,
    onApplyAdjustedMeals: (List<PlannedMeal>) -> Unit
) {
    val today = WeekDay.entries[LocalDate.now().dayOfWeek.value - 1]
    val summaryKey = "WEEKLY_SUMMARY"
    var expandedSection by rememberSaveable { mutableStateOf(today.name) }
    var rebuildSheet by remember { mutableStateOf(false) }
    var optimizationPreview by remember { mutableStateOf<QuantityOptimizationResult?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    val weeklyAssessment = recommendation?.let {
        MealPlanEvaluator.assessWeek(meals, foodsById, dishesById, it)
    }

    fun toggleSection(key: String) {
        expandedSection = if (expandedSection == key) "" else key
    }

    fun nutrientAmount(valuePer100: Double?, grams: Double): String =
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
                dish.ingredients.forEach { ingredient ->
                    val food = foodsById[ingredient.foodId] ?: return@forEach
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
    fun SectionTitle(title: String, expanded: Boolean, onClick: () -> Unit) {
        Row(
            Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Icon(
                if (expanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                contentDescription = if (expanded) "Contraer" else "Expandir"
            )
        }
    }

    @Composable
    fun SummarySection(expanded: Boolean) {
        Column(Modifier.fillMaxWidth()) {
            SectionTitle("Valoración nutricional", expanded) { toggleSection(summaryKey) }
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

    @Composable
    fun DaySection(day: WeekDay, expanded: Boolean) {
        val dayMeals = meals.filter { day in it.days }.associateBy { it.type }
        val assessment = recommendation?.let {
            MealPlanEvaluator.assessDay(day, meals, foodsById, dishesById, it)
        }

        Column(Modifier.fillMaxWidth()) {
            SectionTitle(day.label, expanded) { toggleSection(day.name) }
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
                            meal.items.forEach { planned ->
                                val food = foodsById[planned.foodId] ?: return@forEach
                                FoodNutritionLine(food, meal.resolvedGrams(planned, day))
                            }
                            meal.dishes.forEach { planned ->
                                val dish = dishesById[planned.dishId] ?: return@forEach
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

    message?.let { value ->
        AlertDialog(
            onDismissRequest = { message = null },
            title = { Text("Menú semanal") },
            text = { Text(value) },
            confirmButton = { TextButton(onClick = { message = null }) { Text("Entendido") } }
        )
    }

    if (rebuildSheet) {
        ModalBottomSheet(onDismissRequest = { rebuildSheet = false }) {
            Column(
                Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text("Rehacer menú semanal", style = MaterialTheme.typography.headlineSmall)
                Text("Elige cuánto quieres cambiar.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                FilledTonalButton(
                    onClick = {
                        rebuildSheet = false
                        if (recommendation == null) {
                            message = "Necesitas una recomendación nutricional antes de ajustar el menú."
                        } else {
                            val result = MealQuantityOptimizer.optimize(meals, foodsById, dishesById, recommendation)
                            if (result.changes.isNotEmpty()) optimizationPreview = result
                            else message = "Las cantidades ya están tan ajustadas como permiten tus límites."
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Cambiar solo las cantidades") }
                OutlinedButton(
                    onClick = {
                        rebuildSheet = false
                        message = onRegenerateWeek()
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Cambiar también los platos") }
                TextButton(onClick = { rebuildSheet = false }, Modifier.fillMaxWidth()) { Text("Cancelar") }
                Spacer(Modifier.height(12.dp))
            }
        }
    }

    optimizationPreview?.let { result ->
        QuantityOptimizationPreviewDialog(
            result = result,
            onApply = {
                onApplyAdjustedMeals(result.meals)
                optimizationPreview = null
            },
            onDismiss = { optimizationPreview = null }
        )
    }

    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Tu menú de esta semana", style = MaterialTheme.typography.titleLarge)
        Column(
            Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Card(
                Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(
                    topStart = 12.dp,
                    topEnd = 12.dp,
                    bottomStart = 4.dp,
                    bottomEnd = 4.dp
                )
            ) {
                SummarySection(expandedSection == summaryKey)
            }
            WeekDay.entries.forEachIndexed { index, day ->
                val isLast = index == WeekDay.entries.lastIndex
                Card(
                    Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(
                        topStart = 4.dp,
                        topEnd = 4.dp,
                        bottomStart = if (isLast) 12.dp else 4.dp,
                        bottomEnd = if (isLast) 12.dp else 4.dp
                    )
                ) {
                    DaySection(day, expandedSection == day.name)
                }
            }
        }
    }
}

'''
t = t[:start] + new_weekly + t[end:]

p.write_text(t)
print('Presentación nutricional completa de Inicio aplicada')
