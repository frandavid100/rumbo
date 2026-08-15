package es.david.rumbo.logic

import es.david.rumbo.model.CulinaryType
import es.david.rumbo.model.Food
import es.david.rumbo.model.PlanningRule

enum class CulinaryRole {
    STARCH_BASE,
    BREAKFAST_CEREAL,
    LIQUID_OR_CREAMY_BASE,
    DEPENDENT_PREPARATION,
    PRIMARY_PROTEIN,
    CULINARY_FAT
}

data class CulinaryTypePolicy(
    val roles: Set<CulinaryRole> = emptySet(),
    val preferredGrams: Double? = null,
    val minimumGrams: Double? = null,
    val maximumGrams: Double? = null,
    val standaloneAllowed: Boolean = true
)

/** Central policy table. Foods store only their stable CulinaryType. */
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

    fun policy(food: Food): CulinaryTypePolicy = policies.getValue(food.culinaryType)

    fun roles(food: Food): Set<CulinaryRole> = policy(food).roles

    fun standaloneAllowed(food: Food): Boolean = policy(food).standaloneAllowed

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
        val minimum = checkNotNull(policy.minimumGrams)
        val maximum = checkNotNull(policy.maximumGrams)
        return rule.copy(
            preferredGrams = preferred,
            minimumFactor = minimum / preferred,
            maximumFactor = maximum / preferred
        )
    }
}
