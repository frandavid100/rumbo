from pathlib import Path
import re

path = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
text = path.read_text()

def replace_block(pattern: str, replacement: str, label: str):
    global text
    text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f'{label}: esperaba 1 sustitución y obtuve {count}')

replace_block(
    r'''    @Composable\n    fun SectionHeader\(.*?\n    }\n\n    fun compactNutritionNumber''',
    '''    @Composable
    fun SectionHeader(
        title: String,
        subtitle: String?
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .padding(start = 16.dp, top = 16.dp, end = 16.dp, bottom = 8.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            subtitle?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }

    fun compactNutritionNumber''',
    'SectionHeader'
)

replace_block(
    r'''    @Composable\n    fun CompactNutritionGridValues\(.*?\n    }\n\n    @Composable\n    fun CompactNutritionGrid\(''',
    '''    @Composable
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
                Spacer(Modifier.width(2.dp))
                Text(value, style = MaterialTheme.typography.bodyLarge, color = color, maxLines = 1)
            }
        }

        @Composable
        fun RightMetric(icon: ImageVector, label: String, value: String, modifier: Modifier) {
            Row(
                modifier,
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.End
            ) {
                Text(value, style = MaterialTheme.typography.bodyLarge, color = color, maxLines = 1)
                Spacer(Modifier.width(2.dp))
                Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(17.dp))
            }
        }

        fun display(value: Double?): String = value?.let(::compactNutritionNumber) ?: "—"

        Column(modifier, verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                LeftMetric(
                    Icons.Default.LocalFireDepartment,
                    "Calorías",
                    display(calories),
                    Modifier.width(46.dp)
                )
                Spacer(Modifier.width(6.dp))
                RightMetric(
                    foodCategoryIcon(FoodCategory.PROTEIN),
                    "Proteínas",
                    display(protein),
                    Modifier.width(46.dp)
                )
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                LeftMetric(
                    foodCategoryIcon(FoodCategory.CARBOHYDRATE),
                    "Carbohidratos",
                    display(carbohydrates),
                    Modifier.width(46.dp)
                )
                Spacer(Modifier.width(6.dp))
                RightMetric(
                    foodCategoryIcon(FoodCategory.FAT),
                    "Grasas",
                    display(fat),
                    Modifier.width(46.dp)
                )
            }
        }
    }

    @Composable
    fun CompactNutritionGrid(''',
    'CompactNutritionGridValues'
)

replace_block(
    r'''    @Composable\n    fun FoodNutritionLine\(.*?\n    }\n\n    fun dishAmountLabelForHome''',
    '''    @Composable
    fun FoodNutritionLine(food: Food, grams: Double, modifier: Modifier = Modifier) {
        Row(
            modifier
                .fillMaxWidth()
                .clickable { onOpenFood(food.id) }
                .padding(vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(
                    food.name,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    foodAmountLabel(food, grams),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1
                )
            }
            CompactNutritionGrid(food, grams, Modifier.width(98.dp))
        }
    }

    fun dishAmountLabelForHome''',
    'FoodNutritionLine'
)

replace_block(
    r'''    @Composable\n    fun DishNutritionCard\(.*?\n    }\n\n    @Composable\n    fun AbsoluteNutritionSummary''',
    '''    @Composable
    fun DishNutritionCard(dish: Dish, grams: Double) {
        val totalWeight = dish.totalWeightGrams().takeIf { it > 0.0 } ?: 1.0
        val totals = dish.nutritionForGrams(foodsById, grams)
        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .clickable { onOpenDish(dish.id) }
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        dish.name,
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        dishAmountLabelForHome(dish, grams),
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1
                    )
                }
                CompactNutritionGridValues(
                    calories = totals.calories,
                    protein = totals.proteinGrams,
                    carbohydrates = totals.carbohydrateGrams,
                    fat = totals.fatGrams,
                    modifier = Modifier.width(98.dp)
                )
            }
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = MaterialTheme.colorScheme.surfaceContainer
            ) {
                Column(
                    Modifier.fillMaxWidth().padding(vertical = 6.dp),
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
                            FoodNutritionLine(
                                food,
                                ingredientGrams,
                                Modifier.padding(horizontal = 16.dp)
                            )
                        }
                }
            }
        }
    }

    @Composable
    fun AbsoluteNutritionSummary''',
    'DishNutritionCard'
)

replace_block(
    r'''    @Composable\n    fun AbsoluteNutritionSummary\(.*?\n    }\n\n    @Composable\n    fun WeeklyPercentSummary''',
    '''    @Composable
    fun AbsoluteNutritionSummary(assessment: PlanNutritionAssessment?) {
        val color = MaterialTheme.colorScheme.onSurfaceVariant
        val actual = assessment?.actual

        @Composable
        fun Metric(
            icon: ImageVector,
            label: String,
            text: String,
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
                    text,
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
                actual?.calories?.let { "${compactNutritionNumber(it)} kcal" } ?: "—",
                Arrangement.Start,
                Modifier.weight(1.18f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.PROTEIN),
                "Proteínas",
                actual?.proteinGrams?.let { "${compactNutritionNumber(it)} g" } ?: "—",
                Arrangement.Center,
                Modifier.weight(0.94f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.CARBOHYDRATE),
                "Carbohidratos",
                actual?.carbohydrateGrams?.let { "${compactNutritionNumber(it)} g" } ?: "—",
                Arrangement.Center,
                Modifier.weight(0.94f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.FAT),
                "Grasas",
                actual?.fatGrams?.let { "${compactNutritionNumber(it)} g" } ?: "—",
                Arrangement.End,
                Modifier.weight(0.94f)
            )
        }
    }

    @Composable
    fun WeeklyPercentSummary''',
    'AbsoluteNutritionSummary'
)

replace_block(
    r'''    @Composable\n    fun WeeklyPercentSummary\(.*?\n    }\n\n    @Composable\n    fun SummarySection''',
    '''    @Composable
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
                Modifier.weight(1.18f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.PROTEIN),
                "Proteínas",
                percentage(assessment.actual.proteinGrams, assessment.target.proteinGrams),
                Arrangement.Center,
                Modifier.weight(0.94f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.CARBOHYDRATE),
                "Carbohidratos",
                percentage(assessment.actual.carbohydrateGrams, assessment.target.carbohydrateGrams),
                Arrangement.Center,
                Modifier.weight(0.94f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.FAT),
                "Grasas",
                percentage(assessment.actual.fatGrams, assessment.target.fatGrams),
                Arrangement.End,
                Modifier.weight(0.94f)
            )
        }
    }

    @Composable
    fun SummarySection''',
    'WeeklyPercentSummary'
)

replace_block(
    r'''    @Composable\n    fun SummarySection\(.*?\n    }\n\n    @Composable\n    fun DaySection''',
    '''    @Composable
    fun SummarySection(expanded: Boolean) {
        Column(Modifier.fillMaxWidth()) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .clickable { toggleSection(summaryKey) }
            ) {
                SectionHeader(
                    title = "Valoración nutricional",
                    subtitle = null
                )
                weeklyAssessment?.let {
                    Box(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 14.dp)) {
                        WeeklyPercentSummary(it)
                    }
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
                            onClick = onOpenCurrentShoppingList,
                            modifier = Modifier.weight(1f)
                        ) { Text("Lista de la compra") }
                    }
                }
            }
        }
    }

    @Composable
    fun DaySection''',
    'SummarySection'
)

replace_block(
    r'''    @Composable\n    fun DaySection\(.*?\n    }\n\n    Column\(Modifier.fillMaxWidth\(\), verticalArrangement = Arrangement.spacedBy\(12.dp\)\)''',
    '''    @Composable
    fun DaySection(day: WeekDay, expanded: Boolean) {
        val dayMeals = meals.filter { day in it.days }.associateBy { it.type }
        val assessment = recommendation?.let {
            MealPlanEvaluator.assessDay(day, meals, foodsById, dishesById, it)
        }

        Column(Modifier.fillMaxWidth()) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .clickable { toggleSection(day.name) }
            ) {
                SectionHeader(
                    title = day.label,
                    subtitle = null
                )
                Box(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 14.dp)) {
                    AbsoluteNutritionSummary(assessment)
                }
            }
            AnimatedVisibility(
                visible = expanded,
                enter = expandVertically(expandFrom = Alignment.Top) + fadeIn(),
                exit = shrinkVertically(shrinkTowards = Alignment.Top) + fadeOut()
            ) {
                Column(
                    Modifier.fillMaxWidth().padding(bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    HorizontalDivider(
                        modifier = Modifier.padding(horizontal = 16.dp),
                        color = MaterialTheme.colorScheme.outlineVariant
                    )
                    if (dayMeals.isEmpty()) {
                        Text(
                            "No hay comidas planificadas.",
                            modifier = Modifier.padding(horizontal = 16.dp),
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    val visibleTypes = MealType.entries.filter { dayMeals[it] != null }
                    visibleTypes.forEachIndexed { index, type ->
                        val meal = dayMeals[type] ?: return@forEachIndexed
                        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(
                                type.label,
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier
                                    .padding(horizontal = 16.dp)
                                    .clickable { onOpenMeal(meal.id) }
                            )
                            meal.dishes.forEach dishLoop@ { planned ->
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
                                    FoodNutritionLine(
                                        food,
                                        meal.resolvedGrams(planned, day),
                                        Modifier.padding(horizontal = 16.dp)
                                    )
                                }
                        }
                        if (index < visibleTypes.lastIndex) {
                            HorizontalDivider(
                                modifier = Modifier.padding(horizontal = 16.dp),
                                color = MaterialTheme.colorScheme.outlineVariant
                            )
                        }
                    }
                }
            }
        }
    }

    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp))''',
    'DaySection'
)

path.write_text(text)
print('Último pulido de Inicio aplicado correctamente')
