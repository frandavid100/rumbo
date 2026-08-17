package es.david.rumbo.model

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import java.io.File

data class CanonicalCatalog(
    val foods: List<Food>,
    val menuEligibleFoodIds: Set<Long>
)

object CanonicalFoodCatalog {
    private const val DATABASE = "rumbo-catalog-v1.sqlite"
    private const val SEED_ASSET = "catalog_v1.sql"

    fun load(context: Context): CanonicalCatalog {
        val dbFile = File(context.noBackupFilesDir, DATABASE)
        if (!dbFile.exists()) createFromSeed(context, dbFile)
        val db = SQLiteDatabase.openDatabase(dbFile.absolutePath, null, SQLiteDatabase.OPEN_READONLY)
        return db.use(::decode)
    }

    private fun createFromSeed(context: Context, target: File) {
        target.parentFile?.mkdirs()
        val db = SQLiteDatabase.openOrCreateDatabase(target, null)
        try {
            val script = context.assets.open(SEED_ASSET).bufferedReader().use { it.readText() }
            db.beginTransaction()
            try {
                script.split(';').map(String::trim).filter(String::isNotEmpty).forEach(db::execSQL)
                db.setTransactionSuccessful()
            } finally {
                db.endTransaction()
            }
        } finally {
            db.close()
        }
    }

    private fun decode(db: SQLiteDatabase): CanonicalCatalog {
        val foods = mutableListOf<Food>()
        val eligible = mutableSetOf<Long>()
        val sql = """
            SELECT p.id,p.gtin,p.canonical_name,p.brand,p.legal_name,p.ingredients,
                   n.calories,n.fat_g,n.carbohydrate_g,n.protein_g,n.fiber_g,
                   n.saturated_fat_g,n.sugar_g,n.salt_g,n.source,
                   c.nutritional_role,c.culinary_type,
                   l.retailer,l.url,e.menu_eligible
            FROM products p
            JOIN retailer_listings l ON l.product_id=p.id
            JOIN classifications c ON c.product_id=p.id
            JOIN eligibility e ON e.product_id=p.id
            LEFT JOIN nutrition n ON n.product_id=p.id
            WHERE e.discoverable=1
            ORDER BY p.canonical_name COLLATE NOCASE
        """.trimIndent()
        db.rawQuery(sql, null).use { cursor ->
            while (cursor.moveToNext()) {
                val id = cursor.getLong(0)
                val category = runCatching { FoodCategory.valueOf(cursor.getString(15)) }
                    .getOrDefault(FoodCategory.OTHER)
                val culinaryType = runCatching { CulinaryType.valueOf(cursor.getString(16)) }
                    .getOrDefault(CulinaryType.UNKNOWN)
                foods += Food(
                    id = id,
                    name = cursor.getString(2),
                    category = category,
                    calories = cursor.optionalDouble(6),
                    fatGrams = cursor.optionalDouble(7),
                    carbohydrateGrams = cursor.optionalDouble(8),
                    proteinGrams = cursor.optionalDouble(9),
                    fiberGrams = cursor.optionalDouble(10),
                    links = cursor.optionalString(18)?.let(::listOf).orEmpty(),
                    barcode = cursor.optionalString(1),
                    brand = cursor.optionalString(3),
                    legalName = cursor.optionalString(4),
                    ingredients = cursor.optionalString(5),
                    saturatedFatGrams = cursor.optionalDouble(11),
                    sugarGrams = cursor.optionalDouble(12),
                    saltGrams = cursor.optionalDouble(13),
                    retailer = cursor.optionalString(17),
                    source = cursor.optionalString(14),
                    culinaryType = culinaryType
                )
                if (cursor.getInt(19) == 1) eligible += id
            }
        }
        return CanonicalCatalog(foods, eligible)
    }

    private fun android.database.Cursor.optionalDouble(column: Int): Double? =
        if (isNull(column)) null else getDouble(column)

    private fun android.database.Cursor.optionalString(column: Int): String? =
        if (isNull(column)) null else getString(column)
}
