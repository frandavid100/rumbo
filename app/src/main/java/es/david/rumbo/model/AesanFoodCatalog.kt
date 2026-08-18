package es.david.rumbo.model

import android.content.Context
import es.david.rumbo.data.catalog.CatalogBackedFoodCatalog
import org.json.JSONObject
import java.util.zip.GZIPInputStream

/**
 * Compatibility facade while the old embedded catalogue remains available as fallback.
 * New catalogue foods are appended through the stable data.catalog boundary.
 */
object MercadonaFoodCatalog {
    private const val SOURCE_PAGE =
        "https://www.aesan.gob.es/AECOSAN/web/seguridad_alimentaria/subseccion/alimentosBebidas.htm"

    fun load(context: Context): List<Food> =
        (loadLegacy(context) + CatalogBackedFoodCatalog.load(context)).distinctBy { it.id }

    private fun loadLegacy(context: Context): List<Food> =
        context.assets.open("aesan_foods.dat").use { asset ->
            GZIPInputStream(asset).bufferedReader(Charsets.UTF_8).useLines { lines ->
                lines.filter(String::isNotBlank).map(::decode).toList()
            }
        }

    private fun decode(line: String): Food {
        val item = JSONObject(line)
        return Food(
            id = item.getLong("i"),
            name = item.getString("n"),
            category = FoodCategory.valueOf(item.getString("r")),
            calories = item.optionalDouble("k"),
            fatGrams = item.optionalDouble("f"),
            carbohydrateGrams = item.optionalDouble("c"),
            proteinGrams = item.optionalDouble("p"),
            fiberGrams = item.optionalDouble("fi"),
            links = listOf(SOURCE_PAGE),
            barcode = item.optionalString("b"),
            brand = item.optionalString("br"),
            family = item.optionalString("fa"),
            subcategory = item.optionalString("sc"),
            legalName = item.optionalString("ln"),
            ingredients = item.optionalString("ing"),
            saturatedFatGrams = item.optionalDouble("sat"),
            sugarGrams = item.optionalDouble("su"),
            saltGrams = item.optionalDouble("sa"),
            retailer = item.optionalString("ret"),
            source = "Mercadona · declaración nutricional recopilada por AESAN (2022)",
            culinaryRoles = legacyCulinaryRoles(item.optionalString("ct"))
        )
    }

    private fun JSONObject.optionalDouble(name: String): Double? =
        if (!has(name) || isNull(name)) null else getDouble(name)

    private fun JSONObject.optionalString(name: String): String? =
        if (!has(name) || isNull(name)) null else getString(name)
}
