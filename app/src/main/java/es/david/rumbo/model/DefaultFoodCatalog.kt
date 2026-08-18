package es.david.rumbo.model

object DefaultFoodCatalog {
    val items: List<Food> = listOf(
        food(1, "Leche semidesnatada Hacendado", FoodCategory.CARBOHYDRATE, 46.0, 1.6, 4.8, 3.1, 0.0),
        food(2, "Crema de arroz con leche", FoodCategory.CARBOHYDRATE, 111.513, 0.657, 24.1, 2.3, 0.4),
        food(3, "Arroz", FoodCategory.CARBOHYDRATE, 343.6, 2.8, 72.0, 7.6, 1.3),
        food(4, "Pan de pita", FoodCategory.CARBOHYDRATE, 236.6, 1.0, 48.5, 8.4, 4.0),
        food(5, "Pan integral", FoodCategory.CARBOHYDRATE, 247.5, 1.9, 47.1, 10.5, 6.5),
        food(6, "Pan de molde integral Hacendado", FoodCategory.CARBOHYDRATE, 228.4, 4.8, 36.0, 10.3, 6.0),
        food(7, "Pan tostado integral", FoodCategory.CARBOHYDRATE, 360.4, 6.4, 58.7, 17.0, 7.0),
        food(8, "Patata", FoodCategory.CARBOHYDRATE, 78.9, 0.1, 17.5, 2.0, 1.8),
        food(9, "Boniato", FoodCategory.CARBOHYDRATE, 87.7, 0.1, 20.1, 1.6, 3.0),
        food(10, "Plátanos", FoodCategory.CARBOHYDRATE, 98.3, 0.3, 22.8, 1.1, 2.6),
        food(11, "Corn flakes integrales", FoodCategory.CARBOHYDRATE, 361.5, 1.5, 80.0, 7.0, 4.0),
        food(12, "Spaghetti integral Hacendado", FoodCategory.CARBOHYDRATE, 323.6, 2.4, 62.0, 13.5, 8.0),
        food(13, "Spaghetti al huevo Hacendado", FoodCategory.CARBOHYDRATE, 348.3, 2.7, 67.0, 14.0, 2.5),
        food(14, "Spaghetti fino Hacendado", FoodCategory.CARBOHYDRATE, 353.5, 1.5, 72.0, 13.0, 3.5),
        food(15, "Batata Hacendado ultracongelada", FoodCategory.CARBOHYDRATE, 155.4, 5.0, 26.0, 1.6, 3.0,
            links = listOf("https://tienda.mercadona.es/product/15287/bastones-batata-hacendado-ultracongelada-paquete")),
        food(16, "Arroz integral largo Hacendado", FoodCategory.CARBOHYDRATE, 326.4, 2.8, 72.0, 3.3, 3.3,
            links = listOf("https://tienda.mercadona.es/product/5184/arroz-integral-largo-hacendado-paquete")),
        food(17, "Arroz basmati Hacendado", FoodCategory.CARBOHYDRATE, 353.4, 0.6, 78.0, 9.0, null,
            links = listOf(
                "https://tienda.mercadona.es/product/5002/arroz-basmati-aromatico-hacendado-paquete",
                "https://www.myrealfood.app/es/product/8480000050021",
                "https://finditapp.es/product/5002/arroz-basmati-aromatico-hacendado"
            )),
        food(18, "Melocotón", FoodCategory.FRUIT, 44.3, 0.3, 9.5, 0.9, 2.0),
        food(19, "Melón", FoodCategory.FRUIT, 37.8, 0.2, 8.2, 0.8, 0.8),
        food(20, "Sandía", FoodCategory.FRUIT, 34.6, 0.2, 7.6, 0.6, 0.4),
        food(21, "Aceitunas", FoodCategory.FAT, 145.0, 15.0, 0.9, 1.6, 3.0),
        food(22, "AOVE", FoodCategory.FAT, 819.0, 91.0, 0.0, 0.0, 0.0,
            links = listOf("https://tienda.mercadona.es/product/4740/aceite-oliva-virgen-extra-hacendado-botella")),
        food(23, "Crema de cacahuete", FoodCategory.FAT, 591.0, 47.0, 12.0, 30.0, 6.0),
        food(24, "Guacamole", FoodCategory.FAT, 138.9, 13.7, 2.0, 1.9, 4.5),
        food(25, "Nueces", FoodCategory.FAT, 703.2, 69.6, 2.2, 17.0, 6.7),
        food(26, "Tomate frito", FoodCategory.FAT, 198.6, 15.0, 14.3, 1.6, 1.4),
        food(27, "Tomate frito receta artesana Hacendado", FoodCategory.FAT, 198.6, 15.0, 14.3, 1.6, 1.4),
        food(28, "Queso lonchas tierno mezcla Entrepinares", FoodCategory.FAT, 374.0, 32.0, 0.5, 21.0, 0.0),
        food(29, "Gazpacho fresco", FoodCategory.FAT, 75.4, 7.0, 2.5, 0.6, 0.8),
        food(30, "Melva en aceite de oliva", FoodCategory.PROTEIN, 179.1, 8.3, 1.4, 24.7, 0.0),
        food(31, "Polvo de proteína", FoodCategory.PROTEIN, 394.76, 5.96, 7.18, 78.1, 0.0),
        food(32, "Yogur +proteínas", FoodCategory.PROTEIN, 57.7, 0.5, 5.0, 8.3, 0.0),
        food(33, "Lomo de cerdo adobado", FoodCategory.PROTEIN, 117.2, 3.6, 0.8, 20.4, 0.0,
            links = listOf("https://tienda.mercadona.es/product/2715/lomo-cerdo-adobado-bandeja")),
        food(34, "Lubina", FoodCategory.PROTEIN, 90.0, 2.0, 0.0, 18.0, 0.0,
            links = listOf("https://tienda.mercadona.es/product/81241.5/lubina-filetes-sin-cabeza-sin-espina-pieza")),
        food(35, "Dorada", FoodCategory.PROTEIN, 50.43, 0.67, 0.1, 11.0, 0.0),
        food(36, "Pechuga de pollo", FoodCategory.PROTEIN, 108.1, 1.7, 0.9, 22.3, 0.0),
        food(37, "Pechuga de pavo", FoodCategory.PROTEIN, 113.2, 2.0, 0.0, 23.8, 0.0),
        food(38, "Lomos de salmón", FoodCategory.PROTEIN, 224.0, 16.0, 0.0, 20.0, 0.0),
        food(39, "Filetes de ternera", FoodCategory.PROTEIN, 109.0, 3.0, 0.5, 20.0, 0.0),
        food(40, "Hamburguesa de ternera", FoodCategory.PROTEIN, 205.6, 14.0, 2.9, 17.0, 0.0),
        food(41, "Jamón serrano gran reserva Consum", FoodCategory.PROTEIN, 300.4, 20.0, 0.1, 30.0, 0.0),
        food(42, "Polvo de proteínas Natural Isolate", FoodCategory.PROTEIN, 358.0, 2.0, 2.0, 83.0, 0.0),
        food(43, "Huevos revueltos", FoodCategory.PROTEIN, 140.6, 10.2, 1.2, 11.0, 0.0),
        food(44, "Pechuga 92% pavo Hacendado lonchas", FoodCategory.PROTEIN, 90.1, 1.3, 0.1, 19.5, 0.0,
            links = listOf("https://tienda.mercadona.es/product/5710/pechuga-pavo-92-hacendado-lonchas-paquete")),
        food(45, "Carne picada vacuno y cerdo", FoodCategory.PROTEIN, 184.0, 12.0, 2.0, 17.0, 0.0),
        food(46, "Carne picada vacuno", FoodCategory.PROTEIN, 188.0, 12.0, 3.0, 17.0, 0.0),
        food(47, "Burger de vacuno y cerdo", FoodCategory.PROTEIN, 222.8, 16.0, 2.7, 17.0, 0.0),
        food(48, "Filetes de pechuga de pavo", FoodCategory.PROTEIN, 104.1, 0.9, 0.0, 24.0, 0.0),
        food(49, "Pimiento rojo", FoodCategory.VEGETABLE, 35.1, 0.3, 6.0, 2.1, 1.8),
        food(50, "Pimiento verde para freír", FoodCategory.VEGETABLE, 27.0, 0.2, 4.6, 1.7, 1.7,
            links = listOf("https://tienda.mercadona.es/product/69320/pimiento-verde-freir-pieza")),
        food(51, "Calabacín", FoodCategory.VEGETABLE, 19.9, 0.3, 3.1, 1.2, 1.1),
        food(52, "Tomate rosa", FoodCategory.VEGETABLE, 21.0, 0.2, 3.9, 0.9, 1.2,
            links = listOf("https://tienda.mercadona.es/product/69444/tomate-rosa-pieza"))
    )

    private fun food(
        id: Long,
        name: String,
        category: FoodCategory,
        calories: Double,
        fat: Double,
        carbohydrates: Double,
        protein: Double,
        fiber: Double?,
        links: List<String> = emptyList()
    ) = Food(
        id,
        name,
        category,
        calories,
        fat,
        carbohydrates,
        protein,
        fiber,
        links = links.ifEmpty { listOf(mercadonaSearch(name)) },
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

    private fun mercadonaSearch(name: String): String =
        "https://tienda.mercadona.es/search-results?query=" +
            java.net.URLEncoder.encode(name, "UTF-8").replace("+", "%20")
}
