package es.david.rumbo.logic

import es.david.rumbo.model.Dish
import es.david.rumbo.model.DishIngredient
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealType
import java.text.Normalizer

data class RecipeIngredient(
    val key: String,
    val grams: Double
)

data class ImportedRecipe(
    val sourceId: String,
    val name: String,
    val ingredients: List<RecipeIngredient>,
    val allowedMealTypes: Set<MealType> = setOf(MealType.LUNCH, MealType.DINNER)
)

data class RecipeRecommendation(
    val recipe: ImportedRecipe,
    val foodsByIngredient: Map<String, Food>
) {
    fun toDish(id: Long): Dish = Dish(
        id = id,
        name = recipe.name,
        ingredients = recipe.ingredients.map { ingredient ->
            DishIngredient(
                foodId = requireNotNull(foodsByIngredient[ingredient.key]).id,
                grams = ingredient.grams
            )
        },
        allowedMealTypes = recipe.allowedMealTypes
    )
}

/**
 * Matches commercial AESAN products to the deliberately small generic vocabulary used by
 * imported recipes. It prefers false negatives to false positives: a product is only matched
 * when a positive term appears in its commercial/legal classification and no preparation term
 * makes it a materially different food.
 */
object GenericIngredientClassifier {
    private data class Rule(
        val key: String,
        val requiredAny: List<String>,
        val forbidden: List<String> = commonPreparedTerms
    )

    private val commonPreparedTerms = listOf(
        "nugget", "croqueta", "empanad", "rebozad", "rellen", "pizza", "hamburgues",
        "salchicha", "salsa", "caldo", "sopa", "crema", "paté", "pate", "snack",
        "sabor ", "aroma", "plato preparad", "listo para", "precocinad"
    )

    private val rules = listOf(
        Rule("pechuga_pollo", listOf("pechuga de pollo", "filete de pechuga de pollo")),
        Rule("pechuga_pavo", listOf("pechuga de pavo"), forbidden = commonPreparedTerms + listOf("fiambre", "loncha", "cocid")),
        Rule("pollo", listOf("pollo", "contramuslo de pollo", "muslo de pollo")),
        Rule("salmon", listOf("salmon")),
        Rule("merluza", listOf("merluza")),
        Rule("atun_conserva", listOf("atun al natural", "atun en aceite", "atun claro")),
        Rule("huevo", listOf("huevo de gallina", "huevos frescos", "huevo fresco"), forbidden = commonPreparedTerms + listOf("chocolate")),
        Rule("arroz", listOf("arroz basmati", "arroz integral", "arroz redondo", "arroz largo", "arroz vaporizado"), forbidden = commonPreparedTerms + listOf("tortita", "bebida")),
        Rule("pasta", listOf("espagueti", "spaghetti", "macarron", "pasta alimenticia", "tallarines"), forbidden = commonPreparedTerms + listOf("salsa", "rellena")),
        Rule("patata", listOf("patata"), forbidden = commonPreparedTerms + listOf("frita", "chips", "tortilla", "pure")),
        Rule("boniato", listOf("boniato", "batata")),
        Rule("lenteja", listOf("lenteja"), forbidden = commonPreparedTerms + listOf("plato preparad")),
        Rule("garbanzo", listOf("garbanzo"), forbidden = commonPreparedTerms + listOf("humus", "hummus", "snack")),
        Rule("alubia", listOf("alubia", "judia blanca", "frijol"), forbidden = commonPreparedTerms),
        Rule("avena", listOf("copos de avena", "avena integral"), forbidden = commonPreparedTerms + listOf("galleta", "barrita", "bebida")),
        Rule("pan", listOf("pan integral", "pan de molde", "pan tostado", "barra de pan"), forbidden = commonPreparedTerms + listOf("rallado")),
        Rule("calabacin", listOf("calabacin")),
        Rule("berenjena", listOf("berenjena")),
        Rule("tomate", listOf("tomate fresco", "tomate pera", "tomate rama", "tomate rosa", "tomate ensalada"), forbidden = commonPreparedTerms + listOf("frito", "triturado", "concentrado", "ketchup")),
        Rule("cebolla", listOf("cebolla"), forbidden = commonPreparedTerms + listOf("frita", "caramelizada")),
        Rule("pimiento", listOf("pimiento verde", "pimiento rojo", "pimiento amarillo"), forbidden = commonPreparedTerms + listOf("asado", "relleno")),
        Rule("brocoli", listOf("brocoli")),
        Rule("zanahoria", listOf("zanahoria"), forbidden = commonPreparedTerms),
        Rule("espinaca", listOf("espinaca")),
        Rule("champinon", listOf("champinon", "champiñon")),
        Rule("aguacate", listOf("aguacate"), forbidden = commonPreparedTerms + listOf("guacamole")),
        Rule("platano", listOf("platano", "banana"), forbidden = commonPreparedTerms + listOf("sabor")),
        Rule("manzana", listOf("manzana"), forbidden = commonPreparedTerms + listOf("zumo", "compota", "sabor")),
        Rule("yogur_natural", listOf("yogur natural", "yoghourt natural"), forbidden = commonPreparedTerms + listOf("azucarado", "sabor")),
        Rule("queso", listOf("queso fresco", "mozzarella", "queso emmental", "queso gouda"), forbidden = commonPreparedTerms + listOf("salsa", "fundido")),
        Rule("nuez", listOf("nuez", "nueces"), forbidden = commonPreparedTerms + listOf("aceite", "bebida", "sabor")),
        Rule("almendra", listOf("almendra"), forbidden = commonPreparedTerms + listOf("aceite", "bebida", "sabor", "turron")),
        Rule("aceite_oliva", listOf("aceite de oliva virgen", "aceite oliva virgen"))
    )

    fun classify(food: Food): Set<String> {
        val primary = normalize(
            listOfNotNull(food.name, food.legalName, food.family, food.subcategory)
                .joinToString(" ")
        )
        if (primary.isBlank()) return emptySet()
        return rules.asSequence()
            .filter { rule ->
                rule.requiredAny.any(primary::contains) &&
                    rule.forbidden.none(primary::contains)
            }
            .mapTo(linkedSetOf()) { it.key }
    }

    private fun normalize(value: String): String =
        Normalizer.normalize(value.lowercase(), Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim()
}

object RecipeRecommendationEngine {
    fun recommend(
        foods: List<Food>,
        repertoireFoodIds: Set<Long>,
        existingDishes: List<Dish>,
        maxResults: Int = 8
    ): List<RecipeRecommendation> {
        if (maxResults <= 0 || repertoireFoodIds.isEmpty()) return emptyList()
        val repertoire = foods.filter { it.id in repertoireFoodIds }
        val candidatesByKey = linkedMapOf<String, MutableList<Food>>()
        repertoire.forEach { food ->
            GenericIngredientClassifier.classify(food).forEach { key ->
                candidatesByKey.getOrPut(key, ::mutableListOf).add(food)
            }
        }
        val existingSignatures = existingDishes.mapTo(hashSetOf()) { dish ->
            dish.ingredients.map { it.foodId }.toSet()
        }
        return ImportedRecipeCatalog.recipes.asSequence()
            .mapNotNull { recipe ->
                val mapping = recipe.ingredients.associate { ingredient ->
                    ingredient.key to (candidatesByKey[ingredient.key]
                        ?.sortedWith(compareBy<Food> { it.name.length }.thenBy { it.name })
                        ?.firstOrNull() ?: return@mapNotNull null)
                }
                RecipeRecommendation(recipe, mapping)
            }
            .filterNot { recommendation ->
                recommendation.foodsByIngredient.values.map { it.id }.toSet() in existingSignatures
            }
            .sortedWith(
                compareByDescending<RecipeRecommendation> { it.recipe.ingredients.size }
                    .thenBy { it.recipe.name }
            )
            .take(maxResults)
            .toList()
    }
}
