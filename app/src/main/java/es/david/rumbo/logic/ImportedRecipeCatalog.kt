package es.david.rumbo.logic

import es.david.rumbo.model.MealType

/**
 * Starter subset normalized from the CC BY 3.0 Open Recipes dataset.
 *
 * Open Recipes stores recipe discovery data rather than instructions. Rumbo therefore imports
 * only ordinary ingredient combinations and metric proportions; preparation text and images are
 * deliberately excluded. Ingredient keys are resolved locally against the user's repertoire.
 */
object ImportedRecipeCatalog {
    val recipes: List<ImportedRecipe> = listOf(
        recipe("arroz-pollo-calabacin", "Arroz con pollo y calabacín", "arroz" to 80, "pechuga_pollo" to 150, "calabacin" to 150, "aceite_oliva" to 10),
        recipe("arroz-pavo-pimiento", "Arroz con pavo y pimiento", "arroz" to 80, "pechuga_pavo" to 150, "pimiento" to 120, "aceite_oliva" to 10),
        recipe("arroz-salmon-brocoli", "Arroz con salmón y brócoli", "arroz" to 75, "salmon" to 150, "brocoli" to 160, "aceite_oliva" to 8),
        recipe("pasta-pollo-tomate", "Pasta con pollo y tomate", "pasta" to 85, "pechuga_pollo" to 150, "tomate" to 150, "aceite_oliva" to 10),
        recipe("pasta-pavo-calabacin", "Pasta con pavo y calabacín", "pasta" to 85, "pechuga_pavo" to 150, "calabacin" to 150, "aceite_oliva" to 10),
        recipe("pasta-atun-tomate", "Pasta con atún y tomate", "pasta" to 85, "atun_conserva" to 100, "tomate" to 160, "aceite_oliva" to 8),
        recipe("pollo-patata-pimiento", "Pollo con patata y pimiento", "pechuga_pollo" to 170, "patata" to 220, "pimiento" to 120, "aceite_oliva" to 10),
        recipe("salmon-patata-calabacin", "Salmón con patata y calabacín", "salmon" to 160, "patata" to 200, "calabacin" to 150, "aceite_oliva" to 8),
        recipe("merluza-patata-cebolla", "Merluza con patata y cebolla", "merluza" to 180, "patata" to 200, "cebolla" to 80, "aceite_oliva" to 10),
        recipe("boniato-pollo-brocoli", "Pollo con boniato y brócoli", "pechuga_pollo" to 160, "boniato" to 220, "brocoli" to 150, "aceite_oliva" to 10),
        recipe("lentejas-arroz-verduras", "Lentejas con arroz y verduras", "lenteja" to 80, "arroz" to 45, "zanahoria" to 100, "pimiento" to 80, "aceite_oliva" to 10),
        recipe("garbanzos-pollo-espinacas", "Garbanzos con pollo y espinacas", "garbanzo" to 90, "pechuga_pollo" to 140, "espinaca" to 140, "aceite_oliva" to 10),
        recipe("garbanzos-atun-tomate", "Ensalada de garbanzos, atún y tomate", "garbanzo" to 90, "atun_conserva" to 90, "tomate" to 150, "aceite_oliva" to 10),
        recipe("alubias-pavo-verduras", "Alubias con pavo y verduras", "alubia" to 90, "pechuga_pavo" to 140, "zanahoria" to 100, "pimiento" to 80, "aceite_oliva" to 10),
        recipe("berenjena-pollo-tomate", "Berenjena con pollo y tomate", "berenjena" to 220, "pechuga_pollo" to 160, "tomate" to 150, "aceite_oliva" to 10),
        recipe("calabacin-pavo-queso", "Calabacín con pavo y queso", "calabacin" to 220, "pechuga_pavo" to 150, "queso" to 45, "aceite_oliva" to 8),
        recipe("tortilla-patata-calabacin", "Tortilla de patata y calabacín", "huevo" to 120, "patata" to 180, "calabacin" to 120, "aceite_oliva" to 10),
        recipe("revuelto-champinon-espinaca", "Revuelto de champiñones y espinacas", "huevo" to 120, "champinon" to 150, "espinaca" to 100, "aceite_oliva" to 8),
        recipe("ensalada-pollo-aguacate-tomate", "Ensalada de pollo, aguacate y tomate", "pechuga_pollo" to 150, "aguacate" to 80, "tomate" to 150, "aceite_oliva" to 8),
        recipe("ensalada-salmon-aguacate", "Ensalada de salmón y aguacate", "salmon" to 140, "aguacate" to 80, "tomate" to 140, "aceite_oliva" to 8),
        recipe("tostada-atun-aguacate", "Tostada con atún y aguacate", setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK), "pan" to 80, "atun_conserva" to 80, "aguacate" to 70),
        recipe("tostada-huevo-tomate", "Tostada con huevo y tomate", setOf(MealType.BREAKFAST, MealType.MORNING_SNACK), "pan" to 80, "huevo" to 60, "tomate" to 100, "aceite_oliva" to 5),
        recipe("avena-yogur-platano", "Avena con yogur y plátano", setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK), "avena" to 50, "yogur_natural" to 150, "platano" to 120),
        recipe("yogur-manzana-nueces", "Yogur con manzana y nueces", setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK), "yogur_natural" to 150, "manzana" to 150, "nuez" to 25),
        recipe("yogur-platano-almendras", "Yogur con plátano y almendras", setOf(MealType.BREAKFAST, MealType.MORNING_SNACK, MealType.AFTERNOON_SNACK), "yogur_natural" to 150, "platano" to 120, "almendra" to 25)
    )

    private fun recipe(id: String, name: String, vararg ingredients: Pair<String, Int>) =
        recipe(id, name, setOf(MealType.LUNCH, MealType.DINNER), *ingredients)

    private fun recipe(
        id: String,
        name: String,
        meals: Set<MealType>,
        vararg ingredients: Pair<String, Int>
    ) = ImportedRecipe(
        sourceId = id,
        name = name,
        ingredients = ingredients.map { (key, grams) -> RecipeIngredient(key, grams.toDouble()) },
        allowedMealTypes = meals
    )
}
