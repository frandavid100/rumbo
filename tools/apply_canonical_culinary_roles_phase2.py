from pathlib import Path
import re

def read(p): return Path(p).read_text()
def write(p,s): Path(p).write_text(s)
def one(s,old,new,label):
    n=s.count(old)
    if n!=1: raise SystemExit(f'{label}: exact matches={n}')
    return s.replace(old,new,1)
def sub1(s,pat,repl,label,flags=re.S):
    out,n=re.subn(pat,repl,s,count=1,flags=flags)
    if n!=1: raise SystemExit(f'{label}: regex matches={n}')
    return out

# AppRepository: overrides keyed by role, legacy backup read only.
p='app/src/main/java/es/david/rumbo/data/AppRepository.kt'; s=read(p)
s=s.replace('import es.david.rumbo.model.CulinaryType\n','')
s=one(s,'import es.david.rumbo.model.CulinaryPolicyOverride\n','import es.david.rumbo.model.CulinaryPolicyOverride\nimport es.david.rumbo.model.legacyCulinaryRoles\n','repo legacy import')
s=one(s,'''        val type = override.culinaryType
        val updated = active.copy(
            culinaryPolicyOverrides = active.culinaryPolicyOverrides
                .filterNot { it.culinaryType == type } + override
''','''        val role = override.culinaryRole
        val updated = active.copy(
            culinaryPolicyOverrides = active.culinaryPolicyOverrides
                .filterNot { it.culinaryRole == role } + override
''','save override')
s=one(s,'''    fun resetCulinaryPolicyOverride(type: CulinaryType): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        return updateActive(
            current,
            active.copy(
                culinaryPolicyOverrides = active.culinaryPolicyOverrides
                    .filterNot { it.culinaryType == type }
            )
        )
    }
''','''    fun resetCulinaryPolicyOverride(role: String): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        return updateActive(
            current,
            active.copy(
                culinaryPolicyOverrides = active.culinaryPolicyOverrides
                    .filterNot { it.culinaryRole == role }
            )
        )
    }
''','reset override')
s=s.replace('put("schemaVersion", 22)','put("schemaVersion", 23)')
s=s.replace('                put("culinaryType", food.culinaryType.name)\n','')
s=one(s,'''                put("culinaryType", override.culinaryType.name)
                put("roles", JSONArray(override.roles.toList()))
''','''                put("culinaryRole", override.culinaryRole)
''','encode override')
s=one(s,'''                put("standaloneAllowed", override.standaloneAllowed)
''','''                putNullable("standaloneAllowed", override.standaloneAllowed)
''','override nullable')
s=sub1(s,r'''                    culinaryType = item\.optionalEnum\("culinaryType", CulinaryType::valueOf\)\n                        \?: baseFoodsById\[item\.getLong\("id"\)\]\?\.culinaryType\n                        \?: CulinaryType\.UNKNOWN,\n                    nutritionalRoles =''','''                    nutritionalRoles =''','decode food type')
s=one(s,'''                    culinaryRoles = item.optJSONArray("culinaryRoles")?.let { values ->
                        buildSet { for (i in 0 until values.length()) add(values.getString(i)) }
                    } ?: baseFoodsById[item.getLong("id")]?.culinaryRoles.orEmpty()
''','''                    culinaryRoles = item.optJSONArray("culinaryRoles")?.let { values ->
                        buildSet { for (i in 0 until values.length()) add(values.getString(i)) }
                    } ?: baseFoodsById[item.getLong("id")]?.culinaryRoles
                        ?.takeIf { it.isNotEmpty() }
                        ?: legacyCulinaryRoles(item.optionalString("culinaryType"))
''','decode food roles legacy')
s=sub1(s,r'''    private fun decodeCulinaryPolicyOverrides\(\n        array: JSONArray\n    \): List<CulinaryPolicyOverride> = buildList \{.*?\n    \}\n\n    private fun decodeNutritionToleranceSettings''','''    private fun decodeCulinaryPolicyOverrides(
        array: JSONArray
    ): List<CulinaryPolicyOverride> = buildList {
        for (index in 0 until array.length()) {
            val item = array.getJSONObject(index)
            val roles = item.optionalString("culinaryRole")?.let(::setOf)
                ?: legacyCulinaryRoles(item.optionalString("culinaryType"))
            roles.forEach { role ->
                add(
                    CulinaryPolicyOverride(
                        culinaryRole = role,
                        preferredGrams = item.optionalDouble("preferredGrams"),
                        minimumGrams = item.optionalDouble("minimumGrams"),
                        maximumGrams = item.optionalDouble("maximumGrams"),
                        standaloneAllowed = if (item.has("standaloneAllowed") && !item.isNull("standaloneAllowed")) {
                            item.getBoolean("standaloneAllowed")
                        } else null
                    )
                )
            }
        }
    }

    private fun decodeNutritionToleranceSettings''','decode overrides')
write(p,s)

# Food suggestion equivalence = overlapping functional roles.
p='app/src/main/java/es/david/rumbo/logic/FoodSuggestionEngine.kt'; s=read(p)
s=one(s,'''                it.food.id != source.id && it.food.culinaryType == source.culinaryType &&
                    nutrient in efficientNutrients(it.food) &&
''','''                it.food.id != source.id &&
                    CulinaryPolicy.roles(it.food).intersect(CulinaryPolicy.roles(source)).isNotEmpty() &&
                    nutrient in efficientNutrients(it.food) &&
''','suggestion same culinary function')
write(p,s)

# Repertoire evaluator: needs refer to roles, never types.
p='app/src/main/java/es/david/rumbo/logic/RepertoireEvaluator.kt'; s=read(p)
s=s.replace('import es.david.rumbo.model.CulinaryType\n','')
s=s.replace('    val acceptedTypes: Set<CulinaryType>,','    val acceptedRoles: Set<CulinaryRole>,')
s=sub1(s,r'''    private fun dependencyNeeds\(\n        rules: List<PlanningRule>,\n        foodsById: Map<Long, Food>\n    \): List<CulinaryNeed> \{.*?\n    \}\n\n    private fun macroCulinaryNeeds''','''    private fun dependencyNeeds(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>
    ): List<CulinaryNeed> = MealType.entries.mapNotNull { mealType ->
        val mealRules = rules.filter {
            mealType in it.allowedMealTypes || it.requiredSlots().any { slot -> slot.mealType == mealType }
        }
        val roleChoices = mealRules.mapNotNull { rule ->
            foodsById[rule.itemId]?.let(CulinaryPolicy::roles)
        }
        val missing = CulinaryPolicy.missingRequiredRoles(roleChoices)
        if (missing.isEmpty()) null else CulinaryNeed(
            CulinaryNeedKind.COMPANION_BASE,
            mealType,
            missing,
            "Falta ${missing.joinToString(" o ") { it.label.lowercase() }} para completar una combinación en " +
                mealType.label.lowercase() + "."
        )
    }

    private fun macroCulinaryNeeds''','dependency needs')
s=s.replace('CulinaryRole.STARCH_BASE','CulinaryRole.PLATE_BASE')
s=s.replace('CulinaryRole.PRIMARY_PROTEIN','CulinaryRole.PLATE_CENTER')
s=one(s,'''                    CulinaryNeedKind.STARCH_BASE, meal,
                    setOf(CulinaryType.DRY_RICE, CulinaryType.DRY_PASTA, CulinaryType.FRESH_STARCH),
''','''                    CulinaryNeedKind.STARCH_BASE, meal,
                    setOf(CulinaryRole.PLATE_BASE),
''','carb need')
s=one(s,'''                    CulinaryNeedKind.PRIMARY_PROTEIN, meal,
                    setOf(CulinaryType.MAIN_MEAT, CulinaryType.MAIN_FISH, CulinaryType.MAIN_EGG),
''','''                    CulinaryNeedKind.PRIMARY_PROTEIN, meal,
                    setOf(CulinaryRole.PLATE_CENTER),
''','protein need')
s=one(s,'''                CulinaryNeedKind.FAT_COMPLEMENT, meal,
                setOf(CulinaryType.FAT_COMPLEMENT),
''','''                CulinaryNeedKind.FAT_COMPLEMENT, meal,
                setOf(CulinaryRole.TOPPING, CulinaryRole.COOKING_MEDIUM, CulinaryRole.STANDALONE),
''','fat need')
write(p,s)

# Constraint model: do not exclude non-standalone roles; generic proof for mandatory missing companions.
p='app/src/main/java/es/david/rumbo/logic/MenuConstraintContract.kt'; s=read(p)
s=one(s,'''                    foodsById[it.itemId]?.hasComparableNutrition() == true &&
                    foodsById[it.itemId]?.let(CulinaryPolicy::standaloneAllowed) != false
''','''                    foodsById[it.itemId]?.hasComparableNutrition() == true
''','active rule standalone filter')
s=sub1(s,r'''                    // This is a proof, not a heuristic:.*?                    if \(requiredDependentRules\.isNotEmpty\(\)\) \{.*?                    \}\n''','''                    val requiredRules = mealRules.filter { it.frequency == PlanningFrequency.ALWAYS }
                    val allChoices = mealRules.mapNotNull { rule ->
                        foodsById[rule.itemId]?.let(CulinaryPolicy::roles)
                    }
                    requiredRules.forEach { required ->
                        val requiredChoices = foodsById[required.itemId]?.let(CulinaryPolicy::roles).orEmpty()
                        if (requiredChoices.isNotEmpty()) {
                            val impossible = requiredChoices.all { role ->
                                CulinaryPolicy.policy(role).requiredRoles.any { needed ->
                                    allChoices.none { needed in it }
                                }
                            }
                            if (impossible) {
                                add(ConstraintViolation(
                                    ConstraintViolationKind.MISSING_REQUIRED_COMPANION,
                                    "Hay un alimento obligatorio que necesita un acompañamiento culinario en " +
                                        mealType.label.lowercase() + ", pero no existe ninguna opción programada.",
                                    mealType,
                                    setOf(required.itemId)
                                ))
                            }
                        }
                    }
''','generic structural proof')
write(p,s)

# Weekly generator: validate complete role assignments and generic companion search.
p='app/src/main/java/es/david/rumbo/logic/WeeklyMenuGenerator.kt'; s=read(p)
s=one(s,'''        val foodRules = rules.filter {
            it.itemKind == PlannedItemKind.FOOD && it.isActive &&
                foodsById[it.itemId]?.let(CulinaryPolicy::standaloneAllowed) != false
        }
''','''        val foodRules = rules.filter {
            it.itemKind == PlannedItemKind.FOOD && it.isActive
        }
''','generator active standalone')
s=sub1(s,r'''    private fun hasCompatibleExclusiveRoles\(.*?\n    private fun resolveFixedSlots\(''','''    private fun roleChoices(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): List<Set<CulinaryRole>> = rules.flatMap { rule ->
        when (rule.itemKind) {
            PlannedItemKind.FOOD -> listOf(foodsById[rule.itemId]?.let(CulinaryPolicy::roles).orEmpty())
            PlannedItemKind.DISH -> dishesById[rule.itemId]?.ingredients.orEmpty().map { ingredient ->
                foodsById[ingredient.foodId]?.let(CulinaryPolicy::roles).orEmpty()
            }
        }
    }

    private fun hasCompatibleExclusiveRoles(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): Boolean {
        val choices = roleChoices(rules, foodsById, dishesById)
        if (choices.any { it.isEmpty() }) return false
        // A partial composition may still be completed later; only reject cardinality
        // when no role choice avoids it.
        return choices.isEmpty() || choices.fold(listOf(emptyList<CulinaryRole>())) { states, options ->
            states.flatMap { state -> options.map { state + it } }
                .filter { chosen ->
                    val counts = chosen.groupingBy { it }.eachCount()
                    counts.none { (role, count) -> CulinaryPolicy.policy(role).maxPerMeal?.let { count > it } == true }
                }.take(128)
        }.isNotEmpty()
    }

    private fun hasUnmetDependency(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): Boolean = !CulinaryPolicy.hasValidRoleAssignment(roleChoices(rules, foodsById, dishesById))

    fun isCulinarilyValid(
        meals: List<PlannedMeal>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>
    ): Boolean = WeekDay.entries.all { day ->
        meals.filter { day in it.days }.all { meal ->
            val rules = meal.items.map {
                PlanningRule(
                    itemKind = PlannedItemKind.FOOD,
                    itemId = it.foodId,
                    allowedMealTypes = setOf(meal.type),
                    preferredGrams = meal.resolvedGrams(it, day)
                )
            } + meal.dishes.map {
                PlanningRule(
                    itemKind = PlannedItemKind.DISH,
                    itemId = it.dishId,
                    allowedMealTypes = setOf(meal.type),
                    preferredGrams = meal.resolvedGrams(it, day)
                )
            }
            CulinaryPolicy.hasValidRoleAssignment(roleChoices(rules, foodsById, dishesById))
        }
    }

    private fun resolveFixedSlots(''','generator helpers')
# Generic companion selection: replace hardcoded role.
s=one(s,'''        val companions = eligible.filter { companion ->
            companion.itemKind == PlannedItemKind.FOOD &&
                companion.roles(foodsById, dishesById)
                    .contains(CulinaryRole.LIQUID_OR_CREAMY_BASE) &&
                direct.none { it.sameItem(companion) || it.overlaps(companion, dishesById) } &&
                hasCompatibleExclusiveRoles(direct + companion, foodsById, dishesById) &&
                !hasUnmetDependency(direct + companion, foodsById, dishesById)
        }
''','''        val companions = eligible.filter { companion ->
            companion.itemKind == PlannedItemKind.FOOD &&
                direct.none { it.sameItem(companion) || it.overlaps(companion, dishesById) } &&
                hasCompatibleExclusiveRoles(direct + companion, foodsById, dishesById) &&
                !hasUnmetDependency(direct + companion, foodsById, dishesById)
        }
''','generic companion')
s=s.replace('''                "Hay un alimento que necesita leche, bebida vegetal, yogur o una base similar " +
                    "en ${slot.mealType.label.lowercase()}."
''','''                "Hay una combinación culinaria incompleta en ${slot.mealType.label.lowercase()}."
''')
write(p,s)

# UI: remove legacy screen and type-based rules editor. Keep one search only.
p='app/src/main/java/es/david/rumbo/ui/App.kt'; s=read(p)
s=s.replace('import es.david.rumbo.logic.CulinaryTypePolicy\n','import es.david.rumbo.logic.CulinaryRolePolicy\n')
s=s.replace('import es.david.rumbo.model.CulinaryType\n','')
s=s.replace('    FOODS("Alimentos y platos", Icons.Default.Search, false),\n','')
# Direct all historical FOODS destinations to HOME; search requests are handled by Home search state.
s=s.replace('Screen.FOODS.name','Screen.HOME.name')
s=s.replace('''                        Screen.FOODS ->
                            Text("Alimentos y platos", fontWeight = FontWeight.SemiBold)
''','')
# remove unreachable screen block and entire old composable
s=sub1(s,r'''                screen == Screen\.FOODS -> FoodDishCatalogScreen\(.*?\n                screen == Screen\.ADD_FOOD ->''','''                screen == Screen.ADD_FOOD ->''','remove FOODS route')
s=sub1(s,r'''@Composable\nprivate fun FoodDishCatalogScreen\(.*?\n@Composable\nprivate fun CatalogCanonicalFilterRow\(''','''@Composable
private fun CatalogCanonicalFilterRow(''','remove old catalog screen')
# Remove obsolete filter helpers except canonical row/string menu.
s=sub1(s,r'''@Composable\nprivate fun CatalogFilterChips\(.*?\n@Composable\nprivate fun CatalogEntries\(''','''@Composable
private fun CatalogEntries(''','remove obsolete filter helpers')
# Home onOpenFoods: request canonical search instead of any screen route.
s=one(s,'''                    onOpenFoods = { screenName = Screen.HOME.name },
''','''                    onOpenFoods = {
                        catalogRetailerFilter = null
                        catalogNutritionalRoleFilter = null
                        catalogCulinaryRoleFilter = null
                        catalogSearchRequest += 1
                        screenName = Screen.HOME.name
                    },
''','open foods canonical search')
# Food detail culinary recommendation uses role addressing.
s=s.replace('''                            ?.firstOrNull { food.culinaryType in it.acceptedTypes }
''','''                            ?.firstOrNull { CulinaryPolicy.addresses(it, food) }
''')
# Profile callbacks are strings now.
s=s.replace('onResetCulinaryPolicy: (CulinaryType) -> Unit','onResetCulinaryPolicy: (String) -> Unit')
# Replace whole culinary rules UI with role editor.
s=sub1(s,r'''@Composable\nprivate fun CulinaryRulesCard\(.*?\n@Composable\nprivate fun WaistMeasurementHelp\(''','''@Composable
private fun CulinaryRulesCard(
    overrides: List<CulinaryPolicyOverride>,
    onSave: (CulinaryPolicyOverride) -> Unit,
    onReset: (String) -> Unit
) {
    var editingRole by remember { mutableStateOf<CulinaryRole?>(null) }
    editingRole?.let { role ->
        CulinaryPolicyEditorDialog(
            role = role,
            override = overrides.firstOrNull { it.culinaryRole == role.name },
            onDismiss = { editingRole = null },
            onSave = { onSave(it); editingRole = null },
            onReset = { onReset(role.name); editingRole = null }
        )
    }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(vertical = 8.dp)) {
            Text(
                "Reglas culinarias",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
            )
            Text(
                "Cada función culinaria tiene una política común de cantidades y combinación.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
            )
            HorizontalDivider()
            CulinaryRole.entries.forEach { role ->
                val custom = overrides.firstOrNull { it.culinaryRole == role.name }
                val policy = CulinaryPolicy.policy(role)
                TextButton(
                    onClick = { editingRole = role },
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp)
                ) {
                    Column(Modifier.weight(1f), horizontalAlignment = Alignment.Start) {
                        Text(role.label, color = MaterialTheme.colorScheme.onSurface)
                        Text(
                            culinaryPolicySummary(policy),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = TextAlign.Start
                        )
                    }
                    if (custom != null) Text("Modificada")
                    Icon(Icons.Default.KeyboardArrowRight, contentDescription = null)
                }
            }
        }
    }
}

@Composable
private fun CulinaryPolicyEditorDialog(
    role: CulinaryRole,
    override: CulinaryPolicyOverride?,
    onDismiss: () -> Unit,
    onSave: (CulinaryPolicyOverride) -> Unit,
    onReset: () -> Unit
) {
    val initial = CulinaryPolicy.policy(role)
    var preferred by remember(role, override) { mutableStateOf(initial.preferredGrams?.let(::formatDecimal).orEmpty()) }
    var minimum by remember(role, override) { mutableStateOf(initial.minimumGrams?.let(::formatDecimal).orEmpty()) }
    var maximum by remember(role, override) { mutableStateOf(initial.maximumGrams?.let(::formatDecimal).orEmpty()) }
    var standalone by remember(role, override) { mutableStateOf(initial.standaloneAllowed) }
    val preferredValue = parseDecimal(preferred)
    val minimumValue = parseDecimal(minimum)
    val maximumValue = parseDecimal(maximum)
    val quantitiesValid = preferredValue != null && minimumValue != null && maximumValue != null &&
        minimumValue > 0.0 && minimumValue <= preferredValue && preferredValue <= maximumValue

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(role.label) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                val hardRules = buildList {
                    if (initial.requiredRoles.isNotEmpty()) add("Requiere: ${initial.requiredRoles.joinToString { it.label }}")
                    initial.maxPerMeal?.let { add("Máximo por comida: $it") }
                }
                hardRules.forEach { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                HorizontalDivider()
                Text("Rango de uso", fontWeight = FontWeight.SemiBold)
                NumericField("Cantidad habitual (g)", preferred, { preferred = it }, Modifier.fillMaxWidth())
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    NumericField("Mínimo (g)", minimum, { minimum = it }, Modifier.weight(1f))
                    NumericField("Máximo (g)", maximum, { maximum = it }, Modifier.weight(1f))
                }
                Row(Modifier.fillMaxWidth().clickable { standalone = !standalone }, verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = standalone, onCheckedChange = null)
                    Text("Puede desempeñar esta función como único elemento de la comida")
                }
                if (!quantitiesValid) {
                    Text("Cumple mínimo ≤ habitual ≤ máximo.", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
                if (override != null) TextButton(onClick = onReset) { Text("Restaurar regla predeterminada") }
            }
        },
        confirmButton = {
            TextButton(enabled = quantitiesValid, onClick = {
                onSave(CulinaryPolicyOverride(
                    culinaryRole = role.name,
                    preferredGrams = preferredValue,
                    minimumGrams = minimumValue,
                    maximumGrams = maximumValue,
                    standaloneAllowed = standalone
                ))
            }) { Text("Guardar") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } }
    )
}

private fun culinaryPolicySummary(policy: CulinaryRolePolicy): String {
    val rules = mutableListOf<String>()
    if (!policy.standaloneAllowed) rules += "No puede ir sola"
    if (policy.requiredRoles.isNotEmpty()) rules += "Requiere ${policy.requiredRoles.joinToString { it.label }}"
    policy.maxPerMeal?.let { rules += "Máx. $it por comida" }
    policy.preferredGrams?.let { preferred ->
        rules += "${formatDecimal(policy.minimumGrams ?: preferred)}–${formatDecimal(policy.maximumGrams ?: preferred)} g"
    }
    return rules.ifEmpty { listOf("Sin reglas especiales") }.joinToString(" · ")
}

@Composable
private fun WaistMeasurementHelp(''','replace culinary settings UI')
write(p,s)

print('Phase 2 production migration prepared')
