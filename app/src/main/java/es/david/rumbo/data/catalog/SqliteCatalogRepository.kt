package es.david.rumbo.data.catalog

import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import java.io.File
import java.io.IOException

private const val CATALOG_ASSET_NAME = "catalog.sqlite"

object CatalogRepositoryProvider {
    fun fromAssets(context: Context): CatalogRepository = runCatching {
        SqliteCatalogRepository(context.applicationContext, CATALOG_ASSET_NAME)
    }.getOrElse { EmptyCatalogRepository }
}

object EmptyCatalogRepository : CatalogRepository {
    override fun metadata(): Map<String, String> = emptyMap()
    override fun retailers(): Set<String> = emptySet()
    override fun search(query: CatalogQuery): List<CatalogProduct> = emptyList()
    override fun product(productId: String): CatalogProduct? = null
}

/**
 * Adapter for the current provisional catalogue SQLite.
 * Schema knowledge is intentionally private to this class: app callers depend only on CatalogRepository.
 */
class SqliteCatalogRepository(
    context: Context,
    assetName: String = CATALOG_ASSET_NAME
) : CatalogRepository {
    private val database: SQLiteDatabase
    private val cachedMetadata: Map<String, String>

    init {
        val file = materializeAsset(context, assetName)
        database = SQLiteDatabase.openDatabase(file.absolutePath, null, SQLiteDatabase.OPEN_READONLY)
        requireSchema(database)
        cachedMetadata = readMetadata(database)
    }

    override fun metadata(): Map<String, String> = cachedMetadata

    override fun retailers(): Set<String> = queryStrings(
        "SELECT DISTINCT retailer FROM retailer_listings ORDER BY retailer"
    ).toSet()

    override fun search(query: CatalogQuery): List<CatalogProduct> {
        val clauses = mutableListOf<String>()
        val args = mutableListOf<String>()
        if (query.text.isNotBlank()) {
            clauses += "(LOWER(p.name) LIKE ? OR LOWER(COALESCE(p.brand, '')) LIKE ? OR LOWER(COALESCE(p.family, '')) LIKE ?)"
            val needle = "%${query.text.trim().lowercase()}%"
            repeat(3) { args += needle }
        }
        if (query.retailers.isNotEmpty()) {
            clauses += "rl.retailer IN (${placeholders(query.retailers.size)})"
            args += query.retailers
        }
        if (query.eligibility.isNotEmpty()) {
            val rawStatuses = query.eligibility.flatMap(::rawStatuses).distinct()
            if (rawStatuses.isEmpty()) return emptyList()
            clauses += "c.status IN (${placeholders(rawStatuses.size)})"
            args += rawStatuses
        }
        val where = if (clauses.isEmpty()) "" else " WHERE ${clauses.joinToString(" AND ")}"
        val sql = """
            SELECT DISTINCT p.product_id
            FROM products p
            JOIN retailer_listings rl ON rl.product_id = p.product_id
            LEFT JOIN classifications c ON c.product_id = p.product_id
            $where
            ORDER BY p.name COLLATE NOCASE
            LIMIT ${query.limit}
        """.trimIndent()
        return queryStrings(sql, args.toTypedArray()).mapNotNull(::product)
    }

    override fun product(productId: String): CatalogProduct? {
        val productRow = database.rawQuery(
            """
                SELECT product_id, gtin, name, brand, legal_name, ingredients,
                       family, subcategory, source_page
                FROM products WHERE product_id = ?
            """.trimIndent(),
            arrayOf(productId)
        ).use { cursor ->
            if (!cursor.moveToFirst()) null else ProductRow(
                id = cursor.string("product_id") ?: return@use null,
                gtin = cursor.string("gtin"),
                name = cursor.string("name") ?: return@use null,
                brand = cursor.string("brand"),
                legalName = cursor.string("legal_name"),
                ingredients = cursor.string("ingredients"),
                family = cursor.string("family"),
                subcategory = cursor.string("subcategory"),
                sourcePage = cursor.string("source_page")
            )
        } ?: return null

        val listings = readListings(productId)
        val nutrition = readNutrition(productId)
        val classification = readClassification(productId)
        val eligibility = eligibility(classification, nutrition)
        return CatalogProduct(
            id = productRow.id,
            gtin = productRow.gtin,
            name = productRow.name,
            brand = productRow.brand,
            legalName = productRow.legalName,
            ingredients = productRow.ingredients,
            family = productRow.family,
            subcategory = productRow.subcategory,
            provenance = CatalogProvenance(
                catalogSource = cachedMetadata["catalog_identity_source"],
                productSource = productRow.sourcePage,
                nutritionSource = nutrition?.source,
                catalogVersion = cachedMetadata["schema_version"],
                importerVersion = cachedMetadata["importer_version"],
                classifierVersion = classification?.classifierVersion ?: cachedMetadata["classifier_version"]
            ),
            listings = listings,
            nutrition = nutrition,
            classification = classification,
            eligibility = eligibility
        )
    }

    private fun readListings(productId: String): List<RetailerListing> = database.rawQuery(
        """
            SELECT retailer, retailer_sku, product_id, url, price_eur, observed_at, status
            FROM retailer_listings WHERE product_id = ? ORDER BY retailer, retailer_sku
        """.trimIndent(),
        arrayOf(productId)
    ).use { cursor ->
        buildList {
            while (cursor.moveToNext()) {
                add(RetailerListing(
                    retailer = cursor.string("retailer") ?: continue,
                    retailerSku = cursor.string("retailer_sku") ?: continue,
                    productId = cursor.string("product_id") ?: continue,
                    url = cursor.string("url"),
                    priceEur = cursor.doubleOrNull("price_eur"),
                    observedAt = cursor.string("observed_at"),
                    status = cursor.string("status")
                ))
            }
        }
    }

    private fun readNutrition(productId: String): CatalogNutrition? = database.rawQuery(
        """
            SELECT calories, protein_g, carbohydrate_g, fat_g, fiber_g, salt_g,
                   evidence_level, source, observed_at
            FROM nutrition WHERE product_id = ?
        """.trimIndent(),
        arrayOf(productId)
    ).use { cursor ->
        if (!cursor.moveToFirst()) null else CatalogNutrition(
            calories = cursor.doubleOrNull("calories"),
            proteinGrams = cursor.doubleOrNull("protein_g"),
            carbohydrateGrams = cursor.doubleOrNull("carbohydrate_g"),
            fatGrams = cursor.doubleOrNull("fat_g"),
            fiberGrams = cursor.doubleOrNull("fiber_g"),
            saltGrams = cursor.doubleOrNull("salt_g"),
            evidenceLevel = cursor.string("evidence_level"),
            source = cursor.string("source"),
            observedAt = cursor.string("observed_at")
        )
    }

    private fun readClassification(productId: String): CatalogClassification? {
        val roles = database.rawQuery(
            """
                SELECT axis, role, confidence, rule_id
                FROM classification_roles WHERE product_id = ? ORDER BY axis, role
            """.trimIndent(),
            arrayOf(productId)
        ).use { cursor ->
            buildList {
                while (cursor.moveToNext()) {
                    add(CatalogRole(
                        axis = when (cursor.string("axis")?.uppercase()) {
                            "NUTRITIONAL" -> CatalogRoleAxis.NUTRITIONAL
                            "CULINARY" -> CatalogRoleAxis.CULINARY
                            else -> CatalogRoleAxis.UNKNOWN
                        },
                        role = cursor.string("role") ?: continue,
                        confidence = cursor.doubleOrNull("confidence"),
                        ruleId = cursor.string("rule_id")
                    ))
                }
            }
        }
        return database.rawQuery(
            """
                SELECT classifier_version, classified, status
                FROM classifications WHERE product_id = ?
            """.trimIndent(),
            arrayOf(productId)
        ).use { cursor ->
            if (!cursor.moveToFirst()) null else CatalogClassification(
                classifierVersion = cursor.string("classifier_version"),
                classified = cursor.intOrNull("classified") == 1,
                status = cursor.string("status"),
                roles = roles
            )
        }
    }

    private fun eligibility(
        classification: CatalogClassification?,
        nutrition: CatalogNutrition?
    ): CatalogEligibility {
        val raw = CatalogEligibility.fromRaw(classification?.status)
        return if (
            raw == CatalogEligibility.MENU_ELIGIBLE &&
            classification?.classified == true &&
            nutrition?.hasGeneratorNutrition == true
        ) CatalogEligibility.MENU_ELIGIBLE
        else if (raw == CatalogEligibility.MENU_ELIGIBLE) CatalogEligibility.NUTRITION_MISSING
        else raw
    }

    private fun queryStrings(sql: String, args: Array<String> = emptyArray()): List<String> =
        database.rawQuery(sql, args).use { cursor ->
            buildList { while (cursor.moveToNext()) cursor.getString(0)?.let(::add) }
        }

    private fun rawStatuses(value: CatalogEligibility): List<String> = when (value) {
        CatalogEligibility.MENU_ELIGIBLE -> listOf("MENU_ELIGIBLE")
        CatalogEligibility.REVIEW -> listOf("REVIEW")
        CatalogEligibility.NUTRITION_MISSING -> listOf("NUTRITION_MISSING")
        CatalogEligibility.NUTRITION_INVALID -> listOf("NUTRITION_INVALID")
        CatalogEligibility.EXCLUDED -> listOf("EXCLUDED", "EXCLUDED_SCOPE")
        CatalogEligibility.UNKNOWN -> emptyList()
    }

    private data class ProductRow(
        val id: String,
        val gtin: String?,
        val name: String,
        val brand: String?,
        val legalName: String?,
        val ingredients: String?,
        val family: String?,
        val subcategory: String?,
        val sourcePage: String?
    )
}

private fun materializeAsset(context: Context, assetName: String): File {
    val directory = File(context.filesDir, "catalog").apply { mkdirs() }
    val target = File(directory, assetName)
    val appUpdatedAt = runCatching {
        context.packageManager.getPackageInfo(context.packageName, 0).lastUpdateTime
    }.getOrDefault(Long.MAX_VALUE)
    if (!target.exists() || target.lastModified() < appUpdatedAt) {
        val temp = File(directory, "$assetName.tmp")
        try {
            context.assets.open(assetName).use { input -> temp.outputStream().use(input::copyTo) }
        } catch (error: IOException) {
            temp.delete()
            throw error
        }
        if (target.exists()) target.delete()
        require(temp.renameTo(target)) { "No se pudo activar el catálogo empaquetado" }
    }
    return target
}

private fun requireSchema(database: SQLiteDatabase) {
    val required = setOf(
        "metadata", "products", "retailer_listings", "nutrition",
        "classifications", "classification_roles"
    )
    val present = database.rawQuery(
        "SELECT name FROM sqlite_master WHERE type = 'table'", null
    ).use { cursor -> buildSet { while (cursor.moveToNext()) add(cursor.getString(0)) } }
    require(required.all(present::contains)) { "El catálogo SQLite no cumple el contrato provisional esperado" }
}

private fun readMetadata(database: SQLiteDatabase): Map<String, String> = database.rawQuery(
    "SELECT key, value FROM metadata", null
).use { cursor ->
    buildMap {
        while (cursor.moveToNext()) {
            val key = cursor.getString(0) ?: continue
            val value = cursor.getString(1) ?: continue
            put(key, value)
        }
    }
}

private fun placeholders(size: Int): String = List(size) { "?" }.joinToString(",")

private fun Cursor.string(column: String): String? {
    val index = getColumnIndexOrThrow(column)
    return if (isNull(index)) null else getString(index)
}

private fun Cursor.doubleOrNull(column: String): Double? {
    val index = getColumnIndexOrThrow(column)
    return if (isNull(index)) null else getDouble(index)
}

private fun Cursor.intOrNull(column: String): Int? {
    val index = getColumnIndexOrThrow(column)
    return if (isNull(index)) null else getInt(index)
}
