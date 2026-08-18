from pathlib import Path
import re

ROOT = Path('.')

def replace_once(path, old, new):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one occurrence, got {count}: {old[:100]!r}')
    path.write_text(text.replace(old, new, 1))

def regex_once(path, pattern, replacement):
    text = path.read_text()
    new, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f'{path}: expected one regex occurrence, got {count}: {pattern[:100]!r}')
    path.write_text(new)

# ---------------------------------------------------------------------------
# 1) Preserve catalogue portion policy on Food and through persistence.
# ---------------------------------------------------------------------------
models = ROOT / 'app/src/main/java/es/david/rumbo/model/Models.kt'
replace_once(
    models,
    '    val culinaryRoles: Set<String> = emptySet()\n) {',
    '    val culinaryRoles: Set<String> = emptySet(),\n'
    '    val catalogPreferredGrams: Double? = null,\n'
    '    val catalogMinimumGrams: Double? = null,\n'
    '    val catalogMaximumGrams: Double? = null\n'
    ') {'
)
replace_once(
    models,
    '        culinaryRoles.all { it.length in 1..80 } &&\n        links.size <= 10 &&',
    '        culinaryRoles.all { it.length in 1..80 } &&\n'
    '        listOf(catalogPreferredGrams, catalogMinimumGrams, catalogMaximumGrams).all {\n'
    '            it == null || it in 0.1..5000.0\n'
    '        } &&\n'
    '        (catalogPreferredGrams == null || catalogMinimumGrams == null ||\n'
    '            catalogMinimumGrams <= catalogPreferredGrams) &&\n'
    '        (catalogPreferredGrams == null || catalogMaximumGrams == null ||\n'
    '            catalogPreferredGrams <= catalogMaximumGrams) &&\n'
    '        links.size <= 10 &&'
)

catalog = ROOT / 'app/src/main/java/es/david/rumbo/data/catalog/CatalogModels.kt'
replace_once(
    catalog,
    '            culinaryRoles = classification.culinaryRoles\n        ).takeIf',
    '            culinaryRoles = classification.culinaryRoles,\n'
    '            catalogPreferredGrams = classification.preferredGrams,\n'
    '            catalogMinimumGrams = classification.minimumGrams,\n'
    '            catalogMaximumGrams = classification.maximumGrams\n'
    '        ).takeIf'
)

repo = ROOT / 'app/src/main/java/es/david/rumbo/data/AppRepository.kt'
replace_once(
    repo,
    '                put("culinaryRoles", JSONArray(food.culinaryRoles.toList()))\n',
    '                put("culinaryRoles", JSONArray(food.culinaryRoles.toList()))\n'
    '                putNullable("catalogPreferredGrams", food.catalogPreferredGrams)\n'
    '                putNullable("catalogMinimumGrams", food.catalogMinimumGrams)\n'
    '                putNullable("catalogMaximumGrams", food.catalogMaximumGrams)\n'
)
replace_once(
    repo,
    '                    culinaryRoles = item.optJSONArray("culinaryRoles")?.let { values ->\n'
    '                        buildSet { for (i in 0 until values.length()) add(values.getString(i)) }\n'
    '                    } ?: baseFoodsById[item.getLong("id")]?.culinaryRoles.orEmpty()\n',
    '                    culinaryRoles = item.optJSONArray("culinaryRoles")?.let { values ->\n'
    '                        buildSet { for (i in 0 until values.length()) add(values.getString(i)) }\n'
    '                    } ?: baseFoodsById[item.getLong("id")]?.culinaryRoles.orEmpty(),\n'
    '                    catalogPreferredGrams = item.optionalDouble("catalogPreferredGrams")\n'
    '                        ?: baseFoodsById[item.getLong("id")]?.catalogPreferredGrams,\n'
    '                    catalogMinimumGrams = item.optionalDouble("catalogMinimumGrams")\n'
    '                        ?: baseFoodsById[item.getLong("id")]?.catalogMinimumGrams,\n'
    '                    catalogMaximumGrams = item.optionalDouble("catalogMaximumGrams")\n'
    '                        ?: baseFoodsById[item.getLong("id")]?.catalogMaximumGrams\n'
)

# ---------------------------------------------------------------------------
# 2) Canonical hard culinary policy. The provisional SQLite publishes roles
#    and portions, not relation tables, so relations are the versioned app
#    policy from the agreed specification and operate on catalogue roles.
# ---------------------------------------------------------------------------
culinary = ROOT / 'app/src/main/java/es/david/rumbo/logic/CulinaryPolicy.kt'
culinary.write_text('''package es.david.rumbo.logic

import es.david.rumbo.model.CulinaryPolicyOverride
import es.david.rumbo.model.CulinaryType
import es.david.rumbo.model.Food
import es.david.rumbo.model.PlanningRule

enum class CulinaryRole(val label: String) {
    STARCH_BASE("Base de hidratos · máximo una"),
    BREAKFAST_CEREAL("Cereal de desayuno · máximo uno"),
    LIQUID_OR_CREAMY_BASE("Base líquida o cremosa"),
    DEPENDENT_PREPARATION("Necesita una base líquida o cremosa"),
    PRIMARY_PROTEIN("Proteína principal · máximo una"),
    CULINARY_FAT("Grasa culinaria")
}

data class CulinaryTypePolicy(
    val roles: Set<CulinaryRole> = emptySet(),
    val preferredGrams: Double? = null,
    val minimumGrams: Double? = null,
    val maximumGrams: Double? = null,
    val standaloneAllowed: Boolean = true
)

enum class CanonicalCulinaryViolationKind {
    REQUIRE,
    MAX_CARDINALITY,
    NOT_SOLO
}

data class CanonicalCulinaryViolation(
    val kind: CanonicalCulinaryViolationKind,
    val role: String,
    val requiredRole: String? = null,
    val maximum: Int? = null
)

/**
 * Shared culinary policy for evaluator and generator.
 *
 * Catalogue foods expose their multiple culinary roles plus the published
 * preferred/minimum/maximum portion. The current provisional SQLite does not yet
 * publish relation rows, therefore REQUIRE/cardinality/no-solo rules remain this
 * explicit versioned policy and are evaluated against the real catalogue roles.
 * Legacy type roles remain only as a compatibility fallback for non-catalogue food.
 */
object CulinaryPolicy {
    private val policies = mapOf(
        CulinaryType.UNKNOWN to CulinaryTypePolicy(),
        CulinaryType.MILK_BASE to CulinaryTypePolicy(
            setOf(CulinaryRole.LIQUID_OR_CREAMY_BASE), 250.0, 150.0, 350.0
        ),
        CulinaryType.CREAMY_BASE to CulinaryTypePolicy(
            setOf(CulinaryRole.LIQUID_OR_CREAMY_BASE), 150.0, 100.0, 300.0
        ),
        CulinaryType.BREAKFAST_CEREAL to CulinaryTypePolicy(
            setOf(CulinaryRole.BREAKFAST_CEREAL), 50.0, 25.0, 80.0
        ),
        CulinaryType.PROTEIN_POWDER to CulinaryTypePolicy(
            setOf(CulinaryRole.DEPENDENT_PREPARATION), 30.0, 20.0, 50.0
        ),
        CulinaryType.DRY_RICE to CulinaryTypePolicy(
            setOf(CulinaryRole.STARCH_BASE), 80.0, 40.0, 120.0
        ),
        CulinaryType.DRY_PASTA to CulinaryTypePolicy(
            setOf(CulinaryRole.STARCH_BASE), 80.0, 40.0, 120.0
        ),
        CulinaryType.FRESH_STARCH to CulinaryTypePolicy(
            setOf(CulinaryRole.STARCH_BASE), 250.0, 100.0, 400.0
        ),
        CulinaryType.BREAD to CulinaryTypePolicy(preferredGrams = 70.0, minimumGrams = 30.0, maximumGrams = 150.0),
        CulinaryType.MAIN_MEAT to CulinaryTypePolicy(
            setOf(CulinaryRole.PRIMARY_PROTEIN), 150.0, 75.0, 250.0
        ),
        CulinaryType.MAIN_FISH to CulinaryTypePolicy(
            setOf(CulinaryRole.PRIMARY_PROTEIN), 170.0, 80.0, 300.0
        ),
        CulinaryType.MAIN_EGG to CulinaryTypePolicy(
            setOf(CulinaryRole.PRIMARY_PROTEIN), 120.0, 50.0, 240.0
        ),
        CulinaryType.VEGETABLE to CulinaryTypePolicy(preferredGrams = 200.0, minimumGrams = 75.0, maximumGrams = 400.0),
        CulinaryType.FRUIT to CulinaryTypePolicy(preferredGrams = 150.0, minimumGrams = 75.0, maximumGrams = 300.0),
        CulinaryType.CULINARY_OIL to CulinaryTypePolicy(
            setOf(CulinaryRole.CULINARY_FAT), 10.0, 5.0, 15.0
        ),
        CulinaryType.FAT_COMPLEMENT to CulinaryTypePolicy(preferredGrams = 30.0, minimumGrams = 10.0, maximumGrams = 80.0),
        CulinaryType.SAUCE to CulinaryTypePolicy(preferredGrams = 40.0, minimumGrams = 10.0, maximumGrams = 100.0),
        CulinaryType.SNACK_DESSERT to CulinaryTypePolicy(preferredGrams = 40.0, minimumGrams = 15.0, maximumGrams = 100.0),
        CulinaryType.COOKING_INGREDIENT to CulinaryTypePolicy(standaloneAllowed = false)
    )

    private val requirements = mapOf(
        "CEREAL_MIX_IN" to "CEREAL_BASE",
        "POWDER_MIX_IN" to "POWDER_BASE",
        "SPREAD" to "SANDWICH_BASE",
        "SANDWICH_FILLING" to "SANDWICH_BASE"
    )

    private val noSoloRoles = setOf(
        "TOPPING", "SAUCE_DRESSING", "COOKING_MEDIUM", "BINDER", "COATING", "SEASONING"
    )

    private val maximumRoleCounts = mapOf(
        "PLATE_CENTER" to 1,
        "PLATE_BASE" to 1
    )

    @Volatile
    private var profileOverrides: Map<CulinaryType, CulinaryTypePolicy> = emptyMap()

    fun configure(overrides: List<CulinaryPolicyOverride>) {
        profileOverrides = overrides.associate { override ->
            override.culinaryType to CulinaryTypePolicy(
                roles = override.roles.mapNotNullTo(mutableSetOf()) { name ->
                    runCatching { CulinaryRole.valueOf(name) }.getOrNull()
                },
                preferredGrams = override.preferredGrams,
                minimumGrams = override.minimumGrams,
                maximumGrams = override.maximumGrams,
                standaloneAllowed = override.standaloneAllowed
            )
        }
    }

    fun defaultPolicy(type: CulinaryType): CulinaryTypePolicy = policies.getValue(type)

    fun policy(food: Food): CulinaryTypePolicy {
        profileOverrides[food.culinaryType]?.let { return it }
        val base = defaultPolicy(food.culinaryType)
        return base.copy(
            preferredGrams = food.catalogPreferredGrams ?: base.preferredGrams,
            minimumGrams = food.catalogMinimumGrams ?: base.minimumGrams,
            maximumGrams = food.catalogMaximumGrams ?: base.maximumGrams
        )
    }

    /** Legacy compatibility roles; catalogue roles are evaluated separately. */
    fun roles(food: Food): Set<CulinaryRole> =
        if (food.culinaryRoles.isNotEmpty()) emptySet() else policy(food).roles

    fun canonicalRoles(food: Food): Set<String> = food.culinaryRoles.mapTo(linkedSetOf()) { it.uppercase() }

    fun requiredCompanionRoles(food: Food): Set<String> =
        canonicalRoles(food).mapNotNullTo(linkedSetOf()) { requirements[it] }

    fun providesRole(food: Food, role: String): Boolean = role.uppercase() in canonicalRoles(food)

    fun missingRequiredRoles(foods: List<Food>): Set<String> {
        val present = foods.flatMapTo(linkedSetOf())(::canonicalRoles)
        return present.mapNotNullTo(linkedSetOf()) { requirements[it] }.filterNotTo(linkedSetOf()) { it in present }
    }

    fun onlyNoSoloRoles(foods: List<Food>): Boolean {
        if (foods.isEmpty()) return false
        val roleSets = foods.map(::canonicalRoles)
        if (roleSets.any { it.isEmpty() }) return false // legacy item can anchor a mixed meal
        return roleSets.flatMapTo(linkedSetOf()) { it }.all { it in noSoloRoles }
    }

    fun hardViolations(foods: List<Food>): List<CanonicalCulinaryViolation> = buildList {
        val present = foods.flatMapTo(linkedSetOf())(::canonicalRoles)
        present.forEach { role ->
            val required = requirements[role]
            if (required != null && required !in present) {
                add(CanonicalCulinaryViolation(CanonicalCulinaryViolationKind.REQUIRE, role, required))
            }
        }
        maximumRoleCounts.forEach { (role, maximum) ->
            val count = foods.count { role in canonicalRoles(it) }
            if (count > maximum) {
                add(CanonicalCulinaryViolation(
                    CanonicalCulinaryViolationKind.MAX_CARDINALITY, role, maximum = maximum
                ))
            }
        }
        if (onlyNoSoloRoles(foods)) {
            add(CanonicalCulinaryViolation(CanonicalCulinaryViolationKind.NOT_SOLO, "NO_SOLO"))
        }
    }

    fun hardMealValid(foods: List<Food>): Boolean = hardViolations(foods).isEmpty()

    fun standaloneAllowed(food: Food): Boolean = when {
        food.culinaryRoles.isNotEmpty() -> !onlyNoSoloRoles(listOf(food)) && requiredCompanionRoles(food).isEmpty()
        else -> policy(food).standaloneAllowed
    }

    fun addresses(need: CulinaryNeed, food: Food): Boolean {
        if (food.culinaryType !in need.acceptedTypes) return false
        val servingFactor = (policy(food).preferredGrams ?: 100.0) / 100.0
        return when (need.kind) {
            CulinaryNeedKind.COMPANION_BASE -> true
            CulinaryNeedKind.STARCH_BASE ->
                food.category == es.david.rumbo.model.FoodCategory.CARBOHYDRATE &&
                    (food.carbohydrateGrams ?: 0.0) * servingFactor >= 25.0
            CulinaryNeedKind.PRIMARY_PROTEIN ->
                food.category == es.david.rumbo.model.FoodCategory.PROTEIN &&
                    (food.proteinGrams ?: 0.0) * servingFactor >= 20.0
            CulinaryNeedKind.FAT_COMPLEMENT ->
                food.category == es.david.rumbo.model.FoodCategory.FAT &&
                    (food.fatGrams ?: 0.0) * servingFactor >= 8.0
        }
    }

    fun applyPortion(rule: PlanningRule, food: Food): PlanningRule {
        val policy = policy(food)
        val preferred = policy.preferredGrams ?: return rule
        val minimum = policy.minimumGrams ?: preferred * 0.5
        val maximum = policy.maximumGrams ?: preferred * 1.5
        return rule.copy(
            preferredGrams = preferred,
            minimumFactor = minimum / preferred,
            maximumFactor = maximum / preferred
        )
    }
}
''')

# ---------------------------------------------------------------------------
# 3) Shared constraint model proves missing companions using canonical roles.
# ---------------------------------------------------------------------------
contract = ROOT / 'app/src/main/java/es/david/rumbo/logic/MenuConstraintContract.kt'
replace_once(
    contract,
    '                    foodsById[it.itemId]?.hasComparableNutrition() == true &&\n'
    '                    foodsById[it.itemId]?.let(CulinaryPolicy::standaloneAllowed) != false\n',
    '                    foodsById[it.itemId]?.hasComparableNutrition() == true &&\n'
    '                    foodsById[it.itemId]?.let { food ->\n'
    '                        food.culinaryRoles.isNotEmpty() || CulinaryPolicy.standaloneAllowed(food)\n'
    '                    } != false\n'
)
regex_once(
    contract,
    r'''                    // This is a proof, not a heuristic: an ALWAYS dependent item must.*?                    \}\n                \}\n            \}\n            return MenuConstraintModel\(''',
    '''                    // Proof boundary: mandatory catalogue roles with REQUIRE relations must\n'
    '                    // have a compatible role available in the same meal.\n'
    '                    val mandatoryWithRequirements = mealRules.filter { rule ->\n'
    '                        rule.frequency == PlanningFrequency.ALWAYS &&\n'
    '                            foodsById[rule.itemId]?.let(CulinaryPolicy::requiredCompanionRoles)\n'
    '                                .orEmpty().isNotEmpty()\n'
    '                    }\n'
    '                    mandatoryWithRequirements.forEach { requiredRule ->\n'
    '                        val food = foodsById[requiredRule.itemId] ?: return@forEach\n'
    '                        val missing = CulinaryPolicy.requiredCompanionRoles(food).filterNot { requiredRole ->\n'
    '                            mealRules.any { candidate ->\n'
    '                                foodsById[candidate.itemId]?.let {\n'
    '                                    CulinaryPolicy.providesRole(it, requiredRole)\n'
    '                                } == true\n'
    '                            }\n'
    '                        }\n'
    '                        if (missing.isNotEmpty()) {\n'
    '                            add(ConstraintViolation(\n'
    '                                ConstraintViolationKind.MISSING_REQUIRED_COMPANION,\n'
    '                                "Hay un alimento obligatorio que requiere ${missing.joinToString()} en " +\n'
    '                                    mealType.label.lowercase() + ", pero no existe ninguna opción programada.",\n'
    '                                mealType,\n'
    '                                setOf(requiredRule.itemId)\n'
    '                            ))\n'
    '                        }\n'
    '                    }\n'
    '                }\n'
    '            }\n'
    '            return MenuConstraintModel('''
)

# ---------------------------------------------------------------------------
# 4) Generator consumes the same canonical hard policy.
# ---------------------------------------------------------------------------
generator = ROOT / 'app/src/main/java/es/david/rumbo/logic/WeeklyMenuGenerator.kt'
replace_once(
    generator,
    '            it.itemKind == PlannedItemKind.FOOD && it.isActive &&\n'
    '                foodsById[it.itemId]?.let(CulinaryPolicy::standaloneAllowed) != false\n',
    '            it.itemKind == PlannedItemKind.FOOD && it.isActive &&\n'
    '                foodsById[it.itemId]?.let { food ->\n'
    '                    food.culinaryRoles.isNotEmpty() || CulinaryPolicy.standaloneAllowed(food)\n'
    '                } != false\n'
)
replace_once(
    generator,
    '        if (hasUnmetDependency(chosen, foodsById, dishesById)) {\n'
    '            throw PlanningConflictException(\n'
    '                "Hay un alimento que necesita leche, bebida vegetal, yogur o una base similar " +\n'
    '                    "en ${slot.mealType.label.lowercase()}."\n'
    '            )\n'
    '        }\n',
    '        if (!isHardSelectionValid(chosen, foodsById, dishesById)) {\n'
    '            throw PlanningConflictException(\n'
    '                "La combinación infringe una relación culinaria obligatoria en " +\n'
    '                    slot.mealType.label.lowercase() + "."\n'
    '            )\n'
    '        }\n'
)
regex_once(
    generator,
    r'''    private fun culinaryAddition\(.*?\n    private fun hasCompatibleExclusiveRoles\(''',
    '''    private fun culinaryAddition(\n'
    '        candidate: PlanningRule,\n'
    '        chosen: List<PlanningRule>,\n'
    '        eligible: List<PlanningRule>,\n'
    '        maximumItems: Int,\n'
    '        slot: PlanningSlot,\n'
    '        foodsById: Map<Long, Food>,\n'
    '        dishesById: Map<Long, Dish>,\n'
    '        recommendation: Recommendation,\n'
    '        mealShare: Double\n'
    '    ): List<PlanningRule>? {\n'
    '        val additions = mutableListOf(candidate)\n'
    '        while (true) {\n'
    '            val direct = chosen + additions\n'
    '            if (!hasCompatibleExclusiveRoles(direct, foodsById, dishesById)) return null\n'
    '            val unresolvedDependency = hasUnmetDependency(direct, foodsById, dishesById)\n'
    '            val needsAnchor = onlyNoSoloSelection(direct, foodsById, dishesById)\n'
    '            if (!unresolvedDependency && !needsAnchor) return additions\n'
    '            if (direct.size >= maximumItems) return null\n'
    '\n'
    '            val missingRoles = CulinaryPolicy.missingRequiredRoles(\n'
    '                direct.resolveFoods(foodsById, dishesById)\n'
    '            )\n'
    '            val companions = eligible.filter { companion ->\n'
    '                companion.itemKind == PlannedItemKind.FOOD &&\n'
    '                    direct.none { it.sameItem(companion) || it.overlaps(companion, dishesById) } &&\n'
    '                    (missingRoles.isEmpty() || foodsById[companion.itemId]?.let { food ->\n'
    '                        missingRoles.any { CulinaryPolicy.providesRole(food, it) }\n'
    '                    } == true) &&\n'
    '                    hasCompatibleExclusiveRoles(direct + companion, foodsById, dishesById)\n'
    '            }\n'
    '            val companion = companions.minByOrNull {\n'
    '                combinationError(\n'
    '                    direct + it, slot, foodsById, dishesById, recommendation, mealShare\n'
    '                )\n'
    '            } ?: return null\n'
    '            additions += companion\n'
    '        }\n'
    '    }\n\n'
    '    private fun hasCompatibleExclusiveRoles('''
)
regex_once(
    generator,
    r'''    private fun hasCompatibleExclusiveRoles\(.*?\n    private fun resolveFixedSlots\(''',
    '''    private fun hasCompatibleExclusiveRoles(\n'
    '        rules: List<PlanningRule>,\n'
    '        foodsById: Map<Long, Food>,\n'
    '        dishesById: Map<Long, Dish>\n'
    '    ): Boolean {\n'
    '        val foods = rules.resolveFoods(foodsById, dishesById)\n'
    '        val canonicalCardinalityOk = CulinaryPolicy.hardViolations(foods).none {\n'
    '            it.kind == CanonicalCulinaryViolationKind.MAX_CARDINALITY\n'
    '        }\n'
    '        val legacyOk = listOf(\n'
    '            CulinaryRole.STARCH_BASE,\n'
    '            CulinaryRole.BREAKFAST_CEREAL,\n'
    '            CulinaryRole.PRIMARY_PROTEIN\n'
    '        ).all { exclusiveRole ->\n'
    '            rules.count { exclusiveRole in it.roles(foodsById, dishesById) } <= 1\n'
    '        }\n'
    '        return canonicalCardinalityOk && legacyOk\n'
    '    }\n'
    '\n'
    '    private fun hasUnmetDependency(\n'
    '        rules: List<PlanningRule>,\n'
    '        foodsById: Map<Long, Food>,\n'
    '        dishesById: Map<Long, Dish>\n'
    '    ): Boolean {\n'
    '        val foods = rules.resolveFoods(foodsById, dishesById)\n'
    '        if (CulinaryPolicy.missingRequiredRoles(foods).isNotEmpty()) return true\n'
    '        val roles = rules.map { it.roles(foodsById, dishesById) }\n'
    '        val needsBase = roles.any {\n'
    '            CulinaryRole.DEPENDENT_PREPARATION in it || CulinaryRole.BREAKFAST_CEREAL in it\n'
    '        }\n'
    '        val hasBase = roles.any { CulinaryRole.LIQUID_OR_CREAMY_BASE in it }\n'
    '        return needsBase && !hasBase\n'
    '    }\n'
    '\n'
    '    private fun onlyNoSoloSelection(\n'
    '        rules: List<PlanningRule>,\n'
    '        foodsById: Map<Long, Food>,\n'
    '        dishesById: Map<Long, Dish>\n'
    '    ): Boolean = CulinaryPolicy.onlyNoSoloRoles(rules.resolveFoods(foodsById, dishesById))\n'
    '\n'
    '    private fun isHardSelectionValid(\n'
    '        rules: List<PlanningRule>,\n'
    '        foodsById: Map<Long, Food>,\n'
    '        dishesById: Map<Long, Dish>\n'
    '    ): Boolean = hasCompatibleExclusiveRoles(rules, foodsById, dishesById) &&\n'
    '        !hasUnmetDependency(rules, foodsById, dishesById) &&\n'
    '        !onlyNoSoloSelection(rules, foodsById, dishesById)\n'
    '\n'
    '    private fun List<PlanningRule>.resolveFoods(\n'
    '        foodsById: Map<Long, Food>,\n'
    '        dishesById: Map<Long, Dish>\n'
    '    ): List<Food> = flatMap { rule ->\n'
    '        when (rule.itemKind) {\n'
    '            PlannedItemKind.FOOD -> listOfNotNull(foodsById[rule.itemId])\n'
    '            PlannedItemKind.DISH -> dishesById[rule.itemId]?.ingredients.orEmpty()\n'
    '                .mapNotNull { foodsById[it.foodId] }\n'
    '        }\n'
    '    }.distinctBy { it.id }\n'
    '\n'
    '    private fun PlanningRule.roles(\n'
    '        foodsById: Map<Long, Food>,\n'
    '        dishesById: Map<Long, Dish>\n'
    '    ): Set<CulinaryRole> = when (itemKind) {\n'
    '        PlannedItemKind.FOOD -> foodsById[itemId]?.let(CulinaryPolicy::roles).orEmpty()\n'
    '        PlannedItemKind.DISH -> dishesById[itemId]?.ingredients\n'
    '            ?.mapNotNull { foodsById[it.foodId] }\n'
    '            ?.flatMapTo(mutableSetOf(), CulinaryPolicy::roles)\n'
    '            .orEmpty()\n'
    '    }\n'
    '\n'
    '    fun isCulinarilyValid(\n'
    '        meals: List<PlannedMeal>,\n'
    '        foodsById: Map<Long, Food>,\n'
    '        dishesById: Map<Long, Dish>\n'
    '    ): Boolean = WeekDay.entries.all { day ->\n'
    '        meals.filter { day in it.days }.all { meal ->\n'
    '            val rules = meal.items.map {\n'
    '                PlanningRule(\n'
    '                    itemKind = PlannedItemKind.FOOD,\n'
    '                    itemId = it.foodId,\n'
    '                    allowedMealTypes = setOf(meal.type),\n'
    '                    preferredGrams = meal.resolvedGrams(it, day)\n'
    '                )\n'
    '            } + meal.dishes.map {\n'
    '                PlanningRule(\n'
    '                    itemKind = PlannedItemKind.DISH,\n'
    '                    itemId = it.dishId,\n'
    '                    allowedMealTypes = setOf(meal.type),\n'
    '                    preferredGrams = meal.resolvedGrams(it, day)\n'
    '                )\n'
    '            }\n'
    '            isHardSelectionValid(rules, foodsById, dishesById)\n'
    '        }\n'
    '    }\n\n'
    '    private fun resolveFixedSlots('''
)

# ---------------------------------------------------------------------------
# 5) Remove the obsolete "Alimentos y platos" screen completely.
# ---------------------------------------------------------------------------
app = ROOT / 'app/src/main/java/es/david/rumbo/ui/App.kt'
text = app.read_text()
text = text.replace('    FOODS("Alimentos y platos", Icons.Default.Search, false),\n', '')
text = text.replace('                        Screen.FOODS ->\n                            Text("Alimentos y platos", fontWeight = FontWeight.SemiBold)\n', '')
# Saved-state compatibility: an installation that was literally on FOODS must recover to HOME.
text = text.replace(
    '    val screen = Screen.valueOf(screenName)\n',
    '    val screen = Screen.entries.firstOrNull { it.name == screenName } ?: Screen.HOME\n'
    '    LaunchedEffect(screenName) {\n'
    '        if (Screen.entries.none { it.name == screenName }) screenName = Screen.HOME.name\n'
    '    }\n'
)
# Existing entry point now requests the canonical home search directly.
text = text.replace(
    '                    onOpenFoods = { screenName = Screen.FOODS.name },',
    '                    onOpenFoods = {\n'
    '                        catalogRetailerFilter = null\n'
    '                        catalogNutritionalRoleFilter = null\n'
    '                        catalogCulinaryRoleFilter = null\n'
    '                        catalogSearchRequest += 1\n'
    '                        screenName = Screen.HOME.name\n'
    '                    },'
)
# All fallback destinations formerly pointing at the deleted screen now return home.
text = text.replace('Screen.FOODS.name', 'Screen.HOME.name')
# Remove route branch for the obsolete screen.
text, route_count = re.subn(
    r'''\n                screen == Screen\.FOODS -> FoodDishCatalogScreen\(.*?\n                screen == Screen\.ADD_FOOD ->''',
    '\n                screen == Screen.ADD_FOOD ->',
    text,
    count=1,
    flags=re.S
)
if route_count not in (0, 1):
    raise SystemExit(f'Unexpected obsolete route count {route_count}')
# It may already have become HOME after global replacement; remove that exact generated legacy branch too.
text, route2_count = re.subn(
    r'''\n                screen == Screen\.HOME -> FoodDishCatalogScreen\(.*?\n                screen == Screen\.ADD_FOOD ->''',
    '\n                screen == Screen.ADD_FOOD ->',
    text,
    count=1,
    flags=re.S
)
# Remove composable itself.
text, screen_count = re.subn(
    r'''@Composable\nprivate fun FoodDishCatalogScreen\(.*?\n\}\n\n@Composable\nprivate fun CatalogCanonicalFilterRow''',
    '@Composable\nprivate fun CatalogCanonicalFilterRow',
    text,
    count=1,
    flags=re.S
)
if screen_count != 1:
    raise SystemExit(f'Expected obsolete FoodDishCatalogScreen once, got {screen_count}')
# Remove obsolete filter helpers that were only used by that screen.
text = text.replace('private enum class CatalogFilter { ALL, FOODS, DISHES }\n\n', '')
text, _ = re.subn(
    r'''@Composable\nprivate fun CatalogFilterChips\(.*?\n@Composable\nprivate fun CatalogCanonicalFilterRow''',
    '@Composable\nprivate fun CatalogCanonicalFilterRow',
    text,
    count=1,
    flags=re.S
)
app.write_text(text)

# ---------------------------------------------------------------------------
# 6) Tests: catalogue portions + canonical hard rules + shared proof.
# ---------------------------------------------------------------------------
test_dir = ROOT / 'app/src/test/java/es/david/rumbo/logic'
test_dir.mkdir(parents=True, exist_ok=True)
(test_dir / 'CanonicalCulinaryPolicyTest.kt').write_text('''package es.david.rumbo.logic

import es.david.rumbo.model.CulinaryType
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.WeekDay
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CanonicalCulinaryPolicyTest {
    @Test
    fun sandwichFillingRequiresSandwichBase() {
        val ham = food(1, setOf("SANDWICH_FILLING"))
        val bread = food(2, setOf("SANDWICH_BASE", "STANDALONE"))
        assertFalse(CulinaryPolicy.hardMealValid(listOf(ham)))
        assertTrue(CulinaryPolicy.hardMealValid(listOf(ham, bread)))
        assertEquals(setOf("SANDWICH_BASE"), CulinaryPolicy.missingRequiredRoles(listOf(ham)))
    }

    @Test
    fun powderAndCerealDependenciesUseTheirOwnCanonicalBases() {
        val cereal = food(1, setOf("CEREAL_MIX_IN"))
        val powder = food(2, setOf("POWDER_MIX_IN"))
        val cerealBase = food(3, setOf("CEREAL_BASE", "STANDALONE"))
        val powderBase = food(4, setOf("POWDER_BASE", "BEVERAGE"))
        assertFalse(CulinaryPolicy.hardMealValid(listOf(cereal, powder, cerealBase)))
        assertTrue(CulinaryPolicy.hardMealValid(listOf(cereal, powder, cerealBase, powderBase)))
    }

    @Test
    fun plateCenterAndBaseCardinalityIsHard() {
        val first = food(1, setOf("PLATE_CENTER"))
        val second = food(2, setOf("PLATE_CENTER"))
        assertFalse(CulinaryPolicy.hardMealValid(listOf(first, second)))
        assertTrue(CulinaryPolicy.hardMealValid(listOf(first)))
    }

    @Test
    fun toppingCannotFormMealAloneButCanAccompanyAnchor() {
        val topping = food(1, setOf("TOPPING"))
        val anchor = food(2, setOf("PLATE_CENTER"))
        assertFalse(CulinaryPolicy.hardMealValid(listOf(topping)))
        assertTrue(CulinaryPolicy.hardMealValid(listOf(topping, anchor)))
    }

    @Test
    fun publishedCataloguePortionOverridesLegacyTypePortion() {
        val food = food(1, setOf("PLATE_CENTER")).copy(
            culinaryType = CulinaryType.MAIN_MEAT,
            catalogPreferredGrams = 135.0,
            catalogMinimumGrams = 90.0,
            catalogMaximumGrams = 180.0
        )
        val policy = CulinaryPolicy.policy(food)
        assertEquals(135.0, policy.preferredGrams!!, 0.001)
        assertEquals(90.0, policy.minimumGrams!!, 0.001)
        assertEquals(180.0, policy.maximumGrams!!, 0.001)
    }

    @Test
    fun generatorValidationUsesCanonicalRoles() {
        val ham = food(1, setOf("SANDWICH_FILLING"))
        val bread = food(2, setOf("SANDWICH_BASE", "STANDALONE"))
        val invalid = listOf(meal(listOf(ham)))
        val valid = listOf(meal(listOf(ham, bread)))
        assertFalse(WeeklyMenuGenerator.isCulinarilyValid(invalid, mapOf(1L to ham), emptyMap()))
        assertTrue(WeeklyMenuGenerator.isCulinarilyValid(valid, mapOf(1L to ham, 2L to bread), emptyMap()))
    }

    private fun food(id: Long, roles: Set<String>) = Food(
        id = id,
        name = "Food $id",
        category = FoodCategory.OTHER,
        calories = 100.0,
        fatGrams = 5.0,
        carbohydrateGrams = 10.0,
        proteinGrams = 10.0,
        fiberGrams = 1.0,
        culinaryRoles = roles
    )

    private fun meal(foods: List<Food>) = PlannedMeal(
        id = 1,
        type = MealType.LUNCH,
        days = WeekDay.entries.toSet(),
        items = foods.map { PlannedFood(it.id, 100.0) }
    )
}
''')

# Extend adapter test with published portion mapping.
adapter_test = ROOT / 'app/src/test/java/es/david/rumbo/data/catalog/CatalogFoodAdapterTest.kt'
replace_once(
    adapter_test,
    '        assertEquals(CulinaryType.MILK_BASE, CatalogFoodAdapter.toFood(product)!!.culinaryType)\n',
    '        val food = CatalogFoodAdapter.toFood(product)!!\n'
    '        assertEquals(CulinaryType.MILK_BASE, food.culinaryType)\n'
    '        assertEquals(100.0, food.catalogPreferredGrams!!, 0.001)\n'
    '        assertEquals(50.0, food.catalogMinimumGrams!!, 0.001)\n'
    '        assertEquals(200.0, food.catalogMaximumGrams!!, 0.001)\n'
)

# Add a structural proof case to the shared contract test.
contract_test = ROOT / 'app/src/test/java/es/david/rumbo/logic/MenuConstraintContractTest.kt'
insert = '''
    @Test
    fun mandatorySandwichFillingWithoutBaseIsProvenInsufficient() {
        val filling = testFood(31).copy(culinaryRoles = setOf("SANDWICH_FILLING"))
        val rule = testRule(31).copy(
            frequency = PlanningFrequency.ALWAYS,
            allowedMealTypes = setOf(MealType.LUNCH)
        )
        val constraints = MenuConstraintModel.fromLegacyData(
            rules = listOf(rule),
            foodsById = mapOf(filling.id to filling),
            mealShares = MealType.entries.associateWith { if (it == MealType.LUNCH) 1.0 else 0.0 }
        )
        assertTrue(constraints.structuralViolations.any {
            it.kind == ConstraintViolationKind.MISSING_REQUIRED_COMPANION &&
                it.mealType == MealType.LUNCH && filling.id in it.itemIds
        })
    }

'''
marker = '    @Test\n    fun '
text = contract_test.read_text()
pos = text.find(marker)
if pos < 0:
    raise SystemExit('No test marker in MenuConstraintContractTest')
contract_test.write_text(text[:pos] + insert + text[pos:])

print('Applied canonical culinary policy and removed obsolete catalogue screen')
