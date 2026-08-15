package es.david.rumbo.data

import android.content.Context
import androidx.core.content.edit
import es.david.rumbo.logic.RecommendationEngine
import es.david.rumbo.logic.GeneratedWeeklyMenu
import es.david.rumbo.model.ActivityLevel
import es.david.rumbo.model.MercadonaFoodCatalog
import es.david.rumbo.model.AppData
import es.david.rumbo.model.DietCompliance
import es.david.rumbo.model.Dish
import es.david.rumbo.model.DishIngredient
import es.david.rumbo.model.DefaultFoodCatalog
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.CulinaryType
import es.david.rumbo.model.Measurement
import es.david.rumbo.model.MealType
import es.david.rumbo.model.MenuHistoryEntry
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.PlanningSlot
import es.david.rumbo.model.MealDayAmounts
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedDish
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanWeek
import es.david.rumbo.model.ProfileData
import es.david.rumbo.model.Sex
import es.david.rumbo.model.UserProfile
import es.david.rumbo.model.WeightGoal
import es.david.rumbo.model.WeekDay
import es.david.rumbo.model.sanitizedDayAmounts
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate

class AppRepository(context: Context) {
    private val preferences = context.getSharedPreferences("rumbo_data", Context.MODE_PRIVATE)
    private val baseFoods: List<Food> by lazy {
        (DefaultFoodCatalog.items + MercadonaFoodCatalog.load(context))
            .distinctBy { it.id }
            .sortedWith(foodComparator)
    }
    private val baseFoodsById: Map<Long, Food> by lazy { baseFoods.associateBy { it.id } }

    fun load(): AppData {
        val raw = preferences.getString(KEY_DATA, null)
            ?: return AppData(foods = baseFoods)
        return runCatching { normalize(decode(raw)) }
            .getOrElse { AppData(foods = baseFoods) }
    }

    fun saveProfile(profile: UserProfile): AppData {
        val current = load()
        val existing = current.profiles.firstOrNull { it.profile.id == profile.id }
        val updatedProfile = ProfileData(
            profile = profile,
            measurements = recalculate(profile, existing?.measurements.orEmpty()),
            plannedMeals = existing?.plannedMeals.orEmpty(),
            planningRules = existing?.planningRules.orEmpty(),
            repertoireFoodIds = existing?.repertoireFoodIds.orEmpty(),
            dismissedSuggestionFoodIds = existing?.dismissedSuggestionFoodIds.orEmpty(),
            menuHistory = existing?.menuHistory.orEmpty()
        )
        val profiles = if (existing == null) {
            current.profiles + updatedProfile
        } else {
            current.profiles.map { if (it.profile.id == profile.id) updatedProfile else it }
        }
        return persistAndReturn(AppData(profiles, profile.id, current.foods, current.dishes))
    }

    fun saveProfileWithBaseline(profile: UserProfile, baseline: Measurement): AppData {
        require(baseline.weightKg != null || baseline.waistCm != null) {
            "El perfil inicial necesita al menos el peso o la cintura"
        }
        val current = load()
        val existing = current.profiles.firstOrNull { it.profile.id == profile.id }
        val source = existing?.measurements.orEmpty().filterNot { it.id == baseline.id } +
            baseline.copy(recommendation = null)
        val updatedProfile = ProfileData(
            profile = profile,
            measurements = recalculate(profile, source),
            plannedMeals = existing?.plannedMeals.orEmpty(),
            planningRules = existing?.planningRules.orEmpty(),
            repertoireFoodIds = existing?.repertoireFoodIds.orEmpty(),
            dismissedSuggestionFoodIds = existing?.dismissedSuggestionFoodIds.orEmpty(),
            menuHistory = existing?.menuHistory.orEmpty()
        )
        val profiles = if (existing == null) {
            current.profiles + updatedProfile
        } else {
            current.profiles.map { if (it.profile.id == profile.id) updatedProfile else it }
        }
        return persistAndReturn(AppData(profiles, profile.id, current.foods, current.dishes))
    }

    fun switchProfile(profileId: Long): AppData {
        val current = load()
        if (current.profiles.none { it.profile.id == profileId }) return current
        return persistAndReturn(current.copy(activeProfileId = profileId))
    }

    fun deleteProfile(profileId: Long): AppData {
        val current = load()
        if (current.profiles.size <= 1) return current
        val remaining = current.profiles.filterNot { it.profile.id == profileId }
        val activeId = if (current.activeProfileId == profileId) remaining.first().profile.id
            else current.activeProfileId
        return persistAndReturn(AppData(remaining, activeId, current.foods, current.dishes))
    }

    fun addMeasurement(draft: Measurement): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        val source = active.measurements.filterNot { it.id == draft.id } + draft.copy(recommendation = null)
        return updateActive(current, active.copy(measurements = recalculate(active.profile, source)))
    }

    fun setGoal(goal: WeightGoal): AppData = setWeeklyRate(
        if (goal == WeightGoal.AUTOMATIC) null
        else RecommendationEngine.weeklyRateFor(goal, load().activeProfileData
            ?.let { RecommendationEngine.effectiveValues(it.measurements).weightKg })
    )

    fun setWeeklyRate(weeklyRateKg: Double?): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        val effective = RecommendationEngine.effectiveValues(active.measurements)
        if (weeklyRateKg == null && effective.goal == WeightGoal.AUTOMATIC) return current
        if (weeklyRateKg != null && effective.weeklyRateKg == weeklyRateKg) return current
        val goal = when {
            weeklyRateKg == null -> WeightGoal.AUTOMATIC
            weeklyRateKg < 0.0 -> WeightGoal.LOSE_SLOWLY
            weeklyRateKg > 0.0 -> WeightGoal.GAIN_SLOWLY
            else -> WeightGoal.MAINTAIN
        }
        return addMeasurement(
            Measurement(
                id = System.currentTimeMillis(),
                date = LocalDate.now(),
                goal = goal,
                weeklyRateKg = weeklyRateKg
            )
        )
    }

    fun deleteMeasurement(id: Long): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        val remaining = active.measurements.filterNot { it.id == id }
        return updateActive(current, active.copy(measurements = recalculate(active.profile, remaining)))
    }

    fun saveFood(food: Food): AppData {
        require(food.isValid()) { "El alimento no es válido" }
        val current = load()
        val foods = (current.foods.filterNot { it.id == food.id } + food)
            .sortedWith(foodComparator)
        return persistAndReturn(current.copy(foods = foods))
    }

    fun deleteFood(id: Long): AppData {
        val current = load()
        // A recipe is immutable after creation. Refuse to remove one of its
        // ingredients; the user can delete the complete dish first.
        if (current.dishes.any { dish -> dish.ingredients.any { it.foodId == id } }) return current
        val dishes = current.dishes
        val dishIds = dishes.mapTo(mutableSetOf()) { it.id }
        val profiles = current.profiles.map { profileData ->
            profileData.copy(
                plannedMeals = profileData.plannedMeals.mapNotNull { meal ->
                    val remaining = meal.items.filterNot { it.foodId == id }
                    val plannedDishes = meal.dishes.filter { it.dishId in dishIds }
                    meal.copy(items = remaining, dishes = plannedDishes).sanitizedDayAmounts()
                        .takeIf { remaining.isNotEmpty() || plannedDishes.isNotEmpty() }
                }
            )
        }
        return persistAndReturn(
            current.copy(
                profiles = profiles,
                foods = current.foods.filterNot { it.id == id },
                dishes = dishes
            )
        )
    }

    fun saveDish(dish: Dish): AppData {
        require(dish.isValid()) { "El plato no es válido" }
        val current = load()
        val existing = current.dishes.firstOrNull { it.id == dish.id }
        val savedDish = existing?.let { dish.copy(ingredients = it.ingredients) } ?: dish
        require(savedDish.ingredients.all { ingredient -> current.foods.any { it.id == ingredient.foodId } }) {
            "El plato contiene alimentos inexistentes"
        }
        val dishes = (current.dishes.filterNot { it.id == savedDish.id } + savedDish)
            .sortedWith(dishComparator)
        return persistAndReturn(current.copy(dishes = dishes))
    }

    fun deleteDish(id: Long): AppData {
        val current = load()
        val profiles = current.profiles.map { profileData ->
            profileData.copy(
                plannedMeals = profileData.plannedMeals.mapNotNull { meal ->
                    val dishes = meal.dishes.filterNot { it.dishId == id }
                    meal.copy(dishes = dishes).sanitizedDayAmounts()
                        .takeIf { meal.items.isNotEmpty() || dishes.isNotEmpty() }
                }
            )
        }
        return persistAndReturn(
            current.copy(profiles = profiles, dishes = current.dishes.filterNot { it.id == id })
        )
    }

    fun savePlannedMeal(meal: PlannedMeal): AppData {
        val sanitized = meal.sanitizedDayAmounts()
        require(sanitized.isValid()) { "La comida planificada no es válida" }
        val current = load()
        val active = current.activeProfileData ?: return current
        require(sanitized.items.all { item -> current.foods.any { it.id == item.foodId } }) {
            "La comida contiene alimentos inexistentes"
        }
        require(sanitized.dishes.all { item -> current.dishes.any { it.id == item.dishId } }) {
            "La comida contiene platos inexistentes"
        }
        val otherMeals = active.plannedMeals.filterNot {
            it.id == sanitized.id && it.planWeek == sanitized.planWeek
        }
        require(otherMeals.none {
            it.planWeek == sanitized.planWeek && it.type == sanitized.type &&
                it.days.any(sanitized.days::contains)
        }) {
            "Ya hay otra comida de este tipo en alguno de los días seleccionados"
        }
        val updated = active.copy(
            plannedMeals = (otherMeals + sanitized).sortedWith(plannedMealComparator)
        )
        return updateActive(current, updated)
    }

    fun savePlannedMeals(
        meals: List<PlannedMeal>,
        planWeek: PlanWeek = PlanWeek.CURRENT
    ): AppData {
        val sanitized = meals.map { it.copy(planWeek = planWeek).sanitizedDayAmounts() }
        val current = load()
        val active = current.activeProfileData ?: return current
        require(sanitized.all { it.isValid() }) { "Hay alguna comida planificada no válida" }
        val foodIds = current.foods.mapTo(mutableSetOf()) { it.id }
        val dishIds = current.dishes.mapTo(mutableSetOf()) { it.id }
        require(sanitized.flatMap { it.items }.all { it.foodId in foodIds }) {
            "Hay comidas con alimentos inexistentes"
        }
        require(sanitized.flatMap { it.dishes }.all { it.dishId in dishIds }) {
            "Hay comidas con platos inexistentes"
        }
        require(MealType.entries.all { type ->
            val days = sanitized.filter { it.type == type }.flatMap { it.days }
            days.distinct().size == days.size
        }) { "Hay comidas del mismo tipo que se solapan" }
        val preserved = active.plannedMeals.filterNot { it.planWeek == planWeek }
        return updateActive(
            current,
            active.copy(plannedMeals = (preserved + sanitized).sortedWith(plannedMealComparator))
        )
    }

    fun savePlanningRule(rule: PlanningRule): AppData {
        require(rule.isValid()) { "La regla de planificación no es válida" }
        val current = load()
        val active = current.activeProfileData ?: return current
        val exists = when (rule.itemKind) {
            PlannedItemKind.FOOD -> current.foods.any { it.id == rule.itemId }
            PlannedItemKind.DISH -> current.dishes.any { it.id == rule.itemId }
        }
        require(exists) { "El elemento configurado ya no existe" }
        val rules = active.planningRules.filterNot {
            it.ruleId == rule.ruleId
        } + rule
        val repertoire = if (rule.itemKind == PlannedItemKind.FOOD) {
            active.repertoireFoodIds + rule.itemId
        } else active.repertoireFoodIds
        return updateActive(current, active.copy(planningRules = rules, repertoireFoodIds = repertoire))
    }

    fun deletePlanningRule(kind: PlannedItemKind, itemId: Long): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        return updateActive(
            current,
            active.copy(planningRules = active.planningRules.filterNot {
                it.itemKind == kind && it.itemId == itemId
            })
        )
    }

    fun deletePlanningRule(ruleId: Long): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        return updateActive(current, active.copy(
            planningRules = active.planningRules.filterNot { it.ruleId == ruleId }
        ))
    }

    fun addToRepertoire(foodId: Long): AppData {
        val current = load()
        require(current.foods.any { it.id == foodId }) { "El alimento ya no existe" }
        val active = current.activeProfileData ?: return current
        return updateActive(current, active.copy(repertoireFoodIds = active.repertoireFoodIds + foodId))
    }

    fun dismissFoodSuggestion(foodId: Long): AppData {
        val current = load()
        require(current.foods.any { it.id == foodId }) { "El alimento ya no existe" }
        val active = current.activeProfileData ?: return current
        return updateActive(
            current,
            active.copy(dismissedSuggestionFoodIds = active.dismissedSuggestionFoodIds + foodId)
        )
    }

    fun removeFromRepertoire(foodId: Long): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        return updateActive(current, active.copy(
            repertoireFoodIds = active.repertoireFoodIds - foodId,
            planningRules = active.planningRules.filterNot {
                it.itemKind == PlannedItemKind.FOOD && it.itemId == foodId
            }
        ))
    }

    fun setRepertoireFoodActive(foodId: Long, isActive: Boolean): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        require(foodId in active.repertoireFoodIds) { "El alimento no pertenece al repertorio" }
        return updateActive(current, active.copy(planningRules = active.planningRules.map {
            if (it.itemKind == PlannedItemKind.FOOD && it.itemId == foodId) it.copy(isActive = isActive) else it
        }))
    }

    fun replaceRepertoireFood(oldFoodId: Long, newFoodId: Long): AppData {
        require(oldFoodId != newFoodId) { "Elige un producto diferente" }
        val current = load()
        require(current.foods.any { it.id == newFoodId }) { "El alimento sustituto ya no existe" }
        val active = current.activeProfileData ?: return current
        require(oldFoodId in active.repertoireFoodIds) { "El alimento no pertenece al repertorio" }
        val updatedProfile = active.copy(
            repertoireFoodIds = active.repertoireFoodIds - oldFoodId + newFoodId,
            planningRules = active.planningRules.filterNot {
                it.itemKind == PlannedItemKind.FOOD && it.itemId == newFoodId
            }.map {
                if (it.itemKind == PlannedItemKind.FOOD && it.itemId == oldFoodId) {
                    it.copy(itemId = newFoodId)
                } else it
            }
        )
        val dishes = current.dishes.map { dish ->
            if (dish.ingredients.none { it.foodId == oldFoodId }) dish else dish.copy(
                ingredients = dish.ingredients.map { ingredient ->
                    if (ingredient.foodId == oldFoodId) ingredient.copy(foodId = newFoodId) else ingredient
                }.groupBy { it.foodId }.map { (foodId, entries) ->
                    entries.first().copy(grams = entries.sumOf { it.grams })
                }
            )
        }
        return persistAndReturn(current.copy(
            dishes = dishes,
            profiles = current.profiles.map {
                if (it.profile.id == updatedProfile.profile.id) updatedProfile else it
            }
        ))
    }

    fun applyGeneratedMenu(
        result: GeneratedWeeklyMenu,
        planWeek: PlanWeek = PlanWeek.CURRENT
    ): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        val idOffset = if (planWeek == PlanWeek.NEXT) 500_000_000_000L else 0L
        val sanitized = result.meals.map {
            it.copy(id = it.id + idOffset, planWeek = planWeek).sanitizedDayAmounts()
        }
        require(sanitized.all { it.isValid() }) { "El menú generado no es válido" }
        val preserved = active.plannedMeals.filterNot { it.planWeek == planWeek }
        return updateActive(
            current,
            active.copy(
                plannedMeals = (preserved + sanitized).sortedWith(plannedMealComparator),
                menuHistory = result.history
            )
        )
    }

    fun deletePlannedMeal(id: Long): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        return updateActive(
            current,
            active.copy(plannedMeals = active.plannedMeals.filterNot { it.id == id })
        )
    }

    fun exportJson(): String = encode(load()).toString(2)

    fun importJson(raw: String): AppData {
        val decoded = decode(raw)
        validate(decoded)
        return persistAndReturn(normalize(decoded))
    }

    private fun updateActive(current: AppData, updated: ProfileData): AppData = persistAndReturn(
        current.copy(profiles = current.profiles.map {
            if (it.profile.id == updated.profile.id) updated else it
        })
    )

    private fun persistAndReturn(data: AppData): AppData {
        preferences.edit { putString(KEY_DATA, encode(data).toString()) }
        return data
    }

    private fun normalize(data: AppData): AppData {
        val foods = data.foods.ifEmpty { baseFoods }
        val foodIds = foods.mapTo(mutableSetOf()) { it.id }
        val dishes = data.dishes.mapNotNull { dish ->
            val ingredients = dish.ingredients.filter { it.foodId in foodIds }
            dish.copy(ingredients = ingredients).takeIf { ingredients.isNotEmpty() }
        }.sortedWith(dishComparator)
        val dishIds = dishes.mapTo(mutableSetOf()) { it.id }
        val profiles = data.profiles.map { profileData ->
            profileData.copy(
                measurements = recalculate(profileData.profile, profileData.measurements),
                plannedMeals = profileData.plannedMeals.mapNotNull { meal ->
                    val items = meal.items.filter { it.foodId in foodIds }
                    val plannedDishes = meal.dishes.filter { it.dishId in dishIds }
                    meal.copy(items = items, dishes = plannedDishes).sanitizedDayAmounts()
                        .takeIf { items.isNotEmpty() || plannedDishes.isNotEmpty() }
                }.sortedWith(plannedMealComparator),
                planningRules = profileData.planningRules.filter { rule ->
                    rule.isValid() && when (rule.itemKind) {
                        PlannedItemKind.FOOD -> rule.itemId in foodIds
                        PlannedItemKind.DISH -> rule.itemId in dishIds
                    }
                },
                repertoireFoodIds = profileData.repertoireFoodIds.filterTo(mutableSetOf()) { it in foodIds },
                dismissedSuggestionFoodIds = profileData.dismissedSuggestionFoodIds
                    .filterTo(mutableSetOf()) { it in foodIds },
                menuHistory = profileData.menuHistory.filter { entry ->
                    when (entry.itemKind) {
                        PlannedItemKind.FOOD -> entry.itemId in foodIds
                        PlannedItemKind.DISH -> entry.itemId in dishIds
                    }
                }
            )
        }
        val activeId = data.activeProfileId?.takeIf { id -> profiles.any { it.profile.id == id } }
            ?: profiles.firstOrNull()?.profile?.id
        return AppData(profiles, activeId, foods, dishes)
    }

    private fun validate(data: AppData) {
        require(data.profiles.isNotEmpty()) { "La copia no contiene perfiles" }
        require(data.profiles.map { it.profile.id }.distinct().size == data.profiles.size) {
            "Hay perfiles duplicados"
        }
        require(data.profiles.all { it.profile.isValid() }) { "Hay datos personales no válidos" }
        val measurements = data.profiles.flatMap { it.measurements }
        require(measurements.all { it.weightKg == null || it.weightKg in 30.0..350.0 }) {
            "Hay algún peso fuera de rango"
        }
        require(measurements.all { it.waistCm == null || it.waistCm in 35.0..250.0 }) {
            "Hay alguna cintura fuera de rango"
        }
        require(measurements.all { it.weeklyRateKg == null || it.weeklyRateKg.isFinite() }) {
            "Hay algún objetivo semanal que no es una cifra finita"
        }
        require(data.foods.all { it.isValid() }) { "Hay algún alimento no válido" }
        require(data.foods.map { it.id }.distinct().size == data.foods.size) {
            "Hay alimentos duplicados"
        }
        val foodIds = data.foods.mapTo(mutableSetOf()) { it.id }
        require(data.dishes.all { it.isValid() }) { "Hay algún plato no válido" }
        require(data.dishes.map { it.id }.distinct().size == data.dishes.size) {
            "Hay platos duplicados"
        }
        require(data.dishes.flatMap { it.ingredients }.all { it.foodId in foodIds }) {
            "Hay platos con alimentos inexistentes"
        }
        val dishIds = data.dishes.mapTo(mutableSetOf()) { it.id }
        data.profiles.forEach { profileData ->
            val meals = profileData.plannedMeals
            require(meals.all { it.isValid() }) { "Hay alguna comida planificada no válida" }
            require(meals.map { it.id }.distinct().size == meals.size) {
                "Hay comidas planificadas duplicadas"
            }
            require(meals.flatMap { it.items }.all { it.foodId in foodIds }) {
                "Hay comidas con alimentos inexistentes"
            }
            require(meals.flatMap { it.dishes }.all { it.dishId in dishIds }) {
                "Hay comidas con platos inexistentes"
            }
            require(profileData.planningRules.all { it.isValid() }) {
                "Hay reglas de planificación no válidas"
            }
            require(profileData.planningRules.all { rule ->
                when (rule.itemKind) {
                    PlannedItemKind.FOOD -> rule.itemId in foodIds
                    PlannedItemKind.DISH -> rule.itemId in dishIds
                }
            }) { "Hay reglas para elementos inexistentes" }
            require(profileData.repertoireFoodIds.all { it in foodIds }) {
                "Hay alimentos inexistentes en el repertorio"
            }
            require(PlanWeek.entries.all { week ->
                MealType.entries.all { type ->
                    val days = meals.filter {
                        it.planWeek == week && it.type == type
                    }.flatMap { it.days }
                    days.distinct().size == days.size
                }
            }) { "Hay comidas del mismo tipo que se solapan" }
        }
    }

    private fun recalculate(profile: UserProfile, source: List<Measurement>): List<Measurement> {
        val ordered = source.sortedWith(compareBy<Measurement> { it.date }.thenBy { it.id })
        return buildList {
            ordered.forEach { item ->
                val draft = item.copy(recommendation = null)
                add(draft.copy(recommendation = RecommendationEngine.recommend(profile, this, draft)))
            }
        }
    }

    private fun encode(data: AppData): JSONObject = JSONObject().apply {
        put("schemaVersion", 19)
        putNullable("activeProfileId", data.activeProfileId)
        put("profiles", JSONArray().apply {
            data.profiles.forEach { profileData ->
                put(JSONObject().apply {
                    put("profile", encodeProfile(profileData.profile))
                    put("measurements", encodeMeasurements(profileData.measurements))
                    put("plannedMeals", encodePlannedMeals(profileData.plannedMeals))
                    put("planningRules", encodePlanningRules(profileData.planningRules))
                    put("repertoireFoodIds", JSONArray().apply {
                        profileData.repertoireFoodIds.forEach(::put)
                    })
                    put("dismissedSuggestionFoodIds", JSONArray().apply {
                        profileData.dismissedSuggestionFoodIds.forEach(::put)
                    })
                    put("menuHistory", encodeMenuHistory(profileData.menuHistory))
                })
            }
        })
        val currentFoodsById = data.foods.associateBy { it.id }
        val overrides = data.foods.filter { food -> baseFoodsById[food.id] != food }
        val deletedIds = baseFoods.asSequence().map { it.id }
            .filterNot(currentFoodsById::containsKey).toList()
        put("foodOverrides", encodeFoods(overrides))
        put("deletedFoodIds", JSONArray().apply { deletedIds.forEach(::put) })
        put("dishes", encodeDishes(data.dishes))
    }

    private fun encodeProfile(profile: UserProfile): JSONObject = JSONObject().apply {
        put("id", profile.id)
        put("name", profile.name)
        put("heightCm", profile.heightCm)
        put("birthYear", profile.birthYear)
        put("sex", profile.sex.name)
        profile.photoUri?.let { put("photoUri", it) }
    }

    private fun encodeMeasurements(measurements: List<Measurement>): JSONArray = JSONArray().apply {
        measurements.forEach { measurement ->
            put(JSONObject().apply {
                put("id", measurement.id)
                put("date", measurement.date.toString())
                putNullable("weightKg", measurement.weightKg)
                putNullable("waistCm", measurement.waistCm)
                putNullable("activity", measurement.activity?.name)
                putNullable("compliance", measurement.compliance?.name)
                putNullable("goal", measurement.goal?.name)
                putNullable("weeklyRateKg", measurement.weeklyRateKg)
            })
        }
    }

    private fun encodeFoods(foods: List<Food>): JSONArray = JSONArray().apply {
        foods.forEach { food ->
            put(JSONObject().apply {
                put("id", food.id)
                put("name", food.name)
                put("category", food.category.name)
                putNullable("calories", food.calories)
                putNullable("fatGrams", food.fatGrams)
                putNullable("carbohydrateGrams", food.carbohydrateGrams)
                putNullable("proteinGrams", food.proteinGrams)
                putNullable("fiberGrams", food.fiberGrams)
                put("links", JSONArray().apply { food.links.forEach(::put) })
                putNullable("barcode", food.barcode)
                putNullable("brand", food.brand)
                putNullable("family", food.family)
                putNullable("subcategory", food.subcategory)
                putNullable("legalName", food.legalName)
                putNullable("ingredients", food.ingredients)
                putNullable("saturatedFatGrams", food.saturatedFatGrams)
                putNullable("sugarGrams", food.sugarGrams)
                putNullable("saltGrams", food.saltGrams)
                putNullable("retailer", food.retailer)
                putNullable("source", food.source)
                putNullable("unitName", food.unitName)
                putNullable("unitPlural", food.unitPlural)
                put("unitGender", food.unitGender)
                putNullable("unitAmount", food.unitAmount)
                put("wholeUnitsOnly", food.wholeUnitsOnly)
                put("unitDivisions", food.unitDivisions)
                put("culinaryType", food.culinaryType.name)
            })
        }
    }

    private fun encodePlannedMeals(meals: List<PlannedMeal>): JSONArray = JSONArray().apply {
        meals.forEach { meal ->
            put(JSONObject().apply {
                put("id", meal.id)
                put("type", meal.type.name)
                put("planWeek", meal.planWeek.name)
                put("days", JSONArray().apply {
                    WeekDay.entries.filter(meal.days::contains).forEach { put(it.name) }
                })
                put("items", JSONArray().apply {
                    meal.items.forEach { item ->
                        put(JSONObject().apply {
                            put("foodId", item.foodId)
                            put("grams", item.grams)
                            put("adjustable", item.adjustable)
                            put("minimumGrams", item.minimumGrams)
                            put("maximumGrams", item.maximumGrams)
                        })
                    }
                })
                put("dishes", JSONArray().apply {
                    meal.dishes.forEach { plannedDish ->
                        put(JSONObject().apply {
                            put("dishId", plannedDish.dishId)
                            put("grams", plannedDish.grams)
                            put("adjustable", plannedDish.adjustable)
                            put("minimumGrams", plannedDish.minimumGrams)
                            put("maximumGrams", plannedDish.maximumGrams)
                        })
                    }
                })
                put("dayAmounts", JSONArray().apply {
                    meal.dayAmounts.forEach { amounts ->
                        put(JSONObject().apply {
                            put("day", amounts.day.name)
                            put("items", JSONArray().apply {
                                amounts.foodGrams.forEach { (foodId, grams) ->
                                    put(JSONObject().apply {
                                        put("foodId", foodId)
                                        put("grams", grams)
                                    })
                                }
                            })
                            put("dishes", JSONArray().apply {
                                amounts.dishGrams.forEach { (dishId, grams) ->
                                    put(JSONObject().apply {
                                        put("dishId", dishId)
                                        put("grams", grams)
                                    })
                                }
                            })
                        })
                    }
                })
            })
        }
    }

    private fun encodePlanningRules(rules: List<PlanningRule>): JSONArray = JSONArray().apply {
        rules.forEach { rule ->
            put(JSONObject().apply {
                put("itemKind", rule.itemKind.name)
                put("itemId", rule.itemId)
                put("ruleId", rule.ruleId)
                put("allowedMealTypes", JSONArray().apply {
                    rule.allowedMealTypes.forEach { put(it.name) }
                })
                put("frequency", rule.frequency.name)
                put("isActive", rule.isActive)
                put("preferredGrams", rule.preferredGrams)
                put("minimumFactor", rule.minimumFactor)
                put("maximumFactor", rule.maximumFactor)
            })
        }
    }

    private fun encodeMenuHistory(history: List<MenuHistoryEntry>): JSONArray = JSONArray().apply {
        history.forEach { entry ->
            put(JSONObject().apply {
                put("generation", entry.generation)
                put("itemKind", entry.itemKind.name)
                put("itemId", entry.itemId)
                put("day", entry.day.name)
                put("mealType", entry.mealType.name)
            })
        }
    }

    private fun encodeDishes(dishes: List<Dish>): JSONArray = JSONArray().apply {
        dishes.forEach { dish ->
            put(JSONObject().apply {
                put("id", dish.id)
                put("name", dish.name)
                putNullable("unitName", dish.unitName)
                putNullable("unitPlural", dish.unitPlural)
                put("unitGender", dish.unitGender)
                putNullable("unitAmount", dish.unitAmount)
                put("wholeUnitsOnly", dish.wholeUnitsOnly)
                put("unitDivisions", dish.unitDivisions)
                put("allowedMealTypes", JSONArray(dish.allowedMealTypes.map { it.name }))
                put("ingredients", JSONArray().apply {
                    dish.ingredients.forEach { ingredient ->
                        put(JSONObject().apply {
                            put("foodId", ingredient.foodId)
                            put("grams", ingredient.grams)
                        })
                    }
                })
            })
        }
    }

    private fun decode(raw: String): AppData {
        val root = JSONObject(raw)
        val schemaVersion = root.optInt("schemaVersion", 1)
        val profilesJson = root.optJSONArray("profiles")
        if (profilesJson != null) {
            val dishes = root.optJSONArray("dishes")?.let(::decodeDishes).orEmpty()
            val dishesById = dishes.associateBy { it.id }
            val profiles = buildList {
                for (index in 0 until profilesJson.length()) {
                    val item = profilesJson.getJSONObject(index)
                    add(
                        ProfileData(
                            profile = decodeProfile(item.getJSONObject("profile")),
                            measurements = decodeMeasurements(item.optJSONArray("measurements") ?: JSONArray()),
                            plannedMeals = decodePlannedMeals(
                                item.optJSONArray("plannedMeals") ?: JSONArray(),
                                dishesById,
                                schemaVersion
                            ),
                            planningRules = decodePlanningRules(item.optJSONArray("planningRules") ?: JSONArray()),
                            repertoireFoodIds = item.optJSONArray("repertoireFoodIds")?.let(::decodeIds)
                                ?: decodePlanningRules(item.optJSONArray("planningRules") ?: JSONArray())
                                    .filter { it.itemKind == PlannedItemKind.FOOD }
                                    .mapTo(mutableSetOf()) { it.itemId },
                            dismissedSuggestionFoodIds = item
                                .optJSONArray("dismissedSuggestionFoodIds")
                                ?.let(::decodeIds)
                                .orEmpty(),
                            menuHistory = decodeMenuHistory(item.optJSONArray("menuHistory") ?: JSONArray())
                        )
                    )
                }
            }
            val foods = if (schemaVersion >= 6) {
                val overrides = root.optJSONArray("foodOverrides")?.let(::decodeFoods).orEmpty()
                val deletedIds = root.optJSONArray("deletedFoodIds")?.let(::decodeIds).orEmpty()
                mergeFoodChanges(overrides, deletedIds)
            } else {
                migrateLegacyFoods(root.optJSONArray("foods")?.let(::decodeFoods), schemaVersion)
            }
            return AppData(profiles, root.optionalLong("activeProfileId"), foods, dishes)
        }

        val legacyProfile = root.optJSONObject("profile") ?: return AppData()
        val migrated = UserProfile(
            id = 1L,
            name = "Mi perfil",
            heightCm = legacyProfile.getDouble("heightCm"),
            birthYear = legacyProfile.getInt("birthYear"),
            sex = Sex.valueOf(legacyProfile.getString("sex"))
        )
        val measurements = decodeMeasurements(root.optJSONArray("measurements") ?: JSONArray())
        return AppData(listOf(ProfileData(migrated, measurements)), migrated.id, baseFoods)
    }

    private fun decodeProfile(json: JSONObject): UserProfile = UserProfile(
        id = json.getLong("id"),
        name = json.getString("name"),
        heightCm = json.getDouble("heightCm"),
        birthYear = json.getInt("birthYear"),
        sex = Sex.valueOf(json.getString("sex")),
        photoUri = json.optString("photoUri").takeIf { it.isNotBlank() }
    )

    private fun decodeMeasurements(array: JSONArray): List<Measurement> = buildList {
        for (index in 0 until array.length()) {
            val item = array.getJSONObject(index)
            add(
                Measurement(
                    id = item.getLong("id"),
                    date = LocalDate.parse(item.getString("date")),
                    weightKg = item.optionalDouble("weightKg"),
                    waistCm = item.optionalDouble("waistCm"),
                    activity = item.optionalEnum("activity", ActivityLevel::valueOf),
                    compliance = item.optionalEnum("compliance", DietCompliance::valueOf),
                    goal = item.optionalEnum("goal", WeightGoal::valueOf),
                    weeklyRateKg = item.optionalDouble("weeklyRateKg")
                )
            )
        }
    }.sortedWith(compareBy<Measurement> { it.date }.thenBy { it.id })

    private fun decodeFoods(array: JSONArray): List<Food> = buildList {
        for (index in 0 until array.length()) {
            val item = array.getJSONObject(index)
            add(
                Food(
                    id = item.getLong("id"),
                    name = item.getString("name"),
                    category = FoodCategory.valueOf(item.getString("category")),
                    calories = item.optionalDouble("calories"),
                    fatGrams = item.optionalDouble("fatGrams"),
                    carbohydrateGrams = item.optionalDouble("carbohydrateGrams"),
                    proteinGrams = item.optionalDouble("proteinGrams"),
                    fiberGrams = item.optionalDouble("fiberGrams"),
                    links = item.optJSONArray("links")?.let { links ->
                        buildList {
                            for (linkIndex in 0 until links.length()) add(links.getString(linkIndex))
                        }
                    }.orEmpty(),
                    barcode = item.optionalString("barcode"),
                    brand = item.optionalString("brand"),
                    family = item.optionalString("family"),
                    subcategory = item.optionalString("subcategory"),
                    legalName = item.optionalString("legalName"),
                    ingredients = item.optionalString("ingredients"),
                    saturatedFatGrams = item.optionalDouble("saturatedFatGrams"),
                    sugarGrams = item.optionalDouble("sugarGrams"),
                    saltGrams = item.optionalDouble("saltGrams"),
                    retailer = item.optionalString("retailer"),
                    source = item.optionalString("source"),
                    unitName = item.optionalString("unitName"),
                    unitPlural = item.optionalString("unitPlural"),
                    unitGender = item.optString("unitGender", "MASCULINE"),
                    unitAmount = item.optionalDouble("unitAmount"),
                    wholeUnitsOnly = item.optBoolean("wholeUnitsOnly", false),
                    unitDivisions = item.optInt("unitDivisions", 1).coerceIn(1, 100),
                    culinaryType = item.optionalEnum("culinaryType", CulinaryType::valueOf)
                        ?: baseFoodsById[item.getLong("id")]?.culinaryType
                        ?: CulinaryType.UNKNOWN
                )
            )
        }
    }.sortedWith(foodComparator)

    private fun decodePlannedMeals(
        array: JSONArray,
        dishesById: Map<Long, Dish>,
        schemaVersion: Int
    ): List<PlannedMeal> = buildList {
        for (index in 0 until array.length()) {
            val item = array.getJSONObject(index)
            val daysJson = item.optJSONArray("days") ?: JSONArray()
            val itemsJson = item.optJSONArray("items") ?: JSONArray()
            val dishesJson = item.optJSONArray("dishes") ?: JSONArray()
            val dayAmountsJson = item.optJSONArray("dayAmounts") ?: JSONArray()
            add(
                PlannedMeal(
                    id = item.getLong("id"),
                    type = MealType.valueOf(item.getString("type")),
                    planWeek = if (schemaVersion >= 13) {
                        PlanWeek.valueOf(item.optString("planWeek", PlanWeek.CURRENT.name))
                    } else PlanWeek.CURRENT,
                    days = buildSet {
                        for (dayIndex in 0 until daysJson.length()) {
                            add(WeekDay.valueOf(daysJson.getString(dayIndex)))
                        }
                    },
                    items = buildList {
                        for (itemIndex in 0 until itemsJson.length()) {
                            val planned = itemsJson.getJSONObject(itemIndex)
                            val grams = planned.getDouble("grams")
                            add(
                                PlannedFood(
                                    foodId = planned.getLong("foodId"),
                                    grams = grams,
                                    adjustable = schemaVersion >= 10 && planned.optBoolean("adjustable", false),
                                    minimumGrams = if (schemaVersion >= 10) planned.optDouble("minimumGrams", grams * 0.5) else grams * 0.5,
                                    maximumGrams = if (schemaVersion >= 10) planned.optDouble("maximumGrams", grams * 1.5) else grams * 1.5
                                )
                            )
                        }
                    },
                    dishes = buildList {
                        for (dishIndex in 0 until dishesJson.length()) {
                            val planned = dishesJson.getJSONObject(dishIndex)
                            val dishId = planned.getLong("dishId")
                            val grams = if (schemaVersion >= 9) {
                                planned.getDouble("grams")
                            } else {
                                val servings = planned.getDouble("servings")
                                dishesById[dishId]?.ingredients?.sumOf { it.grams }?.times(servings)
                                    ?: 0.0
                            }
                            add(
                                PlannedDish(
                                    dishId = dishId,
                                    grams = grams,
                                    adjustable = schemaVersion >= 10 && planned.optBoolean("adjustable", false),
                                    minimumGrams = if (schemaVersion >= 10) planned.optDouble("minimumGrams", grams * 0.5) else grams * 0.5,
                                    maximumGrams = if (schemaVersion >= 10) planned.optDouble("maximumGrams", grams * 1.5) else grams * 1.5
                                )
                            )
                        }
                    },
                    dayAmounts = buildList {
                        if (schemaVersion >= 10) for (amountIndex in 0 until dayAmountsJson.length()) {
                            val amounts = dayAmountsJson.getJSONObject(amountIndex)
                            val foodAmountsJson = amounts.optJSONArray("items") ?: JSONArray()
                            val dishAmountsJson = amounts.optJSONArray("dishes") ?: JSONArray()
                            add(
                                MealDayAmounts(
                                    day = WeekDay.valueOf(amounts.getString("day")),
                                    foodGrams = buildMap {
                                        for (i in 0 until foodAmountsJson.length()) {
                                            val entry = foodAmountsJson.getJSONObject(i)
                                            put(entry.getLong("foodId"), entry.getDouble("grams"))
                                        }
                                    },
                                    dishGrams = buildMap {
                                        for (i in 0 until dishAmountsJson.length()) {
                                            val entry = dishAmountsJson.getJSONObject(i)
                                            put(entry.getLong("dishId"), entry.getDouble("grams"))
                                        }
                                    }
                                )
                            )
                        }
                    }
                ).sanitizedDayAmounts()
            )
        }
    }.sortedWith(plannedMealComparator)

    private fun decodePlanningRules(array: JSONArray): List<PlanningRule> = buildList {
        for (index in 0 until array.length()) {
            val item = array.getJSONObject(index)
            val allowed = item.optJSONArray("allowedMealTypes") ?: JSONArray()
            val fixed = item.optJSONArray("fixedSlots") ?: JSONArray()
            val legacyFixedMealTypes = buildSet {
                for (i in 0 until fixed.length()) {
                    add(MealType.valueOf(fixed.getJSONObject(i).getString("mealType")))
                }
            }
            add(
                PlanningRule(
                    itemKind = PlannedItemKind.valueOf(item.getString("itemKind")),
                    itemId = item.getLong("itemId"),
                    allowedMealTypes = buildSet {
                        for (i in 0 until allowed.length()) add(MealType.valueOf(allowed.getString(i)))
                        addAll(legacyFixedMealTypes)
                    },
                    fixedSlots = emptySet(),
                    frequency = PlanningFrequency.valueOf(item.optString("frequency", PlanningFrequency.NORMAL.name)),
                    isActive = item.optBoolean("isActive", true),
                    preferredGrams = item.optDouble("preferredGrams", 100.0),
                    minimumFactor = item.optDouble("minimumFactor", 0.5),
                    maximumFactor = item.optDouble("maximumFactor", 1.5),
                    ruleId = item.optLong("ruleId", item.getLong("itemId")),
                    allowedDays = WeekDay.entries.toSet()
                )
            )
        }
    }

    private fun decodeMenuHistory(array: JSONArray): List<MenuHistoryEntry> = buildList {
        for (index in 0 until array.length()) {
            val item = array.getJSONObject(index)
            add(
                MenuHistoryEntry(
                    generation = item.getInt("generation"),
                    itemKind = PlannedItemKind.valueOf(item.getString("itemKind")),
                    itemId = item.getLong("itemId"),
                    day = WeekDay.valueOf(item.getString("day")),
                    mealType = MealType.valueOf(item.getString("mealType"))
                )
            )
        }
    }

    private fun decodeDishes(array: JSONArray): List<Dish> = buildList {
        for (index in 0 until array.length()) {
            val item = array.getJSONObject(index)
            val ingredientsJson = item.optJSONArray("ingredients") ?: JSONArray()
            add(
                Dish(
                    id = item.getLong("id"),
                    name = item.getString("name"),
                    unitName = item.optionalString("unitName"),
                    unitPlural = item.optionalString("unitPlural"),
                    unitGender = item.optString("unitGender", "MASCULINE"),
                    unitAmount = item.optionalDouble("unitAmount"),
                    wholeUnitsOnly = item.optBoolean("wholeUnitsOnly", false),
                    unitDivisions = item.optInt("unitDivisions", 1).coerceIn(1, 100),
                    allowedMealTypes = item.optJSONArray("allowedMealTypes")?.let { values ->
                        buildSet {
                            for (valueIndex in 0 until values.length()) {
                                runCatching { MealType.valueOf(values.getString(valueIndex)) }.getOrNull()?.let(::add)
                            }
                        }
                    } ?: MealType.entries.toSet(),
                    allowedDays = WeekDay.entries.toSet(),
                    ingredients = buildList {
                        for (ingredientIndex in 0 until ingredientsJson.length()) {
                            val ingredient = ingredientsJson.getJSONObject(ingredientIndex)
                            add(
                                DishIngredient(
                                    ingredient.getLong("foodId"),
                                    ingredient.getDouble("grams")
                                )
                            )
                        }
                    }
                )
            )
        }
    }.sortedWith(dishComparator)

    private fun decodeIds(array: JSONArray): Set<Long> = buildSet {
        for (index in 0 until array.length()) add(array.getLong(index))
    }

    private fun mergeFoodChanges(overrides: List<Food>, deletedIds: Set<Long>): List<Food> {
        val overrideById = overrides.associateBy { it.id }
        return (baseFoods.asSequence()
            .filterNot { it.id in deletedIds }
            .map { overrideById[it.id] ?: it } +
            overrides.asSequence().filterNot { baseFoodsById.containsKey(it.id) })
            .distinctBy { it.id }
            .sortedWith(foodComparator)
            .toList()
    }

    private fun migrateLegacyFoods(decoded: List<Food>?, schemaVersion: Int): List<Food> {
        if (decoded == null) return baseFoods
        val legacyFoods = if (schemaVersion < 5) addDefaultLinks(decoded) else decoded
        val legacyById = legacyFoods.associateBy { it.id }
        val defaultById = DefaultFoodCatalog.items.associateBy { it.id }
        val deletedDefaultIds = defaultById.keys - legacyById.keys
        val overrides = legacyFoods.filter { food -> defaultById[food.id] != food }
        return mergeFoodChanges(overrides, deletedDefaultIds)
    }

    private fun addDefaultLinks(foods: List<Food>): List<Food> {
        val defaults = DefaultFoodCatalog.items.associateBy { it.id }
        return foods.map { food ->
            val default = defaults[food.id]
            if (food.links.isEmpty() && default?.name == food.name) food.copy(links = default.links) else food
        }
    }

    private fun JSONObject.putNullable(name: String, value: Any?) {
        if (value == null) put(name, JSONObject.NULL) else put(name, value)
    }

    private fun JSONObject.optionalDouble(name: String): Double? =
        if (isNull(name) || !has(name)) null else getDouble(name)

    private fun JSONObject.optionalLong(name: String): Long? =
        if (isNull(name) || !has(name)) null else getLong(name)

    private fun JSONObject.optionalString(name: String): String? =
        if (isNull(name) || !has(name)) null else getString(name)

    private fun <T> JSONObject.optionalEnum(name: String, parser: (String) -> T): T? =
        if (isNull(name) || !has(name)) null else parser(getString(name))

    companion object {
        private const val KEY_DATA = "app_data_v1"
        private val foodComparator = compareBy<Food> { it.category.ordinal }
            .thenBy { it.name.lowercase() }
        private val dishComparator = compareBy<Dish> { it.name.lowercase() }
        private val plannedMealComparator = compareBy<PlannedMeal> { it.planWeek.ordinal }
            .thenBy { it.type.ordinal }
            .thenBy { meal -> WeekDay.entries.indexOfFirst(meal.days::contains) }
    }
}
