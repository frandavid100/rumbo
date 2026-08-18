from pathlib import Path
import re

ROOT = Path('.')

def read(path): return (ROOT/path).read_text()
def write(path, text): (ROOT/path).write_text(text)
def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 exact match, got {n}')
    return text.replace(old, new, 1)
def sub1(text, pattern, repl, label, flags=re.S):
    out, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 regex match, got {n}')
    return out

# --- Models: one canonical culinary axis. Legacy type names exist only as migration strings. ---
p = Path('app/src/main/java/es/david/rumbo/model/Models.kt')
s = read(p)
s = sub1(s, r'''enum class CulinaryType\(val label: String\) \{.*?\n\}\n\ndata class CulinaryPolicyOverride\(\n    val culinaryType: CulinaryType,\n    val roles: Set<String> = emptySet\(\),\n    val preferredGrams: Double\? = null,\n    val minimumGrams: Double\? = null,\n    val maximumGrams: Double\? = null,\n    val standaloneAllowed: Boolean = true\n\)''', '''/**
 * Converts the obsolete pre-0.74 culinary type into the canonical functional roles.
 * New code must never persist or reason over the legacy type name itself.
 */
fun legacyCulinaryRoles(typeName: String?): Set<String> = when (typeName) {
    "MILK_BASE" -> setOf("CEREAL_BASE", "POWDER_BASE", "BEVERAGE", "STANDALONE")
    "CREAMY_BASE" -> setOf("CEREAL_BASE", "POWDER_BASE", "STANDALONE", "DESSERT")
    "BREAKFAST_CEREAL" -> setOf("CEREAL_MIX_IN")
    "PROTEIN_POWDER" -> setOf("POWDER_MIX_IN")
    "DRY_RICE", "DRY_PASTA", "FRESH_STARCH" -> setOf("PLATE_BASE")
    "BREAD" -> setOf("SANDWICH_BASE", "PLATE_BASE", "STANDALONE")
    "MAIN_MEAT" -> setOf("PLATE_CENTER", "SANDWICH_FILLING", "TOPPING", "STANDALONE")
    "MAIN_FISH" -> setOf("PLATE_CENTER", "STANDALONE")
    "MAIN_EGG" -> setOf("PLATE_CENTER", "SANDWICH_FILLING", "STANDALONE")
    "VEGETABLE" -> setOf("SIDE", "PLATE_BASE", "STANDALONE")
    "FRUIT" -> setOf("STANDALONE", "DESSERT")
    "CULINARY_OIL" -> setOf("COOKING_MEDIUM", "SAUCE_DRESSING")
    "FAT_COMPLEMENT" -> setOf("TOPPING", "STANDALONE")
    "SAUCE" -> setOf("SAUCE_DRESSING")
    "SNACK_DESSERT" -> setOf("STANDALONE", "DESSERT")
    "COOKING_INGREDIENT" -> setOf("SEASONING")
    else -> emptySet()
}

data class CulinaryPolicyOverride(
    val culinaryRole: String,
    val preferredGrams: Double? = null,
    val minimumGrams: Double? = null,
    val maximumGrams: Double? = null,
    val standaloneAllowed: Boolean? = null
)''', 'models culinary type/override')
s = one(s, '''    val unitDivisions: Int = 1,
    val culinaryType: CulinaryType = CulinaryType.UNKNOWN,
    val nutritionalRoles: Set<String> = emptySet(),
''', '''    val unitDivisions: Int = 1,
    val nutritionalRoles: Set<String> = emptySet(),
''', 'Food culinaryType')
write(p, s)

# --- Catalog contract: expose roles only; ignore accidental type/portion columns. ---
p = Path('app/src/main/java/es/david/rumbo/data/catalog/CatalogModels.kt')
s = read(p)
s = s.replace('import es.david.rumbo.model.CulinaryType\n', '')
s = one(s, '''data class CatalogClassification(
    val classifierVersion: String?,
    val culinaryType: String?,
    val preferredGrams: Double?,
    val minimumGrams: Double?,
    val maximumGrams: Double?,
    val classified: Boolean,
''', '''data class CatalogClassification(
    val classifierVersion: String?,
    val classified: Boolean,
''', 'CatalogClassification legacy fields')
s = one(s, '''            source = product.provenance.catalogSource ?: nutrition.source,
            culinaryType = legacyCulinaryType(classification.culinaryType),
            nutritionalRoles = classification.nutritionalRoles,
''', '''            source = product.provenance.catalogSource ?: nutrition.source,
            nutritionalRoles = classification.nutritionalRoles,
''', 'adapter culinary type')
s = sub1(s, r'''\n    internal fun legacyCulinaryType\(raw: String\?\): CulinaryType =\n        raw\?\.let \{ value -> CulinaryType\.entries\.firstOrNull \{ it\.name == value \} \} \?: CulinaryType\.UNKNOWN\n''', '\n', 'legacy adapter helper')
write(p, s)

p = Path('app/src/main/java/es/david/rumbo/data/catalog/SqliteCatalogRepository.kt')
s = read(p)
s = one(s, '''                SELECT classifier_version, culinary_type, preferred_grams, minimum_grams,
                       maximum_grams, classified, status
''', '''                SELECT classifier_version, classified, status
''', 'sqlite classification projection')
s = one(s, '''                classifierVersion = cursor.string("classifier_version"),
                culinaryType = cursor.string("culinary_type"),
                preferredGrams = cursor.doubleOrNull("preferred_grams"),
                minimumGrams = cursor.doubleOrNull("minimum_grams"),
                maximumGrams = cursor.doubleOrNull("maximum_grams"),
                classified = cursor.intOrNull("classified") == 1,
''', '''                classifierVersion = cursor.string("classifier_version"),
                classified = cursor.intOrNull("classified") == 1,
''', 'sqlite classification object')
write(p, s)

# Legacy embedded data readers produce roles only.
p = Path('app/src/main/java/es/david/rumbo/model/AesanFoodCatalog.kt')
s = read(p)
s = one(s, '''            source = "Mercadona · declaración nutricional recopilada por AESAN (2022)",
            culinaryType = item.optionalString("ct")
                ?.let { runCatching { CulinaryType.valueOf(it) }.getOrNull() }
                ?: CulinaryType.UNKNOWN
''', '''            source = "Mercadona · declaración nutricional recopilada por AESAN (2022)",
            culinaryRoles = legacyCulinaryRoles(item.optionalString("ct"))
''', 'AESAN legacy type')
write(p, s)

p = Path('app/src/main/java/es/david/rumbo/model/DefaultFoodCatalog.kt')
s = read(p)
s = one(s, '''        links = links.ifEmpty { listOf(mercadonaSearch(name)) },
        culinaryType = culinaryType(id)
    )

    private fun culinaryType(id: Long): CulinaryType = when (id) {
        1L -> CulinaryType.MILK_BASE
        2L -> CulinaryType.SNACK_DESSERT
        3L, 16L, 17L -> CulinaryType.DRY_RICE
        in 4L..7L -> CulinaryType.BREAD
        8L, 9L, 15L -> CulinaryType.FRESH_STARCH
        10L, in 18L..20L -> CulinaryType.FRUIT
        11L -> CulinaryType.BREAKFAST_CEREAL
        in 12L..14L -> CulinaryType.DRY_PASTA
        21L, 23L, 24L, 25L, 28L -> CulinaryType.FAT_COMPLEMENT
        22L -> CulinaryType.CULINARY_OIL
        26L, 27L -> CulinaryType.SAUCE
        29L -> CulinaryType.VEGETABLE
        30L, in 34L..35L, 38L -> CulinaryType.MAIN_FISH
        31L, 42L -> CulinaryType.PROTEIN_POWDER
        32L -> CulinaryType.CREAMY_BASE
        43L -> CulinaryType.MAIN_EGG
        33L, 36L, 37L, 39L, 40L, 41L, in 44L..48L -> CulinaryType.MAIN_MEAT
        in 49L..52L -> CulinaryType.VEGETABLE
        else -> CulinaryType.UNKNOWN
    }
''', '''        links = links.ifEmpty { listOf(mercadonaSearch(name)) },
        culinaryRoles = legacyCulinaryRoles(legacyTypeName(id))
    )

    private fun legacyTypeName(id: Long): String? = when (id) {
        1L -> "MILK_BASE"
        2L -> "SNACK_DESSERT"
        3L, 16L, 17L -> "DRY_RICE"
        in 4L..7L -> "BREAD"
        8L, 9L, 15L -> "FRESH_STARCH"
        10L, in 18L..20L -> "FRUIT"
        11L -> "BREAKFAST_CEREAL"
        in 12L..14L -> "DRY_PASTA"
        21L, 23L, 24L, 25L, 28L -> "FAT_COMPLEMENT"
        22L -> "CULINARY_OIL"
        26L, 27L -> "SAUCE"
        29L -> "VEGETABLE"
        30L, in 34L..35L, 38L -> "MAIN_FISH"
        31L, 42L -> "PROTEIN_POWDER"
        32L -> "CREAMY_BASE"
        43L -> "MAIN_EGG"
        33L, 36L, 37L, 39L, 40L, 41L, in 44L..48L -> "MAIN_MEAT"
        in 49L..52L -> "VEGETABLE"
        else -> null
    }
''', 'Default catalog migration')
write(p, s)

# --- Central canonical policy keyed only by functional role. ---
p = Path('app/src/main/java/es/david/rumbo/logic/CulinaryPolicy.kt')
write(p, '''package es.david.rumbo.logic

import es.david.rumbo.model.CulinaryPolicyOverride
import es.david.rumbo.model.Food
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
    val maxPerMeal: Int? = null
)

/** Canonical culinary policy. Products only store the functional roles they can perform. */
object CulinaryPolicy {
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
        CulinaryRole.BINDER to CulinaryRolePolicy(20.0, 5.0, 60.0, standaloneAllowed = false),
        CulinaryRole.COATING to CulinaryRolePolicy(30.0, 10.0, 80.0, standaloneAllowed = false),
        CulinaryRole.SEASONING to CulinaryRolePolicy(3.0, 0.5, 10.0, standaloneAllowed = false),
        CulinaryRole.STANDALONE to CulinaryRolePolicy(100.0, 20.0, 300.0),
        CulinaryRole.BEVERAGE to CulinaryRolePolicy(250.0, 100.0, 500.0),
        CulinaryRole.DESSERT to CulinaryRolePolicy(125.0, 40.0, 250.0)
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

    fun defaultPolicy(role: CulinaryRole): CulinaryRolePolicy = policies.getValue(role)
    fun policy(role: CulinaryRole): CulinaryRolePolicy = profileOverrides[role] ?: defaultPolicy(role)
    fun parseRole(name: String): CulinaryRole? = CulinaryRole.entries.firstOrNull { it.name == name }

    fun roles(food: Food): Set<CulinaryRole> = food.culinaryRoles.mapNotNullTo(linkedSetOf(), ::parseRole)

    private fun portionRole(food: Food): CulinaryRole? = roles(food).minByOrNull { role ->
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

    fun applyPortion(rule: PlanningRule, food: Food): PlanningRule {
        val role = portionRole(food) ?: return rule
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

    /** True when one role can be chosen for every item so all hard rules hold. */
    fun hasValidRoleAssignment(roleChoices: List<Set<CulinaryRole>>): Boolean {
        if (roleChoices.isEmpty()) return false
        if (roleChoices.any { it.isEmpty() }) return false
        val chosen = ArrayList<CulinaryRole>(roleChoices.size)
        fun visit(index: Int): Boolean {
            if (index == roleChoices.size) {
                val counts = chosen.groupingBy { it }.eachCount()
                if (chosen.size == 1 && !policy(chosen.single()).standaloneAllowed) return false
                if (chosen.any { role -> policy(role).requiredRoles.any { required -> counts.getOrDefault(required, 0) == 0 } }) return false
                if (counts.any { (role, count) -> policy(role).maxPerMeal?.let { count > it } == true }) return false
                return true
            }
            for (role in roleChoices[index]) {
                chosen += role
                if (visit(index + 1)) return true
                chosen.removeAt(chosen.lastIndex)
            }
            return false
        }
        return visit(0)
    }

    fun missingRequiredRoles(roleChoices: List<Set<CulinaryRole>>): Set<CulinaryRole> {
        val available = roleChoices.flatten().toSet()
        return roleChoices.flatten().flatMapTo(linkedSetOf()) { role ->
            policy(role).requiredRoles.filter { it !in available }
        }
    }
}
''')

print('Canonical culinary-role core migration prepared')
