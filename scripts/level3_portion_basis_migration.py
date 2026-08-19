from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"No se encontró el bloque esperado en {path}: {old[:80]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"El bloque no es único en {path}: {text.count(old)} apariciones")
    p.write_text(text.replace(old, new, 1))

# Food: the physical portion basis is product metadata, independent of culinary role/user.
replace_once(
    "app/src/main/java/es/david/rumbo/model/Models.kt",
    """    val unitDivisions: Int = 1,\n    val nutritionalRoles: Set<String> = emptySet(),\n""",
    """    val unitDivisions: Int = 1,\n    val portionBasisGrams: Double? = null,\n    val nutritionalRoles: Set<String> = emptySet(),\n""",
)
replace_once(
    "app/src/main/java/es/david/rumbo/model/Models.kt",
    """        (unitAmount == null || unitAmount in 0.1..5000.0) &&\n        (!wholeUnitsOnly || unitName?.isNotBlank() == true) &&\n""",
    """        (unitAmount == null || unitAmount in 0.1..5000.0) &&\n        (portionBasisGrams == null || portionBasisGrams in 0.1..5000.0) &&\n        (!wholeUnitsOnly || unitName?.isNotBlank() == true) &&\n""",
)

# Catalogue DTO and adapter.
replace_once(
    "app/src/main/java/es/david/rumbo/data/catalog/CatalogModels.kt",
    """data class CatalogClassification(\n    val classifierVersion: String?,\n    val classified: Boolean,\n    val status: String?,\n    val roles: List<CatalogRole>\n) {\n""",
    """data class CatalogClassification(\n    val classifierVersion: String?,\n    val classified: Boolean,\n    val status: String?,\n    val roles: List<CatalogRole>,\n    val portionBasisGrams: Double? = null\n) {\n""",
)
replace_once(
    "app/src/main/java/es/david/rumbo/data/catalog/CatalogModels.kt",
    """            unitDivisions = 1,\n            nutritionalRoles = classification.nutritionalRoles,\n""" if False else """            source = product.provenance.catalogSource ?: nutrition.source,\n            nutritionalRoles = classification.nutritionalRoles,\n""",
    """            source = product.provenance.catalogSource ?: nutrition.source,\n            portionBasisGrams = classification.portionBasisGrams,\n            nutritionalRoles = classification.nutritionalRoles,\n""",
)

# Provisional SQLite bridge: prefer the future canonical name, otherwise migrate the old preferred_grams.
replace_once(
    "app/src/main/java/es/david/rumbo/data/catalog/SqliteCatalogRepository.kt",
    """        return database.rawQuery(\n            \"\"\"\n                SELECT classifier_version, classified, status\n                FROM classifications WHERE product_id = ?\n            \"\"\".trimIndent(),\n            arrayOf(productId)\n        ).use { cursor ->\n            if (!cursor.moveToFirst()) null else CatalogClassification(\n                classifierVersion = cursor.string(\"classifier_version\"),\n                classified = cursor.intOrNull(\"classified\") == 1,\n                status = cursor.string(\"status\"),\n                roles = roles\n            )\n        }\n""",
    """        val portionExpression = when {\n            database.hasColumn(\"classifications\", \"portion_basis_grams\") -> \"portion_basis_grams\"\n            database.hasColumn(\"classifications\", \"preferred_grams\") -> \"preferred_grams\"\n            else -> \"NULL\"\n        }\n        return database.rawQuery(\n            \"\"\"\n                SELECT classifier_version, classified, status,\n                       $portionExpression AS portion_basis_grams\n                FROM classifications WHERE product_id = ?\n            \"\"\".trimIndent(),\n            arrayOf(productId)\n        ).use { cursor ->\n            if (!cursor.moveToFirst()) null else CatalogClassification(\n                classifierVersion = cursor.string(\"classifier_version\"),\n                classified = cursor.intOrNull(\"classified\") == 1,\n                status = cursor.string(\"status\"),\n                roles = roles,\n                portionBasisGrams = cursor.doubleOrNull(\"portion_basis_grams\")\n            )\n        }\n""",
)
replace_once(
    "app/src/main/java/es/david/rumbo/data/catalog/SqliteCatalogRepository.kt",
    """private fun Cursor.string(column: String): String? {\n""",
    """private fun SQLiteDatabase.hasColumn(table: String, column: String): Boolean =\n    rawQuery(\"PRAGMA table_info($table)\", null).use { cursor ->\n        val nameIndex = cursor.getColumnIndexOrThrow(\"name\")\n        while (cursor.moveToNext()) {\n            if (cursor.getString(nameIndex) == column) return@use true\n        }\n        false\n    }\n\nprivate fun Cursor.string(column: String): String? {\n""",
)

# Backup compatibility. Schema 25 adds optional portionBasisGrams.
replace_once(
    "app/src/main/java/es/david/rumbo/data/AppRepository.kt",
    """        put(\"schemaVersion\", 24)\n""",
    """        put(\"schemaVersion\", 25)\n""",
)
replace_once(
    "app/src/main/java/es/david/rumbo/data/AppRepository.kt",
    """                put(\"unitDivisions\", food.unitDivisions)\n                put(\"nutritionalRoles\", JSONArray(food.nutritionalRoles.toList()))\n""",
    """                put(\"unitDivisions\", food.unitDivisions)\n                putNullable(\"portionBasisGrams\", food.portionBasisGrams)\n                put(\"nutritionalRoles\", JSONArray(food.nutritionalRoles.toList()))\n""",
)
replace_once(
    "app/src/main/java/es/david/rumbo/data/AppRepository.kt",
    """                    unitDivisions = item.optInt(\"unitDivisions\", 1).coerceIn(1, 100),\n                    nutritionalRoles = item.optJSONArray(\"nutritionalRoles\")?.let { values ->\n""",
    """                    unitDivisions = item.optInt(\"unitDivisions\", 1).coerceIn(1, 100),\n                    portionBasisGrams = item.optionalDouble(\"portionBasisGrams\")\n                        ?: baseFoodsById[item.getLong(\"id\")]?.portionBasisGrams,\n                    nutritionalRoles = item.optJSONArray(\"nutritionalRoles\")?.let { values ->\n""",
)

print("Migración portionBasisGrams aplicada")
