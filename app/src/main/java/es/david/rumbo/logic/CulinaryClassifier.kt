package es.david.rumbo.logic

import es.david.rumbo.model.Food
import java.text.Normalizer

enum class CulinaryRole {
    STARCH_BASE,
    BREAKFAST_CEREAL,
    LIQUID_OR_CREAMY_BASE,
    DEPENDENT_PREPARATION
}

/**
 * Conservative culinary classification derived from catalog data. Unknown
 * products deliberately remain unclassified instead of being blocked by a
 * low-confidence guess.
 */
object CulinaryClassifier {
    fun roles(food: Food): Set<CulinaryRole> {
        val name = normalize(food.name)
        val dependent = isDependentPreparation(name)
        return buildSet {
            if (isStarchBase(name)) add(CulinaryRole.STARCH_BASE)
            if (isBreakfastCereal(name)) add(CulinaryRole.BREAKFAST_CEREAL)
            if (!dependent && isLiquidOrCreamyBase(name)) {
                add(CulinaryRole.LIQUID_OR_CREAMY_BASE)
            }
            if (dependent) add(CulinaryRole.DEPENDENT_PREPARATION)
        }
    }

    private fun isStarchBase(name: String): Boolean = containsAnyPhrase(
        name,
        "arroz",
        "pasta",
        "macarron",
        "macarrones",
        "helice",
        "helices",
        "espagueti",
        "espaguetis",
        "spaghetti",
        "tallarin",
        "tallarines",
        "fideo",
        "fideos",
        "cuscus",
        "couscous",
        "quinoa",
        "patata",
        "patatas"
    )

    private fun isBreakfastCereal(name: String): Boolean = containsAnyPhrase(
        name,
        "corn flakes",
        "copos de maiz",
        "copos de avena",
        "cereales desayuno",
        "cereal desayuno",
        "muesli",
        "granola"
    )

    private fun isLiquidOrCreamyBase(name: String): Boolean {
        val liquidMilk = containsAnyPhrase(name, "leche") &&
            !containsAnyPhrase(
                name,
                "chocolate con leche",
                "leche condensada",
                "leche en polvo",
                "proteina de leche"
            )
        return liquidMilk || containsAnyPhrase(
                name,
                "bebida de soja",
                "bebida soja",
                "bebida de avena",
                "bebida avena",
                "bebida de almendra",
                "bebida almendra",
                "yogur",
                "yoghurt",
                "kefir",
                "queso fresco batido"
            )
    }

    private fun isDependentPreparation(name: String): Boolean =
        containsAnyPhrase(
            name,
            "polvo de proteina",
            "polvo de proteinas",
            "proteina en polvo",
            "proteinas en polvo",
            "proteina whey",
            "whey protein",
            "natural isolate"
        )

    private fun containsAnyPhrase(value: String, vararg phrases: String): Boolean =
        phrases.any { phrase ->
            value == phrase || value.startsWith("$phrase ") ||
                value.endsWith(" $phrase") || value.contains(" $phrase ")
        }

    private fun normalize(value: String): String = Normalizer
        .normalize(value.lowercase(), Normalizer.Form.NFD)
        .replace("\\p{Mn}+".toRegex(), "")
        .replace("[^a-z0-9]+".toRegex(), " ")
        .trim()
}
