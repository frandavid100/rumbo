package es.david.rumbo.data.catalog

import android.content.Context
import es.david.rumbo.model.Food

/** Transitional bridge: the rest of Rumbo still consumes Food. */
object CatalogBackedFoodCatalog {
    fun load(context: Context): List<Food> {
        val repository = CatalogRepositoryProvider.fromAssets(context)
        return repository.search(
            CatalogQuery(
                eligibility = setOf(CatalogEligibility.MENU_ELIGIBLE),
                limit = 20_000
            )
        ).mapNotNull(CatalogFoodAdapter::toFood)
            .distinctBy { it.id }
    }
}
