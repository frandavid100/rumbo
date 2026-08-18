from pathlib import Path

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()

def exact(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, got {n}')
    s = s.replace(old, new, 1)

# Home callback for guided search targets.
exact(
'''                    onOpenFoods = {
                        catalogRetailerFilter = null
                        catalogNutritionalRoleFilter = null
                        catalogCulinaryRoleFilter = null
                        catalogSearchRequest += 1
                        screenName = Screen.HOME.name
                    },
''',
'''                    onOpenFoods = {
                        catalogRetailerFilter = null
                        catalogNutritionalRoleFilter = null
                        catalogCulinaryRoleFilter = null
                        catalogSearchRequest += 1
                        screenName = Screen.HOME.name
                    },
                    onOpenProgressSearch = { nutritionalRole, culinaryRole, mealType ->
                        catalogRetailerFilter = null
                        catalogNutritionalRoleFilter = nutritionalRole
                        catalogCulinaryRoleFilter = culinaryRole
                        catalogSearchMealTypeName = mealType?.name
                        catalogSearchOverlayOpen = true
                    },
''',
'home progress callback')

exact(
'''    onOpenDish: (Long) -> Unit,
    onOpenFoods: () -> Unit,
    onAddMissingMeal: (MealType, WeekDay) -> Unit,
''',
'''    onOpenDish: (Long) -> Unit,
    onOpenFoods: () -> Unit,
    onOpenProgressSearch: (String?, String?, MealType?) -> Unit,
    onAddMissingMeal: (MealType, WeekDay) -> Unit,
''',
'home signature progress callback')

# Replace the old three-suggestion card on Home with a single evaluator-driven progress card.
exact(
'''        if (pinnedSuggestions.isNotEmpty() || !menuReady && recommendation != null) {
            item {
                FoodSuggestionsCard(
                    suggestions = pinnedSuggestions,
                    showMenuReadiness = recommendation != null && !menuReady,
                    assessment = repertoireAssessment,
                    recommendationMessage = pinnedRecommendationMessage,
                    recommendationFocus = recommendationFocusName?.let { name ->
                        EfficientNutrient.entries.firstOrNull { it.name == name }
                    },
                    onOpenFood = openFood,
                    onDismiss = onDismissFoodSuggestion
                )
            }
        }
''',
'''        if (recommendation != null) {
            item {
                RepertoireProgressCard(
                    assessment = repertoireAssessment,
                    foods = data.foods,
                    repertoireFoodIds = data.activeProfileData?.repertoireFoodIds.orEmpty(),
                    planningRules = data.activeProfileData?.planningRules.orEmpty(),
                    onOpenSearch = onOpenProgressSearch
                )
            }
        }
''',
'home progress card')

# Insert model/helpers/card before the legacy FoodSuggestionsCard. Keep the old composable for now
# because detail/other flows may still refer to FoodSuggestionEntry; only Home stops using the card.
marker = '''@Composable
private fun FoodSuggestionsCard(
'''
if s.count(marker) != 1:
    raise SystemExit('FoodSuggestionsCard marker mismatch')
insert = r'''private data class RepertoireProgressTarget(
    val message: String,
    val buttonLabel: String? = null,
    val nutritionalRole: String? = null,
    val culinaryRole: String? = null,
    val mealType: MealType? = null
)

private data class RepertoireRoleMilestone(
    val role: String,
    val target: Int,
    val singular: String,
    val plural: String
)

private val initialRepertoireRoleMilestones = listOf(
    RepertoireRoleMilestone("PRIMARY_PROTEIN", 3, "proteína principal", "proteínas principales"),
    RepertoireRoleMilestone("COMPLEMENTARY_PROTEIN", 3, "proteína complementaria", "proteínas complementarias"),
    RepertoireRoleMilestone("PRIMARY_CARBOHYDRATE", 3, "hidrato principal", "hidratos principales"),
    RepertoireRoleMilestone("COMPLEMENTARY_CARBOHYDRATE", 3, "hidrato complementario", "hidratos complementarios"),
    RepertoireRoleMilestone("CONCENTRATED_FAT", 1, "grasa concentrada", "grasas concentradas"),
    RepertoireRoleMilestone("COMPLEMENTARY_FAT", 3, "grasa complementaria", "grasas complementarias")
)

private fun repertoireProgressTarget(
    assessment: RepertoireAssessment?,
    foods: List<Food>,
    repertoireFoodIds: Set<Long>,
    planningRules: List<PlanningRule>
): Pair<Int, RepertoireProgressTarget> {
    if (assessment == null) {
        return 0 to RepertoireProgressTarget("Estamos analizando tus alimentos para encontrar el siguiente paso.")
    }
    if (assessment.searchStatus == ConstraintSearchStatus.FEASIBLE) {
        val missingVegetables = (3 - assessment.vegetableConcepts).coerceAtLeast(0)
        if (missingVegetables > 0) {
            val noun = if (missingVegetables == 1) "verdura diferente" else "verduras diferentes"
            return 1 to RepertoireProgressTarget(
                message = "Ya puedes crear un menú viable. Para avanzar hacia un menú completo, amplía primero la variedad de verduras.",
                buttonLabel = "Añadir $missingVegetables $noun",
                nutritionalRole = "VEGETABLE"
            )
        }
        val missingFruit = (2 - assessment.fruitConcepts).coerceAtLeast(0)
        if (missingFruit > 0) {
            val noun = if (missingFruit == 1) "fruta diferente" else "frutas diferentes"
            return 1 to RepertoireProgressTarget(
                message = "Ya puedes crear un menú viable. El siguiente paso es ampliar la fruta para acercarte al nivel 2.",
                buttonLabel = "Añadir $missingFruit $noun",
                nutritionalRole = "FRUIT"
            )
        }
        return 1 to RepertoireProgressTarget(
            "Nivel 1 conseguido: tu repertorio permite crear un menú viable. Ya tienes cubierta la variedad básica de fruta y verdura; los demás criterios del nivel 2 se evaluarán al completar el motor de menú completo."
        )
    }

    val activeConfiguredIds = planningRules.asSequence()
        .filter {
            it.itemKind == PlannedItemKind.FOOD && it.isActive &&
                it.frequency != PlanningFrequency.NEVER
        }
        .map { it.itemId }
        .toSet()
        .intersect(repertoireFoodIds)
    val configuredFoods = foods.filter { it.id in activeConfiguredIds }

    initialRepertoireRoleMilestones.forEach { milestone ->
        val current = configuredFoods.count { milestone.role in it.nutritionalRoles }
        val missing = (milestone.target - current).coerceAtLeast(0)
        if (missing > 0) {
            val noun = if (missing == 1) milestone.singular else milestone.plural
            return 0 to RepertoireProgressTarget(
                message = "Para poder crear un menú viable, el siguiente paso es cubrir ${milestone.plural} en tu repertorio.",
                buttonLabel = "Añadir $missing $noun",
                nutritionalRole = milestone.role
            )
        }
    }

    assessment.culinaryNeeds.firstOrNull()?.let { need ->
        val role = need.acceptedRoles.firstOrNull()
        if (role != null) {
            return 0 to RepertoireProgressTarget(
                message = need.message,
                buttonLabel = "Añadir ${role.label.lowercase()}",
                culinaryRole = role.name,
                mealType = need.mealType
            )
        }
    }

    val deficit = listOf(
        NutrientKind.PROTEIN to "PRIMARY_PROTEIN",
        NutrientKind.CARBOHYDRATES to "PRIMARY_CARBOHYDRATE",
        NutrientKind.FAT to "COMPLEMENTARY_FAT"
    ).firstOrNull { (kind, _) ->
        assessment.nutrition[kind]?.let { it.deviation < 0.0 && it.fit != TargetFit.ON_TARGET } == true
    }
    if (deficit != null) {
        val roleLabel = nutritionalRoleLabel(deficit.second).lowercase()
        return 0 to RepertoireProgressTarget(
            message = "Tu repertorio básico ya está configurado, pero el evaluador todavía detecta un déficit. Añade otra opción eficiente para intentar resolverlo.",
            buttonLabel = "Añadir $roleLabel",
            nutritionalRole = deficit.second
        )
    }

    return 0 to RepertoireProgressTarget(
        assessment.limitingFactors.firstOrNull()
            ?: "Todavía no hemos podido demostrar que exista un menú viable con la configuración actual. Revisa las comidas asignadas a tus alimentos."
    )
}

@Composable
private fun RepertoireLevelMilestones(currentLevel: Int) {
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        (0..4).forEach { level ->
            val reached = level <= currentLevel
            val circleColor = if (reached) MaterialTheme.colorScheme.primary
                else MaterialTheme.colorScheme.outlineVariant
            Box(
                Modifier.size(30.dp).background(circleColor, CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    level.toString(),
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold,
                    color = if (reached) MaterialTheme.colorScheme.onPrimary
                    else MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            if (level < 4) {
                HorizontalDivider(
                    modifier = Modifier.weight(1f),
                    thickness = 2.dp,
                    color = if (level < currentLevel) MaterialTheme.colorScheme.primary
                    else MaterialTheme.colorScheme.outlineVariant
                )
            }
        }
    }
}

@Composable
private fun RepertoireProgressCard(
    assessment: RepertoireAssessment?,
    foods: List<Food>,
    repertoireFoodIds: Set<Long>,
    planningRules: List<PlanningRule>,
    onOpenSearch: (String?, String?, MealType?) -> Unit
) {
    val (level, target) = remember(assessment, foods, repertoireFoodIds, planningRules) {
        repertoireProgressTarget(assessment, foods, repertoireFoodIds, planningRules)
    }
    val title = when (level) {
        0 -> "Nivel 0 · Preparando un menú viable"
        1 -> "Nivel 1 · Menú viable"
        2 -> "Nivel 2 · Menú completo"
        3 -> "Nivel 3 · Culinariamente satisfactorio"
        else -> "Nivel 4 · Menú variado"
    }
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Tu repertorio", style = MaterialTheme.typography.titleLarge)
        Card(Modifier.fillMaxWidth()) {
            Column(
                Modifier.fillMaxWidth().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                RepertoireLevelMilestones(level)
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(target.message, style = MaterialTheme.typography.bodyLarge)
                target.buttonLabel?.let { label ->
                    FilledTonalButton(
                        onClick = {
                            onOpenSearch(target.nutritionalRole, target.culinaryRole, target.mealType)
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(label)
                    }
                }
            }
        }
    }
}

'''
s = s.replace(marker, insert + marker, 1)

p.write_text(s)
print('single repertoire progress card applied')
