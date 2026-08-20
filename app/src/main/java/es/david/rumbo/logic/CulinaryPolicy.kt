package es.david.rumbo.logic

import es.david.rumbo.model.CulinaryPolicyOverride
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlanningRule

enum class CulinaryRole(val label: String) {
    PLATE_CENTER("Centro del plato"),
    PLATE_BASE("Base del plato"),
    SIDE("Acompañamiento"),
    TOPPING("Topping"),
    SAUCE_DRESSING("Salsa o aliño"),
    CEREAL_BASE("Base para cereal"),
    CEREAL_MIX_IN("Cereal para mezclar"),
    POWDER_BASE("Base para polvo"),
    POWDER_MIX_IN("Polvo para mezclar"),
    SANDWICH_BASE("Base de bocadillo"),
    SANDWICH_FILLING("Relleno de bocadillo"),
    SPREAD("Untable"),
    COOKING_MEDIUM("Medio de cocción"),
    BINDER("Ligante"),
    COATING("Rebozado"),
    SEASONING("Condimento"),
    STANDALONE("Puede tomarse solo"),
    BEVERAGE("Bebida"),
    DESSERT("Postre")
}

data class CulinaryRolePolicy(
    val preferredGrams: Double? = null,
    val minimumGrams: Double? = null,
    val maximumGrams: Double? = null,
    val standaloneAllowed: Boolean = true,
    val requiredRoles: Set<CulinaryRole> = emptySet(),
    val requiredAnyOfRoles: Set<CulinaryRole> = emptySet(),
    val maxPerMeal: Int? = null,
    val suggestedMealTypes: Set<MealType> = MealType.entries.toSet()
)

/** Canonical culinary policy. Products only store the functional roles they can perform. */
object CulinaryPolicy {
    private val mealRestrictedRoles = setOf(CulinaryRole.BINDER, CulinaryRole.COATING)
    private val policies = mapOf(
        CulinaryRole.PLATE_CENTER to CulinaryRolePolicy(150.0, 75.0, 300.0, maxPerMeal = 1),
        CulinaryRole.PLATE_BASE to CulinaryRolePolicy(100.0, 40.0, 300.0, maxPerMeal = 1),
        CulinaryRole.SIDE to CulinaryRolePolicy(150.0, 50.0, 300.0),
        CulinaryRole.TOPPING to CulinaryRolePolicy(20.0, 5.0, 60.0, standaloneAllowed = false),
        CulinaryRole.SAUCE_DRESSING to CulinaryRolePolicy(30.0, 5.0, 100.0, standaloneAllowed = false),
        CulinaryRole.CEREAL_BASE to CulinaryRolePolicy(200.0, 100.0, 350.0),
        CulinaryRole.CEREAL_MIX_IN to CulinaryRolePolicy(
            50.0, 25.0, 80.0, standaloneAllowed = false,
            requiredRoles = setOf(CulinaryRole.CEREAL_BASE)
        ),
        CulinaryRole.POWDER_BASE to CulinaryRolePolicy(250.0, 100.0, 400.0),
        CulinaryRole.POWDER_MIX_IN to CulinaryRolePolicy(
            30.0, 20.0, 50.0, standaloneAllowed = false,
            requiredRoles = setOf(CulinaryRole.POWDER_BASE)
        ),
        CulinaryRole.SANDWICH_BASE to CulinaryRolePolicy(70.0, 30.0, 150.0),
        CulinaryRole.SANDWICH_FILLING to CulinaryRolePolicy(
            60.0, 20.0, 150.0, standaloneAllowed = false,
            requiredRoles = setOf(CulinaryRole.SANDWICH_BASE)
        ),
        CulinaryRole.SPREAD to CulinaryRolePolicy(
            25.0, 5.0, 60.0, standaloneAllowed = false,
            requiredRoles = setOf(CulinaryRole.SANDWICH_BASE)
        ),
        CulinaryRole.COOKING_MEDIUM to CulinaryRolePolicy(10.0, 5.0, 15.0, standaloneAllowed = false),
        CulinaryRole.BINDER to CulinaryRolePolicy(
            20.0, 5.0, 60.0, standaloneAllowed = false,
            requiredAnyOfRoles = setOf(CulinaryRole.PLATE_CENTER, CulinaryRole.PLATE_BASE)
        ),
        CulinaryRole.COATING to CulinaryRolePolicy(
            30.0, 10.0, 80.0, standaloneAllowed = false,
            requiredRoles = setOf(CulinaryRole.PLATE_CENTER)
        ),
        CulinaryRole.SEASONING to CulinaryRolePolicy(3.0, 0.5, 10.0, standaloneAllowed = false),
        CulinaryRole.STANDALONE to CulinaryRolePolicy(100.0, 20.0, 300.0),
        CulinaryRole.BEVERAGE to CulinaryRolePolicy(250.0, 100.0, 500.0),
        CulinaryRole.DESSERT to CulinaryRolePolicy(125.0, 40.0, 250.0)
    )

    private val suggestedMealsByRole: Map<CulinaryRole, Set<MealType>> = mapOf(
        CulinaryRole.CEREAL_BASE to setOf(MealType.BREAKFAST),
        CulinaryRole.CEREAL_MIX_IN to setOf(MealType.BREAKFAST),
        CulinaryRole.POWDER_BASE to setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        CulinaryRole.POWDER_MIX_IN to setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        CulinaryRole.SANDWICH_BASE to setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        CulinaryRole.SANDWICH_FILLING to setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        CulinaryRole.SPREAD to setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        CulinaryRole.BEVERAGE to setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK),
        CulinaryRole.DESSERT to MealType.entries.toSet(),
        CulinaryRole.STANDALONE to MealType.entries.toSet(),
        CulinaryRole.PLATE_CENTER to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.PLATE_BASE to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.SIDE to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.TOPPING to MealType.entries.toSet(),
        CulinaryRole.SAUCE_DRESSING to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.COOKING_MEDIUM to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.BINDER to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.COATING to setOf(MealType.LUNCH, MealType.DINNER),
        CulinaryRole.SEASONING to setOf(MealType.LUNCH, MealType.DINNER)
    )

    @Volatile private var profileOverrides: Map<CulinaryRole, CulinaryRolePolicy> = emptyMap()

    fun configure(overrides: List<CulinaryPolicyOverride>) {
        profileOverrides = overrides.mapNotNull { override ->
            val role = parseRole(override.culinaryRole) ?: return@mapNotNull null
            val base = policies.getValue(role)
            role to base.copy(
                preferredGrams = override.preferredGrams ?: base.preferredGrams,
                minimumGrams = override.minimumGrams ?: base.minimumGrams,
                maximumGrams = override.maximumGrams ?: base.maximumGrams,
                standaloneAllowed = override.standaloneAllowed ?: base.standaloneAllowed
            )
        }.toMap()
    }

    fun defaultPolicy(role: CulinaryRole): CulinaryRolePolicy = policies.getValue(role).copy(
        suggestedMealTypes = suggestedMealsByRole[role] ?: MealType.entries.toSet()
    )
    fun policy(role: CulinaryRole): CulinaryRolePolicy = profileOverrides[role]
        ?.copy(suggestedMealTypes = suggestedMealsByRole[role] ?: MealType.entries.toSet())
        ?: defaultPolicy(role)
    fun parseRole(name: String): CulinaryRole? = CulinaryRole.entries.firstOrNull { it.name == name }

    fun roles(food: Food): Set<CulinaryRole> = food.culinaryRoles.mapNotNullTo(linkedSetOf(), ::parseRole)

    private fun portionRole(rule: PlanningRule, food: Food): CulinaryRole? {
        val available = roles(food)
        if (available.isEmpty()) return null

        // A SIDE+TOPPING product used at lunch/dinner is normally functioning as
        // an accompaniment, not as a garnish. Keep every other multi-role choice
        // on the historic priority for now so this fix does not change unrelated
        // repertoire behaviour while explicit per-occurrence role assignment is built.
        if (
            CulinaryRole.SIDE in available &&
            CulinaryRole.TOPPING in available &&
            rule.allowedMealTypes.any { it == MealType.LUNCH || it == MealType.DINNER }
        ) return CulinaryRole.SIDE

        return available.minByOrNull { role ->
            when (role) {
                CulinaryRole.COOKING_MEDIUM, CulinaryRole.SEASONING, CulinaryRole.TOPPING,
                CulinaryRole.SAUCE_DRESSING, CulinaryRole.SPREAD, CulinaryRole.BINDER,
                CulinaryRole.COATING -> 0
                CulinaryRole.CEREAL_MIX_IN, CulinaryRole.POWDER_MIX_IN,
                CulinaryRole.SANDWICH_FILLING -> 1
                CulinaryRole.PLATE_CENTER, CulinaryRole.PLATE_BASE, CulinaryRole.SIDE -> 2
                CulinaryRole.STANDALONE, CulinaryRole.BEVERAGE, CulinaryRole.DESSERT,
                CulinaryRole.CEREAL_BASE, CulinaryRole.POWDER_BASE, CulinaryRole.SANDWICH_BASE -> 3
            }
        }
    }

    fun applyPortion(rule: PlanningRule, food: Food): PlanningRule {
        val role = portionRole(rule, food) ?: return rule
        val p = policy(role)
        val preferred = p.preferredGrams ?: return rule
        val minimum = p.minimumGrams ?: preferred
        val maximum = p.maximumGrams ?: preferred
        return rule.copy(
            preferredGrams = preferred,
            minimumFactor = minimum / preferred,
            maximumFactor = maximum / preferred
        )
    }

    fun addresses(need: CulinaryNeed, food: Food): Boolean =
        roles(food).any { it in need.acceptedRoles }

    fun isSuggestedForMeal(food: Food, mealType: MealType): Boolean =
        roles(food).any { role -> mealType in policy(role).suggestedMealTypes }

    fun isAllowedForMeal(role: CulinaryRole, mealType: MealType): Boolean =
        role !in mealRestrictedRoles || mealType in policy(role).suggestedMealTypes

    /**
     * True when one role can be chosen for every role-aware item so all hard rules hold.
     * Empty role sets belong only to migrated/custom legacy foods and mean that Rumbo has
     * no culinary restriction to enforce for that item. Published MENU_ELIGIBLE catalogue
     * products are expected to carry canonical roles.
     */
    fun hasValidRoleAssignment(roleChoices: List<Set<CulinaryRole>>): Boolean {
        val constrained = roleChoices.filter { it.isNotEmpty() }
        if (constrained.isEmpty()) return true
        val chosen = ArrayList<CulinaryRole>(constrained.size)
        fun visit(index: Int): Boolean {
            if (index == constrained.size) {
                val counts = chosen.groupingBy { it }.eachCount()
                if (constrained.size == 1 && !policy(chosen.single()).standaloneAllowed) return false
                if (chosen.any { role ->
                        policy(role).requiredRoles.any { required -> counts.getOrDefault(required, 0) == 0 }
                    }
                ) return false
                if (chosen.any { role ->
                        policy(role).requiredAnyOfRoles.let { alternatives ->
                            alternatives.isNotEmpty() && alternatives.none { counts.getOrDefault(it, 0) > 0 }
                        }
                    }
                ) return false
                if (counts.any { (role, count) ->
                        policy(role).maxPerMeal?.let { count > it } == true
                    }
                ) return false
                return true
            }
            for (role in constrained[index]) {
                chosen += role
                if (visit(index + 1)) return true
                chosen.removeAt(chosen.lastIndex)
            }
            return false
        }
        return visit(0)
    }

    fun missingRequiredRoles(roleChoices: List<Set<CulinaryRole>>): Set<CulinaryRole> {
        val constrained = roleChoices.filter { it.isNotEmpty() }
        val available = constrained.flatten().toSet()
        return constrained.flatten().flatMapTo(linkedSetOf()) { role ->
            buildSet {
                addAll(policy(role).requiredRoles.filter { it !in available })
                val alternatives = policy(role).requiredAnyOfRoles
                if (alternatives.isNotEmpty() && alternatives.none(available::contains)) addAll(alternatives)
            }
        }
    }
}
