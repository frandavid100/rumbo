package es.david.rumbo.logic

import es.david.rumbo.model.Food

/**
 * Versioned structural preferences used by level 3.
 * Hard REQUIRE/FORBID/cardinality rules remain in CulinaryPolicy.
 */
object CulinarySoftPolicy {
    const val POLICY_VERSION = 4

    private val unlimitedDailyRepetitionRoles = setOf(
        CulinaryRole.COOKING_MEDIUM,
        CulinaryRole.SAUCE_DRESSING,
        CulinaryRole.SEASONING,
        CulinaryRole.BEVERAGE
    )

    private val twiceDailyRoles = setOf(
        CulinaryRole.PLATE_BASE,
        CulinaryRole.SANDWICH_BASE,
        CulinaryRole.CEREAL_BASE,
        CulinaryRole.POWDER_BASE
    )

    private val plateVehicleRoles = setOf(
        CulinaryRole.PLATE_CENTER, CulinaryRole.PLATE_BASE, CulinaryRole.SIDE
    )

    private val leafySaladMarkers = setOf(
        "canonigo", "canónigo", "lechuga", "escarola", "rucula", "rúcula", "endibia", "berro"
    )

    private val preferAnyOf: Map<CulinaryRole, Set<CulinaryRole>> = mapOf(
        CulinaryRole.PLATE_CENTER to setOf(CulinaryRole.PLATE_BASE, CulinaryRole.SIDE),
        CulinaryRole.PLATE_BASE to setOf(CulinaryRole.PLATE_CENTER, CulinaryRole.SIDE),
        CulinaryRole.SIDE to setOf(CulinaryRole.PLATE_CENTER, CulinaryRole.PLATE_BASE),
        CulinaryRole.SANDWICH_BASE to setOf(CulinaryRole.SANDWICH_FILLING, CulinaryRole.SPREAD),
        CulinaryRole.CEREAL_BASE to setOf(CulinaryRole.CEREAL_MIX_IN),
        CulinaryRole.POWDER_BASE to setOf(CulinaryRole.POWDER_MIX_IN),
        CulinaryRole.COOKING_MEDIUM to plateVehicleRoles,
        CulinaryRole.SAUCE_DRESSING to plateVehicleRoles
    )

    fun preferredCompanions(role: CulinaryRole): Set<CulinaryRole> =
        preferAnyOf[role].orEmpty()

    fun additionalPreferredCompanions(food: Food, role: CulinaryRole): Set<CulinaryRole> {
        val name = food.name.lowercase()
        return if (role == CulinaryRole.SIDE && leafySaladMarkers.any(name::contains)) {
            setOf(CulinaryRole.SAUCE_DRESSING)
        } else emptySet()
    }

    fun missingPreferences(roles: Collection<CulinaryRole>): Map<CulinaryRole, Set<CulinaryRole>> {
        val present = roles.toSet()
        return roles.distinct().mapNotNull { role ->
            val targets = preferredCompanions(role)
            (role to targets).takeIf { targets.isNotEmpty() && targets.none(present::contains) }
        }.toMap()
    }

    fun hasMissingFoodPreferences(assignments: List<Pair<Food, CulinaryRole>>): Boolean {
        val present = assignments.mapTo(mutableSetOf()) { it.second }
        return assignments.any { (food, role) ->
            val targets = additionalPreferredCompanions(food, role)
            targets.isNotEmpty() && targets.none(present::contains)
        }
    }

    fun maximumDailyOccurrences(roles: Collection<CulinaryRole>): Int? = when {
        roles.isNotEmpty() && roles.all(unlimitedDailyRepetitionRoles::contains) -> null
        roles.isNotEmpty() && roles.all(twiceDailyRoles::contains) -> 2
        else -> 1
    }
}
