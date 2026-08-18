package es.david.rumbo.data.catalog

import es.david.rumbo.model.FoodCategory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CatalogFoodAdapterTest {
    @Test
    fun realCarrefourOilKeepsProductAndListingIdentityAndCanonicalRoles() {
        val productId = "carrefour:aceite-de-girasol-carrefour-classic-1-l-carrefour"
        val product = product(
            id = productId,
            name = "Aceite de girasol Carrefour Classic' 1 l.",
            nutritionalRoles = setOf("CONCENTRATED_FAT"),
            culinaryRoles = setOf("COOKING_MEDIUM", "SAUCE_DRESSING"),
            nutrition = completeNutrition(calories = 900.0, protein = 0.0, carbs = 0.0, fat = 100.0)
        )

        assertEquals(productId, product.id)
        assertEquals("aceite-de-girasol-carrefour-classic-1-l-carrefour", product.listings.single().retailerSku)
        assertEquals("CARREFOUR", product.listings.single().retailer)

        val food = CatalogFoodAdapter.toFood(product)!!
        assertEquals(FoodCategory.FAT, food.category)
        assertEquals(setOf("COOKING_MEDIUM", "SAUCE_DRESSING"), food.culinaryRoles)
        assertEquals("CARREFOUR", food.retailer)
        assertTrue(food.hasComparableNutrition())
    }

    @Test
    fun realCarrefourMilkExposesBothClassificationAxes() {
        val product = product(
            id = "carrefour:leche-entera-carrefour-brik-1-l-carrefour",
            name = "Leche entera Carrefour brik 1 l.",
            nutritionalRoles = setOf(
                "COMPLEMENTARY_PROTEIN", "COMPLEMENTARY_CARBOHYDRATE", "COMPLEMENTARY_FAT"
            ),
            culinaryRoles = setOf("CEREAL_BASE", "POWDER_BASE", "BEVERAGE", "STANDALONE"),
            nutrition = completeNutrition(62.0, 3.1, 4.7, 3.6)
        )

        assertEquals(
            setOf("COMPLEMENTARY_PROTEIN", "COMPLEMENTARY_CARBOHYDRATE", "COMPLEMENTARY_FAT"),
            product.classification!!.nutritionalRoles
        )
        assertEquals(
            setOf("CEREAL_BASE", "POWDER_BASE", "BEVERAGE", "STANDALONE"),
            product.classification!!.culinaryRoles
        )
        val food = CatalogFoodAdapter.toFood(product)!!
        assertEquals(product.classification!!.nutritionalRoles, food.nutritionalRoles)
        assertEquals(product.classification!!.culinaryRoles, food.culinaryRoles)
    }

    @Test
    fun menuEligibleLabelCannotBypassMissingCoreNutrition() {
        val incomplete = product(
            id = "carrefour:producto-incompleto",
            name = "Producto incompleto",
            nutritionalRoles = setOf("PRIMARY_PROTEIN"),
            culinaryRoles = setOf("PLATE_CENTER"),
            nutrition = completeNutrition(100.0, 20.0, 0.0, 2.0).copy(proteinGrams = null)
        )
        assertNull(CatalogFoodAdapter.toFood(incomplete))
    }

    @Test
    fun reviewAndExcludedProductsNeverEnterGeneratorFoodSet() {
        val review = product(
            id = "carrefour:producto-review",
            name = "Producto pendiente",
            nutritionalRoles = emptySet(),
            culinaryRoles = emptySet(),
            nutrition = completeNutrition(100.0, 3.0, 10.0, 5.0),
            eligibility = CatalogEligibility.REVIEW
        )
        val excluded = product(
            id = "carrefour:amaretto-disaronno-70-cl-carrefour",
            name = "Amaretto Disaronno 70 cl.",
            nutritionalRoles = emptySet(),
            culinaryRoles = setOf("BEVERAGE"),
            nutrition = null,
            eligibility = CatalogEligibility.EXCLUDED
        )
        assertNull(CatalogFoodAdapter.toFood(review))
        assertNull(CatalogFoodAdapter.toFood(excluded))
    }

    @Test
    fun stableBridgeIdIsDeterministicButDoesNotReplaceCatalogIdentity() {
        val first = "carrefour:arroz-bomba-sos-1-kg-carrefour"
        val second = "carrefour:pasta-espagueti-integral-carrefour-classic-500-g-carrefour"
        assertEquals(CatalogFoodAdapter.stableFoodId(first), CatalogFoodAdapter.stableFoodId(first))
        assertNotEquals(CatalogFoodAdapter.stableFoodId(first), CatalogFoodAdapter.stableFoodId(second))
        assertTrue(CatalogFoodAdapter.stableFoodId(first) > 0)
    }

    private fun product(
        id: String,
        name: String,
        nutritionalRoles: Set<String>,
        culinaryRoles: Set<String>,
        nutrition: CatalogNutrition?,
        eligibility: CatalogEligibility = CatalogEligibility.MENU_ELIGIBLE
    ): CatalogProduct {
        val roles = nutritionalRoles.map {
            CatalogRole(CatalogRoleAxis.NUTRITIONAL, it, 1.0, "test")
        } + culinaryRoles.map {
            CatalogRole(CatalogRoleAxis.CULINARY, it, 1.0, "test")
        }
        val sku = id.removePrefix("carrefour:")
        return CatalogProduct(
            id = id,
            gtin = null,
            name = name,
            brand = "Carrefour",
            legalName = null,
            ingredients = null,
            family = null,
            subcategory = null,
            provenance = CatalogProvenance(
                catalogSource = "RadarSuper mirror of Carrefour",
                productSource = "Carrefour",
                nutritionSource = "test-fixture",
                catalogVersion = "carrefour-dev-mirror-2",
                importerVersion = "test",
                classifierVersion = "test"
            ),
            listings = listOf(
                RetailerListing("CARREFOUR", sku, id, "https://www.carrefour.es/$sku", null, null, "ACTIVE")
            ),
            nutrition = nutrition,
            classification = CatalogClassification(
                classifierVersion = "test",
                classified = eligibility == CatalogEligibility.MENU_ELIGIBLE,
                status = eligibility.name,
                roles = roles
            ),
            eligibility = eligibility
        )
    }

    private fun completeNutrition(calories: Double, protein: Double, carbs: Double, fat: Double) =
        CatalogNutrition(
            calories = calories,
            proteinGrams = protein,
            carbohydrateGrams = carbs,
            fatGrams = fat,
            fiberGrams = null,
            saltGrams = null,
            evidenceLevel = "MATCHED",
            source = "test-fixture",
            observedAt = null
        )
}
