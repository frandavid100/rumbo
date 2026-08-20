package es.david.rumbo.data.catalog

import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption

private const val CATALOG_ASSET_NAME = "catalog.sqlite"
private const val CATALOG_FORMAT = "es.rumbo.catalog.sqlite"
private const val CATALOG_FORMAT_VERSION = "1"
private const val CATALOG_SCHEMA_VERSION = "rumbo-catalog-1"
private val CATALOG_TOKEN = Regex("[a-z0-9][a-z0-9._-]{0,79}")

object CatalogRepositoryProvider {
    fun fromAssets(context: Context): CatalogRepository = runCatching {
        val imported = CatalogImportManager.catalogFiles(context.applicationContext)
            .map(::SqliteCatalogRepository)
        when (imported.size) {
            0 -> SqliteCatalogRepository(context.applicationContext, CATALOG_ASSET_NAME)
            1 -> imported.single()
            else -> CompositeCatalogRepository(imported)
        }
    }.getOrElse { EmptyCatalogRepository }
}

data class InstalledCatalog(
    val id: String,
    val name: String,
    val source: String,
    val catalogVersion: String?,
    val schemaVersion: String,
    val productCount: Int,
    val productIdNamespace: String
)

/** Atomic storage boundary for catalogues selected through Android's document picker. */
object CatalogImportManager {
    private const val EXTENSION = ".rumbocatalog"

    private fun directory(context: Context): File = File(context.filesDir, "catalogs")
        .apply { mkdirs() }

    internal fun catalogFiles(context: Context): List<File> = directory(context)
        .listFiles { file -> file.isFile && file.name.endsWith(EXTENSION) }
        .orEmpty().sortedBy { it.name }

    fun list(context: Context): List<InstalledCatalog> = catalogFiles(context).mapNotNull { file ->
        runCatching { summary(validateCatalogFile(file)) }.getOrNull()
    }

    fun import(context: Context, input: InputStream): InstalledCatalog {
        val directory = directory(context)
        val temporary = File(directory, "catalog-import.tmp")
        input.use { source -> temporary.outputStream().use(source::copyTo) }
        val metadata = runCatching { validateCatalogFile(temporary) }
            .getOrElse { error ->
                temporary.delete()
                throw IllegalArgumentException("El archivo no es un catálogo válido de Rumbo", error)
            }
        require(metadata["catalog_format"] == CATALOG_FORMAT &&
            metadata["catalog_format_version"] == CATALOG_FORMAT_VERSION) {
            "El archivo no usa el formato de catálogo de Rumbo compatible"
        }
        require(metadata["schema_version"] == CATALOG_SCHEMA_VERSION) {
            "La versión del catálogo no es compatible con esta versión de Rumbo"
        }
        val catalog = summary(metadata)
        require(catalog.catalogVersion?.isNotBlank() == true) {
            "El catálogo no declara una versión actualizable"
        }
        val namespaceOwner = list(context).firstOrNull {
            it.id != catalog.id && it.productIdNamespace == catalog.productIdNamespace
        }
        require(namespaceOwner == null) {
            "El espacio de productos ${catalog.productIdNamespace} ya pertenece a ${namespaceOwner?.name}"
        }
        val target = File(directory, "${catalog.id}$EXTENSION")
        Files.move(
            temporary.toPath(), target.toPath(),
            StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING
        )
        return catalog
    }

    fun delete(context: Context, catalogId: String): Boolean {
        require(catalogId.matches(CATALOG_TOKEN))
        val target = File(directory(context), "$catalogId$EXTENSION")
        return !target.exists() || target.delete()
    }

    private fun summary(metadata: Map<String, String>): InstalledCatalog {
        val id = metadata["catalog_id"]
            ?.takeIf { it.matches(CATALOG_TOKEN) }
            ?: error("El catálogo no declara una identidad válida")
        val namespace = metadata["product_id_namespace"]
            ?.takeIf { it.matches(CATALOG_TOKEN) }
            ?: error("El catálogo no declara un espacio de productos válido")
        return InstalledCatalog(
            id = id,
            name = metadata["catalog_name"]?.takeIf { it.isNotBlank() } ?: id,
            source = metadata["catalog_identity_source"] ?: "Desconocida",
            catalogVersion = metadata["catalog_version"],
            schemaVersion = metadata["schema_version"] ?: error("Falta schema_version"),
            productCount = metadata["product_count"]?.toIntOrNull()?.coerceAtLeast(0) ?: 0,
            productIdNamespace = namespace
        )
    }
}

private class CompositeCatalogRepository(
    private val repositories: List<CatalogRepository>
) : CatalogRepository {
    override fun metadata(): Map<String, String> = mapOf(
        "catalog_count" to repositories.size.toString(),
        "catalog_format" to CATALOG_FORMAT,
        "catalog_format_version" to CATALOG_FORMAT_VERSION,
        "schema_version" to CATALOG_SCHEMA_VERSION
    )

    override fun retailers(): Set<String> = repositories.flatMapTo(sortedSetOf()) { it.retailers() }

    override fun search(query: CatalogQuery): List<CatalogProduct> = repositories
        .flatMap { it.search(query) }
        .distinctBy { it.id }
        .sortedBy { it.name.lowercase() }
        .take(query.limit)

    override fun product(productId: String): CatalogProduct? =
        repositories.firstNotNullOfOrNull { it.product(productId) }
}

private fun validateCatalogFile(file: File): Map<String, String> {
    val database = SQLiteDatabase.openDatabase(file.absolutePath, null, SQLiteDatabase.OPEN_READONLY)
    return database.use {
        requireSchema(it)
        val metadata = readMetadata(it)
        val namespace = metadata["product_id_namespace"]
            ?.takeIf { token -> token.matches(CATALOG_TOKEN) }
            ?: error("Falta product_id_namespace")
        val actualCount = it.rawQuery("SELECT COUNT(*) FROM products", null).use { cursor ->
            check(cursor.moveToFirst())
            cursor.getInt(0)
        }
        require(metadata["product_count"]?.toIntOrNull() == actualCount) {
            "El recuento de productos no coincide con el contenido"
        }
        val invalidIds = it.rawQuery(
            "SELECT COUNT(*) FROM products WHERE product_id NOT LIKE ?",
            arrayOf("$namespace:%")
        ).use { cursor ->
            check(cursor.moveToFirst())
            cursor.getInt(0)
        }
        require(invalidIds == 0) { "Hay productos fuera del espacio de identidad declarado" }
        metadata
    }
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
class SqliteCatalogRepository internal constructor(
    file: File
) : CatalogRepository {
    constructor(
        context: Context,
        assetName: String = CATALOG_ASSET_NAME
    ) : this(materializeAsset(context, assetName))

    private val database: SQLiteDatabase
    private val cachedMetadata: Map<String, String>

    init {
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
            clauses += "EXISTS (SELECT 1 FROM retailer_listings filtered_rl " +
                "WHERE filtered_rl.product_id = p.product_id AND " +
                "filtered_rl.retailer IN (${placeholders(query.retailers.size)}))"
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
        val portionExpression = when {
            database.hasColumn("classifications", "portion_basis_grams") -> "portion_basis_grams"
            database.hasColumn("classifications", "preferred_grams") -> "preferred_grams"
            else -> "NULL"
        }
        return database.rawQuery(
            """
                SELECT classifier_version, classified, status,
                       $portionExpression AS portion_basis_grams
                FROM classifications WHERE product_id = ?
            """.trimIndent(),
            arrayOf(productId)
        ).use { cursor ->
            if (!cursor.moveToFirst()) null else CatalogClassification(
                classifierVersion = cursor.string("classifier_version"),
                classified = cursor.intOrNull("classified") == 1,
                status = cursor.string("status"),
                roles = roles,
                portionBasisGrams = cursor.doubleOrNull("portion_basis_grams")
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

private fun SQLiteDatabase.hasColumn(table: String, column: String): Boolean =
    rawQuery("PRAGMA table_info($table)", null).use { cursor ->
        val nameIndex = cursor.getColumnIndexOrThrow("name")
        while (cursor.moveToNext()) {
            if (cursor.getString(nameIndex) == column) return@use true
        }
        false
    }

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
