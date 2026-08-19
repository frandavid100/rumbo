package es.david.rumbo.data.catalog

import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import java.nio.ByteBuffer
import java.security.MessageDigest

/** Stable app-facing product identity. It deliberately does not expose SQLite rows. */
data class CatalogProduct(
    val id: String,
    val gtin: String?,
    val name: String,
    val brand: String?,
    val legalName: String?,
    val ingredients: String?,
    val family: String?,
    val subcategory: String?,
    val provenance: CatalogProvenance,
    val listings: List<RetailerListing>,
    val nutrition: CatalogNutrition?,
    val classification: CatalogClassification?,
    val eligibility: CatalogEligibility
)

data class RetailerListing(
    val retailer: String,
    val retailerSku: String,
    val productId: String,
    val url: String?,
    val priceEur: Double?,
    val observedAt: String?,
    val status: String?
)

data class CatalogNutrition(
    val calories: Double?,
    val proteinGrams: Double?,
    val carbohydrateGrams: Double?,
    val fatGrams: Double?,
    val fiberGrams: Double?,
    val saltGrams: Double?,
    val evidenceLevel: String?,
    val source: String?,
    val observedAt: String?
) {
    val hasGeneratorNutrition: Boolean
        get() = calories != null && proteinGrams != null && carbohydrateGrams != null && fatGrams != null
}

data class CatalogRole(
    val axis: CatalogRoleAxis,
    val role: String,
    val confidence: Double?,
    val ruleId: String?
)

enum class CatalogRoleAxis { NUTRITIONAL, CULINARY, UNKNOWN }

data class CatalogClassification(
    val classifierVersion: String?,
    val classified: Boolean,
    val status: String?,
    val roles: List<CatalogRole>,
    val portionBasisGrams: Double? = null
) {
    val nutritionalRoles: Set<String>
        get() = roles.filter { it.axis == CatalogRoleAxis.NUTRITIONAL }.mapTo(linkedSetOf()) { it.role }
    val culinaryRoles: Set<String>
        get() = roles.filter { it.axis == CatalogRoleAxis.CULINARY }.mapTo(linkedSetOf()) { it.role }
}

data class CatalogProvenance(
    val catalogSource: String?,
    val productSource: String?,
    val nutritionSource: String?,
    val catalogVersion: String?,
    val importerVersion: String?,
    val classifierVersion: String?
)

enum class CatalogEligibility {
    MENU_ELIGIBLE,
    REVIEW,
    NUTRITION_MISSING,
    NUTRITION_INVALID,
    EXCLUDED,
    UNKNOWN;

    companion object {
        fun fromRaw(value: String?): CatalogEligibility = when (value?.uppercase()) {
            "MENU_ELIGIBLE" -> MENU_ELIGIBLE
            "REVIEW" -> REVIEW
            "NUTRITION_MISSING" -> NUTRITION_MISSING
            "NUTRITION_INVALID" -> NUTRITION_INVALID
            "EXCLUDED", "EXCLUDED_SCOPE" -> EXCLUDED
            else -> UNKNOWN
        }
    }
}

data class CatalogQuery(
    val text: String = "",
    val retailers: Set<String> = emptySet(),
    val eligibility: Set<CatalogEligibility> = emptySet(),
    val limit: Int = 200
) {
    init {
        require(limit in 1..20_000)
    }
}

interface CatalogRepository {
    fun metadata(): Map<String, String>
    fun retailers(): Set<String>
    fun search(query: CatalogQuery = CatalogQuery()): List<CatalogProduct>
    fun product(productId: String): CatalogProduct?
}

/**
 * Boundary between the richer catalogue contract and Rumbo's current Food model.
 * Only generator-safe products cross this boundary.
 */
object CatalogFoodAdapter {
    private const val CATALOG_ID_BASE = 4_000_000_000_000_000_000L
    private const val HASH_RANGE = 2_000_000_000_000_000_000L

    fun toFood(product: CatalogProduct): Food? {
        if (product.eligibility != CatalogEligibility.MENU_ELIGIBLE) return null
        val nutrition = product.nutrition?.takeIf { it.hasGeneratorNutrition } ?: return null
        val classification = product.classification?.takeIf { it.classified } ?: return null
        return Food(
            id = stableFoodId(product.id),
            name = product.name,
            category = legacyCategory(classification.nutritionalRoles),
            calories = nutrition.calories,
            fatGrams = nutrition.fatGrams,
            carbohydrateGrams = nutrition.carbohydrateGrams,
            proteinGrams = nutrition.proteinGrams,
            fiberGrams = nutrition.fiberGrams,
            links = product.listings.mapNotNull { it.url }.distinct().take(10),
            barcode = product.gtin?.takeIf { it.length in 8..14 },
            brand = product.brand,
            family = product.family,
            subcategory = product.subcategory,
            legalName = product.legalName,
            ingredients = product.ingredients,
            saltGrams = nutrition.saltGrams,
            retailer = product.listings.map { it.retailer }.distinct().joinToString(", ").takeIf { it.isNotBlank() },
            source = product.provenance.catalogSource ?: nutrition.source,
            portionBasisGrams = classification.portionBasisGrams,
            nutritionalRoles = classification.nutritionalRoles,
            culinaryRoles = classification.culinaryRoles
        ).takeIf { it.isValid() && it.hasComparableNutrition() }
    }

    fun stableFoodId(productId: String): Long {
        val digest = MessageDigest.getInstance("SHA-256").digest(productId.toByteArray(Charsets.UTF_8))
        val raw = ByteBuffer.wrap(digest, 0, Long.SIZE_BYTES).long and Long.MAX_VALUE
        return CATALOG_ID_BASE + (raw % HASH_RANGE)
    }

    internal fun legacyCategory(roles: Set<String>): FoodCategory = when {
        "FRUIT" in roles -> FoodCategory.FRUIT
        "VEGETABLE" in roles -> FoodCategory.VEGETABLE
        "PRIMARY_PROTEIN" in roles -> FoodCategory.PROTEIN
        "PRIMARY_CARBOHYDRATE" in roles -> FoodCategory.CARBOHYDRATE
        "CONCENTRATED_FAT" in roles -> FoodCategory.FAT
        "COMPLEMENTARY_PROTEIN" in roles -> FoodCategory.PROTEIN
        "COMPLEMENTARY_CARBOHYDRATE" in roles -> FoodCategory.CARBOHYDRATE
        "COMPLEMENTARY_FAT" in roles -> FoodCategory.FAT
        else -> FoodCategory.OTHER
    }

}
